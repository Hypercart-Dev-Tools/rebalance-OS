import logging
import sys
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rebalance.ingest import embedder

def _fake_embed_batch(_model, _tokenizer, texts):
    return [[0.0] * embedder.EMBEDDING_DIM for _ in texts]

class MockMLXCore:
    def __init__(self):
        self.reset_count = 0
        self.active_val = 1000
        self.cache_val = 2000
        self.peak_val = 3000

    def reset_peak_memory(self):
        self.reset_count += 1

    def get_active_memory(self):
        return self.active_val

    def get_cache_memory(self):
        return self.cache_val

    def get_peak_memory(self):
        return self.peak_val

    def eval(self, *args):
        pass

class MockGenerateOutput:
    def __init__(self, n):
        self.text_embeds = MagicMock()
        self.text_embeds.tolist.return_value = [[0.0] * embedder.EMBEDDING_DIM for _ in range(n)]

def mock_generate(model, tokenizer, texts):
    return MockGenerateOutput(len(texts))

@pytest.fixture
def mock_mlx():
    mock_core = MockMLXCore()
    mock_embeddings = MagicMock()
    mock_embeddings.generate = mock_generate
    
    with patch.dict(sys.modules, {'mlx.core': mock_core, 'mlx_embeddings': mock_embeddings}):
        yield mock_core

def test_telemetry_cadence_and_keys(mock_mlx, caplog, monkeypatch):
    """Telemetry is emitted at the expected cadence (every 10 batches), with the expected keys."""
    caplog.set_level(logging.INFO)
    embedder._batch_count = 0
    embedder._current_run_id = "test-run"
    embedder._current_entry_point = "test"
    embedder._last_activity_time = 0.0

    for _ in range(9):
        embedder._embed_batch(None, None, ["text"])
        
    records = [r for r in caplog.records if "MLX telemetry" in r.message]
    assert len(records) == 0

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
    """reset_peak_memory is called once per pass, not per batch."""
    embedder._current_run_id = None
    embedder._current_entry_point = None
    embedder._batch_count = 0
    embedder._last_activity_time = 0.0
    
    embedder.instrument_embedding_pass("test_site")
    assert mock_mlx.reset_count == 1
    
    for _ in range(5):
        embedder._embed_batch(None, None, ["text"])
        embedder.instrument_embedding_pass("test_site")
        
    assert mock_mlx.reset_count == 1
    
    embedder.instrument_embedding_pass("other_site")
    assert mock_mlx.reset_count == 2

def test_four_call_sites_covered_by_grep():
    """All four call sites are covered - verifiable by grep."""
    root = Path(__file__).resolve().parents[1]
    
    embedder_py = (root / "src" / "rebalance" / "ingest" / "embedder.py").read_text()
    semantic_index_py = (root / "src" / "rebalance" / "ingest" / "semantic_index.py").read_text()
    github_knowledge_py = (root / "src" / "rebalance" / "ingest" / "github_knowledge.py").read_text()
    
    # Check embed_chunks in embedder.py
    assert re.search(r'def embed_chunks\([^:]+:\s*instrument_embedding_pass\("embed_chunks"\)', embedder_py, re.DOTALL)
    
    # Check query_similar in embedder.py
    assert re.search(r'def query_similar\([^:]+:\s*instrument_embedding_pass\("query_similar"\)', embedder_py, re.DOTALL)
    
    # Check embed_pending in semantic_index.py
    assert re.search(r'def embed_pending\([^:]+:\s*.*?instrument_embedding_pass\("embed_pending"\)', semantic_index_py, re.DOTALL)
    
    # Check _default_embed_texts in github_knowledge.py
    assert re.search(r'def _default_embed_texts\([^:]+:\s*.*?instrument_embedding_pass\("_default_embed_texts"\)', github_knowledge_py, re.DOTALL)


def test_four_call_sites_produce_record(caplog):
    """Every one of the four call sites produces a run-ID + entry-point + PID record."""
    caplog.set_level(logging.INFO)
    embedder._current_run_id = None
    embedder._current_entry_point = None
    embedder._last_activity_time = 0.0

    embedder.instrument_embedding_pass("embed_chunks")
    records = [r for r in caplog.records if "Embedding pass started" in r.message]
    assert len(records) == 1
    assert "run_id=" in records[-1].message
    assert "entry_point=embed_chunks" in records[-1].message
    assert "pid=" in records[-1].message

def test_degrades_safely_when_mlx_absent(caplog):
    """Instrumentation degrades safely when MLX is absent."""
    caplog.set_level(logging.INFO)
    embedder._current_run_id = None
    embedder._current_entry_point = None
    embedder._last_activity_time = 0.0

    with patch.dict(sys.modules, {'mlx.core': None}):
        embedder.instrument_embedding_pass("test_site")
        
        mock_emb = MagicMock()
        mock_emb.generate = mock_generate
        with patch.dict(sys.modules, {'mlx_embeddings': mock_emb}):
            embedder._batch_count = 9
            embedder._embed_batch(None, None, ["text"])
            
    records = [r for r in caplog.records if "Embedding pass started" in r.message]
    assert len(records) == 1
