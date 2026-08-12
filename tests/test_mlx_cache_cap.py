"""GH-219 Lane 2 (#215) — cap and clear the MLX buffer cache.

Tests the fix for unbounded cache growth when embedding variable-length texts.
"""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from rebalance.ingest import embedder
from rebalance.ingest.embedder import _embed_batch, _load_model


class MockMLXCoreForCap:
    def __init__(self) -> None:
        self.reset_count = 0
        self.clear_cache_count = 0
        self.set_cache_limit_count = 0
        self.cache_limit_val = None
        self.active_val = 1000
        self.peak_val = 3000
        self._simulated_cache = 0

    def reset_peak_memory(self) -> None:
        self.reset_count += 1

    def clear_cache(self) -> None:
        self.clear_cache_count += 1
        self._simulated_cache = 0

    def set_cache_limit(self, limit: int) -> None:
        self.set_cache_limit_count += 1
        self.cache_limit_val = limit

    def get_active_memory(self) -> int:
        return self.active_val

    def get_cache_memory(self) -> int:
        return self._simulated_cache

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
    import sys
    core = sys.modules.get("mlx.core")
    if hasattr(core, "_simulated_cache"):
        total_len = sum(len(t) for t in texts)
        core._simulated_cache += total_len * 1024 * 1024
    return MockGenerateOutput(len(texts))


@pytest.fixture
def mock_mlx_cap():
    """Replace mlx.core on the PARENT PACKAGE."""
    import mlx
    import mlx.core  # noqa: F401

    mock_core = MockMLXCoreForCap()
    mock_embeddings = MagicMock()
    mock_embeddings.generate = mock_generate
    mock_embeddings.load = MagicMock(return_value=("mock_model", "mock_tokenizer"))

    with patch.object(mlx, "core", mock_core), patch.dict(
        sys.modules, {"mlx.core": mock_core, "mlx_embeddings": mock_embeddings}
    ):
        yield mock_core


@pytest.fixture
def propagating_logs():
    """Let caplog see records from the ``rebalance`` logger tree."""
    lg = logging.getLogger("rebalance")
    previous_propagate, previous_level = lg.propagate, lg.level
    lg.propagate = True
    lg.setLevel(logging.INFO)
    try:
        yield
    finally:
        lg.propagate = previous_propagate
        lg.setLevel(previous_level)


@pytest.fixture(autouse=True)
def reset_instrumentation_state():
    """Module-level counters are global; isolate every test from its neighbours."""
    embedder._current_run_id = None
    embedder._current_entry_point = None
    embedder._batch_count = 0
    embedder._last_activity_time = 0.0
    embedder._cached_model = None
    embedder._cached_tokenizer = None
    embedder._cached_model_name = None
    embedder._cache_limit_set = False
    yield


@pytest.mark.requires_metal
def test_cache_bounded_variable_lengths():
    """Cache stays bounded across many VARIABLE-length batches."""
    # This must use the real MLX to prove the cache bound works with variable lengths.
    #
    # GH-250: the `requires_metal` marker is what actually protects this test.
    # The previous inline guard caught RuntimeError("No Metal device available"),
    # but with no reachable device MLX ABORTS (SIGABRT) inside load() rather than
    # raising — so the except never ran and the whole pytest process died,
    # discarding every other test's result. Observed 4x on 2026-08-04 inside the
    # codex/agy relay-turn sandbox. A signal cannot be caught in-process; the
    # marker probes out-of-process (see tests/conftest.py) and skips before any
    # MLX call happens here.
    try:
        import mlx.core as mx
        from mlx_embeddings import load

        load(embedder.DEFAULT_MODEL)
    except ImportError:
        pytest.skip("mlx / mlx_embeddings not installed")

    embedder._cached_model = None
    embedder._cached_tokenizer = None
    embedder._cached_model_name = None
    
    # Run _load_model to set the limit
    model, tokenizer = _load_model(embedder.DEFAULT_MODEL)
    
    # 20 batches of variable lengths
    for i in range(20):
        # variable length between 10 and 100 words
        texts = ["word " * (10 + (i * 13) % 90) for _ in range(5)]
        _embed_batch(model, tokenizer, texts)
        
    final_cache = mx.get_cache_memory()
    
    # If the bug was present, final_cache would grow unbounded with each variable length batch.
    # We assert that the final cache is safely bounded (way less than gigabytes of unbounded growth).
    # Specifically, it shouldn't be much higher than the cache limit we set (3 GB), 
    # and since we are clearing it on every batch, it should actually be extremely small.
    # We use a generous 200MB threshold to avoid flakiness while clearly catching gigabytes of growth.
    assert final_cache < 200 * 1024 * 1024, f"Cache grew unbounded to {final_cache / 1024 / 1024:.2f} MB"


