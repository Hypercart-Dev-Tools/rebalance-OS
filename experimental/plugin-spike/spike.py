"""Phase 0 spike for P2-PLUGIN-SOURCE-MODULES.

Throwaway. Proves (or disproves) the three seams the plugin architecture rests
on, independently, before any real build:

  Seam 1 — Discovery: an out-of-tree package advertised via the
           `rebalance.sources` entry-point group is found, loaded, registered
           into a registry, and dispatched — with no core import-by-name.
  Seam 2 — linkding API: a paginated `{count,next,previous,results}` client
           walks `next` to completion and maps bookmark rows to the
           SemanticDoc shape. Driven from fixtures (no live token here).
  Seam 3 — Vector round-trip: linkding docs go through the REAL semantic
           tables (upsert -> embed -> vec0 KNN search) using the injectable
           embedder seam, since the mlx model can't load off Apple Silicon.
           Also probes exactly where the current orchestration blocks a new
           source_type.

Run:  PYTHONPATH=src python3 experimental/plugin-spike/spike.py
"""

from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
from importlib.metadata import entry_points
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures" / "linkding"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Seam 1 — entry-point discovery + dispatch
# ---------------------------------------------------------------------------
def seam_discovery() -> None:
    print("\n=== Seam 1: entry-point discovery ===")
    eps = entry_points(group="rebalance.sources")
    names = sorted(ep.name for ep in eps)
    check("discovery.group_visible", "dummy" in names,
          f"entry_points(group='rebalance.sources') -> {names}")
    if "dummy" not in names:
        return

    # A registry that knows NOTHING about the dummy package statically.
    registry: dict[str, object] = {}
    for ep in eps:
        mod = ep.load()              # imports the plugin lazily, by entry point only
        registry[mod.name] = mod
    check("discovery.registered", "dummy" in registry,
          f"registry keys after load -> {sorted(registry)}")

    # Dispatch exactly like refresh_index would: look up by scope, call refresh.
    out = registry["dummy"].refresh(db_path="/tmp/x", dry_run=True, since_days=7)
    check("discovery.dispatched", out.get("discovered") is True, json.dumps(out))


# ---------------------------------------------------------------------------
# Seam 2 — linkding paginated client (over fixtures) + SemanticDoc mapping
# ---------------------------------------------------------------------------
def _page_loader():
    """Return a fake transport that serves the two fixture pages in order,
    keyed by whether the request carries an offset (page 2) or not (page 1)."""
    page1 = json.loads((FIXTURES / "bookmarks_page1.json").read_text())
    page2 = json.loads((FIXTURES / "bookmarks_page2.json").read_text())

    def get(url: str) -> dict:
        return page2 if "offset=2" in url else page1
    return get


def paginate(get, base_url: str) -> list[dict]:
    """Walk {count,next,previous,results} until next is None."""
    url = f"{base_url}/api/bookmarks/?limit=2"
    rows: list[dict] = []
    guard = 0
    while url and guard < 50:
        payload = get(url)
        rows.extend(payload["results"])
        url = payload.get("next")
        guard += 1
    return rows


def bookmark_to_semantic_doc(b: dict) -> dict:
    """The proposed linkding -> SemanticDoc mapping (no schema change)."""
    title = b.get("title") or b.get("website_title") or b["url"]
    body = "\n".join(p for p in (b.get("title"), b.get("description"), b.get("notes")) if p).strip()
    return {
        "source_type": "linkding",
        "source_table": "linkding_bookmarks",
        "source_pk": str(b["id"]),
        "doc_kind": "bookmark",
        "title": title,
        "body": body,
        "metadata": {
            "url": b["url"],
            "tag_names": b.get("tag_names", []),
            "is_archived": bool(b.get("is_archived")),
            "unread": bool(b.get("unread")),
            "date_added": b.get("date_added"),
        },
        "created_at": b.get("date_added"),
        "updated_at": b.get("date_modified") or b.get("date_added"),
    }


def seam_linkding(docs_out: list[dict]) -> None:
    print("\n=== Seam 2: linkding paginated client + mapping ===")
    get = _page_loader()
    rows = paginate(get, "https://links.example.com")
    check("linkding.pagination", len(rows) == 3,
          f"walked next-> got {len(rows)} bookmarks (expected count=3)")
    ids = [r["id"] for r in rows]
    check("linkding.order_preserved", ids == [101, 102, 103], f"ids={ids}")

    docs = [bookmark_to_semantic_doc(r) for r in rows]
    docs_out.extend(docs)
    sample = docs[0]
    body_ok = "sqlite-vec" in sample["body"] and "\n" in sample["body"]
    check("linkding.semanticdoc_body", body_ok,
          f"doc[101].body[:60]={sample['body'][:60]!r}")
    meta_ok = sample["metadata"]["tag_names"] == ["database", "embeddings", "sqlite"]
    check("linkding.semanticdoc_meta", meta_ok, f"meta={sample['metadata']}")


