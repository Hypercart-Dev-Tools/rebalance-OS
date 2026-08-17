"""GH-219 Lane 1 (#216) — MLX memory instrumentation.

Covers the telemetry + run-ID/entry-point attribution added to the embedding path.

Two non-obvious things these tests have to work around, both of which silently
produced false passes/failures in the first draft:

1. ``logging.getLogger("rebalance")`` sets ``propagate = False`` and installs its
   own handler, so records never reach the root logger where pytest's ``caplog``
   attaches. Every caplog assertion sees zero records unless propagation is
   restored for the duration of the test — see the ``propagating_logs`` fixture.

2. ``mlx`` is a REAL installed package here, so ``import mlx.core as mx`` resolves
   through ``getattr(mlx, "core")`` and a ``sys.modules["mlx.core"]`` patch is
   ignored entirely. The mock must replace the attribute on the parent package —
   see the ``mock_mlx`` fixture. Patching sys.modules alone silently exercises
   real MLX and leaves the mock's counters at zero.
"""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rebalance.ingest import embedder

SRC = Path(__file__).resolve().parents[1] / "src" / "rebalance" / "ingest"


class MockMLXCore:
    def __init__(self) -> None:
        self.reset_count = 0
        self.active_val = 1000
        self.cache_val = 2000
        self.peak_val = 3000

    def reset_peak_memory(self) -> None:
        self.reset_count += 1

    def get_active_memory(self) -> int:
        return self.active_val

    def get_cache_memory(self) -> int:
        return self.cache_val

    def get_peak_memory(self) -> int:
        return self.peak_val

    def eval(self, *_args) -> None:
        pass


class MockGenerateOutput:
    def __init__(self, n: int) -> None:
        self.text_embeds = MagicMock()
        self.text_embeds.tolist.return_value = [
            [0.0] * embedder.EMBEDDING_DIM for _ in range(n)
        ]


def mock_generate(_model, _tokenizer, texts):
    return MockGenerateOutput(len(texts))


@pytest.fixture
def propagating_logs():
    """Let caplog see records from the ``rebalance`` logger tree.

    Two separate barriers, and BOTH must come down (see module docstring):
      * ``propagate = False`` stops records reaching root, where caplog attaches.
      * the package sets the ``rebalance`` logger to WARNING, so ``logger.info()``
        is discarded before a record is even constructed — a level change on the
        root logger alone cannot bring it back.
    """
    lg = logging.getLogger("rebalance")
    previous_propagate, previous_level = lg.propagate, lg.level
    lg.propagate = True
    lg.setLevel(logging.INFO)
    try:
        yield
    finally:
        lg.propagate = previous_propagate
        lg.setLevel(previous_level)


@pytest.fixture
def mock_mlx():
    """Replace mlx.core on the PARENT PACKAGE, not just in sys.modules.

    ``import mlx`` alone does not bind the ``core`` attribute, so patch.object
    would fail to find an original; importing the submodule materialises it.
    """
    import mlx
    import mlx.core  # noqa: F401  — materialises the attribute patch.object needs

    mock_core = MockMLXCore()
    mock_embeddings = MagicMock()
    mock_embeddings.generate = mock_generate

    with patch.object(mlx, "core", mock_core), patch.dict(
        sys.modules, {"mlx.core": mock_core, "mlx_embeddings": mock_embeddings}
    ):
        yield mock_core


@pytest.fixture(autouse=True)
def reset_instrumentation_state():
    """Module-level counters are global; isolate every test from its neighbours."""
    embedder._current_run_id = None
    embedder._current_entry_point = None
    embedder._batch_count = 0
    embedder._last_activity_time = 0.0
    yield


def test_telemetry_cadence_and_keys(mock_mlx, caplog, propagating_logs):
    """Telemetry is emitted every 10 batches, carrying the documented keys."""
    caplog.set_level(logging.INFO)
    embedder._current_run_id = "test-run"
    embedder._current_entry_point = "test"

    for _ in range(9):
        embedder._embed_batch(None, None, ["text"])
    assert [r for r in caplog.records if "MLX telemetry" in r.message] == []

    embedder._embed_batch(None, None, ["text"])

    records = [r for r in caplog.records if "MLX telemetry" in r.message]
    assert len(records) == 1
    msg = records[0].message
    assert "run_id=test-run" in msg
    assert "batch=10" in msg
    assert "active_mem=1000" in msg
    assert "cache_mem=2000" in msg
    assert "peak_mem=3000" in msg


def test_reset_peak_memory_once_per_pass(mock_mlx):
    """reset_peak_memory fires once per pass, not per batch."""
    embedder.instrument_embedding_pass("test_site")
    assert mock_mlx.reset_count == 1

    # Re-entering the same site mid-pass must not reset the peak again.
    for _ in range(5):
        embedder._embed_batch(None, None, ["text"])
        embedder.instrument_embedding_pass("test_site")
    assert mock_mlx.reset_count == 1

    # A different entry point is a new pass.
    embedder.instrument_embedding_pass("other_site")
    assert mock_mlx.reset_count == 2


@pytest.mark.parametrize(
    ("module", "site"),
    [
        ("embedder.py", "embed_chunks"),
        ("semantic_index.py", "embed_pending"),
        ("github_knowledge.py", "_default_embed_texts"),
    ],
)
def test_all_four_call_sites_instrumented(module: str, site: str):
    """Each of the four embedding call sites announces itself.

    Deliberately a substring check, not a regex over the function signature: an
    earlier version asserted ``def <name>([^:]+: instrument_embedding_pass(...)``
    which can never match, because ``[^:]+`` cannot cross annotated parameters.
    That made the test fail against correct code.
    """
    source = (SRC / module).read_text(encoding="utf-8")
    assert f'instrument_embedding_pass("{site}")' in source, (
        f"{module} does not instrument {site} — an uninstrumented embedding path "
        "is exactly how the 07-27 episodes went unattributed"
    )


def test_call_site_emits_run_id_entry_point_and_pid(caplog, propagating_logs):
    """The attribution record carries everything needed to trace an episode to a caller."""
    caplog.set_level(logging.INFO)

    embedder.instrument_embedding_pass("embed_chunks")

    records = [r for r in caplog.records if "Embedding pass started" in r.message]
    assert len(records) == 1
    msg = records[0].message
    assert "run_id=" in msg
    assert "entry_point=embed_chunks" in msg
    assert f"pid={__import__('os').getpid()}" in msg


def test_instrumentation_degrades_when_mlx_absent(caplog, propagating_logs):
    """Telemetry must never become a new crash path.

    Scoped to the INSTRUMENTATION only. ``_embed_batch`` legitimately requires MLX
    to embed anything at all, so asserting it survives without MLX (as the first
    draft did) tests a behaviour the code neither has nor should have.
    """
    import mlx

    caplog.set_level(logging.INFO)

    broken = MagicMock()
    broken.reset_peak_memory.side_effect = RuntimeError("no Metal device")
    broken.get_active_memory.side_effect = RuntimeError("no Metal device")

    with patch.object(mlx, "core", broken):
        embedder.instrument_embedding_pass("test_site")  # must not raise

    records = [r for r in caplog.records if "Embedding pass started" in r.message]
    assert len(records) == 1, "attribution must survive MLX telemetry failure"