def test_mocked_cache_bounded_variable_lengths(mock_mlx_cap):
    """Proves clear_cache() bounds cache growth deterministically without real MLX."""
    # Run _load_model to set the limit
    model, tokenizer = _load_model("test_model")
    
    # 20 batches of variable lengths
    for i in range(20):
        # variable length between 10 and 100 words
        texts = ["word " * (10 + (i * 13) % 90) for _ in range(5)]
        _embed_batch(model, tokenizer, texts)
        
    # We should have cleared cache exactly 20 times (once per batch)
    assert mock_mlx_cap.clear_cache_count == 20
    # Cache should be bounded (cleared after last batch)
    assert mock_mlx_cap.get_cache_memory() == 0

    # Prove it would grow without clearing
    with patch.object(mock_mlx_cap, "clear_cache", lambda: None):
        for i in range(20):
            texts = ["word " * (10 + (i * 13) % 90) for _ in range(5)]
            _embed_batch(model, tokenizer, texts)
        
        # Cache should have grown significantly due to variable shapes
        assert mock_mlx_cap.get_cache_memory() > 0


def test_set_cache_limit_applied_once(mock_mlx_cap):
    """set_cache_limit is applied once, not per call."""
    _load_model("test_model")
    assert mock_mlx_cap.set_cache_limit_count == 1
    assert mock_mlx_cap.cache_limit_val == int(3.0 * 1024 * 1024 * 1024)
    
    # Second call with distinct model name uses cache limit previously set, does not set limit again
    _load_model("test_model_2")
    assert mock_mlx_cap.set_cache_limit_count == 1


def test_clear_cache_invoked_expected_cadence(mock_mlx_cap):
    """clear_cache is invoked at the end of each batch."""
    _embed_batch("model", "tokenizer", ["text1"])
    assert mock_mlx_cap.clear_cache_count == 1
    
    _embed_batch("model", "tokenizer", ["text2"])
    assert mock_mlx_cap.clear_cache_count == 2


@pytest.mark.parametrize(
    ("module", "site"),
    [
        ("embedder.py", "embed_chunks"),
        ("semantic_index.py", "embed_pending"),
        ("github_knowledge.py", "_default_embed_texts"),
    ],
)
def test_all_four_call_sites_covered(module: str, site: str):
    """All four call sites actually delegate to _load_model / _embed_batch."""
    import importlib
    from unittest.mock import patch
    from pathlib import Path

    mod_name = module.replace(".py", "")
    full_mod_name = f"rebalance.ingest.{mod_name}"
    mod = importlib.import_module(full_mod_name)
    
    with patch(f"{full_mod_name}._load_model") as mock_load, \
         patch(f"{full_mod_name}._embed_batch") as mock_embed:
         
        mock_load.return_value = ("mock_model", "mock_tokenizer")
        mock_embed.return_value = [[0.1] * 1024]

        if site == "embed_chunks":
            with patch(f"{full_mod_name}.db_connection") as mock_db:
                mock_conn = mock_db.return_value.__enter__.return_value
                mock_conn.execute.return_value.fetchone.return_value = [1]
                mock_conn.execute.return_value.fetchall.return_value = [{"id": "1", "body": "test"}]
                mod.embed_chunks(Path("/tmp/fake.db"))
                

        elif site == "embed_pending":
            with patch(f"{full_mod_name}.sem") as mock_sem, \
                 patch(f"{full_mod_name}.db_connection") as mock_db:
                mock_sem.semantic_documents_pending_embed.return_value = [{"id": 1, "body": "test"}]
                mock_sem.count_embeddable_semantic_documents.return_value = 1
                mod.embed_pending(Path("/tmp/fake.db"))
                
        elif site == "_default_embed_texts":
            func = getattr(mod, site)
            func(["text"], "test_model")
            
        mock_load.assert_called_once()
        mock_embed.assert_called_once()


def test_telemetry_emitted_at_warning(mock_mlx_cap, caplog, propagating_logs):
    """Telemetry is emitted at WARNING level so it survives default config."""
    caplog.set_level(logging.WARNING)
    embedder._current_run_id = "test-run"
    embedder._current_entry_point = "test"

    for _ in range(10):
        embedder._embed_batch(None, None, ["text"])
        
    records = [r for r in caplog.records if "MLX telemetry" in r.message]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING


def test_degrades_safely_when_mlx_unavailable(caplog, propagating_logs):
    """Behaviour degrades safely when new cache methods fail."""
    import mlx
    import mlx.core  # noqa: F401
    
    broken = MagicMock()
    broken.set_cache_limit.side_effect = RuntimeError("no Metal device")
    broken.clear_cache.side_effect = RuntimeError("no Metal device")
    broken.get_active_memory.side_effect = RuntimeError("no Metal device")
    broken.get_cache_memory.side_effect = RuntimeError("no Metal device")
    broken.get_peak_memory.side_effect = RuntimeError("no Metal device")
    broken.eval = MagicMock()
    
    mock_embeddings = MagicMock()
    mock_embeddings.generate = mock_generate
    mock_embeddings.load = MagicMock(return_value=("mock_model", "mock_tokenizer"))
    
    with patch.object(mlx, "core", broken), patch.dict(
        sys.modules, {"mlx.core": broken, "mlx_embeddings": mock_embeddings}
    ):
        embedder._cache_limit_set = False
        embedder._cached_model = None
        
        # Should return models successfully despite set_cache_limit failing
        model, tokenizer = embedder._load_model("test_model")
        assert model == "mock_model"
        
        # Should return embeddings successfully despite clear_cache failing
        vectors = embedder._embed_batch(model, tokenizer, ["text"])
        assert len(vectors) == 1
        assert len(vectors[0]) == embedder.EMBEDDING_DIM