# ---------------------------------------------------------------------------
# Seam 3 — real semantic tables: upsert -> embed -> vec0 KNN
# ---------------------------------------------------------------------------
def _fake_embed(text: str, dim: int) -> list[float]:
    """Deterministic bag-of-tokens hash embedding -> unit vector.

    Stands in for the mlx Qwen3 model (which can't load on Linux). Good enough
    to prove vec0 MATCH ranking puts a query next to the bookmark it overlaps.
    """
    vec = [0.0] * dim
    for tok in text.lower().split():
        h = hash(tok) % dim
        vec[h] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def seam_vector(docs: list[dict]) -> None:
    print("\n=== Seam 3: vector round-trip through real semantic tables ===")
    try:
        from rebalance.ingest.db import db_connection, ensure_semantic_schema
        from rebalance.ingest.db import semantic as sem
        from rebalance.ingest.embedder import EMBEDDING_DIM, _vec_to_bytes
        from rebalance.ingest import semantic_index as si
        from rebalance.ingest.semantic_index import upsert_document
    except Exception as e:  # pragma: no cover
        check("vector.imports", False, f"import failed: {e}")
        return
    check("vector.imports", True, f"EMBEDDING_DIM={EMBEDDING_DIM}")

    # Finding probe: does the table accept a brand-new source_type with NO core edit,
    # but does the ORCHESTRATION (_normalize_sources) reject it?
    try:
        si._normalize_sources(["linkding"])
        normalize_blocks = False
    except ValueError as e:
        normalize_blocks = True
        norm_err = str(e)
    check("vector.normalize_rejects_new_source", normalize_blocks,
          "si._normalize_sources(['linkding']) raises -> confirms Phase 1 cut point"
          + (f": {norm_err}" if normalize_blocks else ""))

    db_path = Path(tempfile.mkdtemp()) / "spike.db"
    try:
        with db_connection(db_path, ensure_semantic_schema) as conn:
            # vec0 must actually be loaded for this to work at all.
            try:
                conn.execute("SELECT count(*) FROM semantic_embeddings").fetchone()
                vec_ok = True
            except Exception as e:
                vec_ok = False
                vec_err = str(e)
            check("vector.vec0_loaded", vec_ok,
                  "semantic_embeddings (vec0) queryable" if vec_ok else f"{vec_err}")
            if not vec_ok:
                return

            # 1) upsert linkding docs into semantic_documents — NO edit to upsert_document.
            states = []
            for d in docs:
                _, state = upsert_document(
                    conn,
                    source_type=d["source_type"], source_table=d["source_table"],
                    source_pk=d["source_pk"], doc_kind=d["doc_kind"],
                    title=d["title"], body=d["body"], metadata=d["metadata"],
                    created_at=d["created_at"], updated_at=d["updated_at"],
                )
                states.append(state)
            conn.commit()
            n = conn.execute(
                "SELECT COUNT(*) FROM semantic_documents WHERE source_type='linkding'"
            ).fetchone()[0]
            check("vector.upsert_new_source", n == 3 and states == ["inserted"] * 3,
                  f"{n} linkding docs inserted, states={states}")

            # 2) idempotency: re-upsert unchanged -> all 'unchanged'
            states2 = [
                upsert_document(
                    conn, source_type=d["source_type"], source_table=d["source_table"],
                    source_pk=d["source_pk"], doc_kind=d["doc_kind"], title=d["title"],
                    body=d["body"], metadata=d["metadata"], created_at=d["created_at"],
                    updated_at=d["updated_at"],
                )[1]
                for d in docs
            ]
            check("vector.upsert_idempotent", states2 == ["unchanged"] * 3, f"states={states2}")

            # 3) embed via the injectable seam (bypassing _normalize_sources, which blocks).
            model_version = f"spike-fake|{EMBEDDING_DIM}"
            pending = sem.semantic_documents_pending_embed(conn, ["linkding"], 1, model_version)
            for row in pending:
                vec = _fake_embed(row["body"], EMBEDDING_DIM)
                sem.delete_semantic_embedding(conn, row["id"])
                sem.insert_semantic_embedding(conn, row["id"], _vec_to_bytes(vec))
                sem.mark_semantic_document_embedded(conn, row["id"], model_version, "2026-06-06T00:00:00Z")
            conn.commit()
            embedded = conn.execute("SELECT COUNT(*) FROM semantic_embeddings").fetchone()[0]
            check("vector.embed_roundtrip", embedded == 3, f"{embedded} vectors stored")

            # 4) KNN search scoped to source_type='linkding' — the dashboard/ask read path.
            qvec = _vec_to_bytes(_fake_embed("vector search sqlite extension embeddings", EMBEDDING_DIM))
            hits = sem.search_semantic_documents(conn, qvec, 3, ["linkding"])
            top = hits[0] if hits else None
            top_pk = top["source_pk"] if top else None
            check("vector.knn_search", top_pk == "101",
                  f"top hit source_pk={top_pk} (expected 101 = sqlite-vec bookmark); "
                  f"returned {len(hits)} hits")
    finally:
        try:
            db_path.unlink()
        except Exception:
            pass


def main() -> int:
    sys.path.insert(0, str(REPO / "src"))
    seam_discovery()
    docs: list[dict] = []
    seam_linkding(docs)
    seam_vector(docs)

    print("\n=== SUMMARY ===")
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, _ in results:
        print(f"  {'✓' if ok else '✗'} {name}")
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
