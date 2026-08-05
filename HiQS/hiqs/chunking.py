"""One chunk-size cap, shared by every source that emits documents.

§6.3 specifies a truncation gate — "≥95% of chunks fit the shipped model's context
(256 word-pieces for MiniLM)" — and the gate had never been run. When it finally was, the
corpus scored 64.0%: MiniLM was silently truncating a third of every note past its 256-token
window, and the tail was never embedded at all. That is anti-pattern B in its purest form,
trusting a measurement (139 green tests, a full docs_vec table) that was measuring the wrong
thing. Nothing failed. The index just quietly held less than it claimed.

The same unbounded chunk is why Qwen3-Embedding-0.6B OOM'd twice: its context is 32768, so it
truncates nothing and instead ran attention over a 6893-token sequence. Bounding the chunk
bounds both — the truncation loss and the memory.

Why this lives in its own module rather than in ``vault.py``, where the plan's remedy put it:
the measured fit rate was 77.5% for vault and **11.7% for github**, which emits an entire issue
body as one document. A cap in vault.py alone would have left the corpus-wide gate failing at
78% while looking like the fix had landed. The cap belongs at the seam every source shares, so
a source added later inherits it instead of re-learning this (L23, anti-pattern C).

The cap is in characters, not tokens, on purpose: a source plugin must not import the embedding
model to decide how to split a note (PORTABLE). Characters do not map cleanly onto word-pieces
— the measured ratio across this corpus ranges from 1.69 to 4.06 chars/token — so the cap was
not derived analytically. It was chosen by running the real gate over the real corpus for each
candidate value:

    cap  500 -> 99.8% fit    cap  800 -> 88.1% FAIL
    cap  600 -> 96.9% fit    cap  900 -> 82.8% FAIL
    cap  700 -> 93.2% FAIL   no cap   -> 77.5% FAIL   (vault only; corpus-wide 64.0%)

600 is the largest cap that clears 95%, and larger chunks retrieve better than smaller ones, so
600 it is. Corpus-wide that yields 98.2% fit and a maximum sequence of 350 tokens. The margin
over the 95% gate is only ~3 points, which is exactly why the gate is now executable rather
than a sentence in a plan: if the corpus drifts denser, it must fail loudly (§8), not silently
truncate the way it just did for the entire life of this index.
"""

from __future__ import annotations

MAX_CHUNK_CHARS = 600


def split_oversized(body: str, cap: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split ``body`` into parts of at most ``cap`` characters.

    Splits at the coarsest boundary that fits — paragraphs first, then lines, and only as a
    last resort mid-line — so a part stays a readable unit of prose rather than an arbitrary
    slice. Bodies already within the cap are returned unchanged and un-split, which keeps the
    common case (p50 is 511 characters) identical to what it was before the cap existed.

    There is deliberately no overlap between parts. Overlap would hedge against a sentence
    straddling a boundary, but it also puts the same text in the index twice, and duplicate
    text is what makes a ranked list look confident about one note repeated three times.
    Splitting on paragraph boundaries already keeps most semantic units intact.
    """
    if cap < 1:
        raise ValueError("chunk cap must be at least 1 character")
    if len(body) <= cap:
        return [body]

    parts: list[str] = []
    for block in _pack(body.split("\n\n"), "\n\n", cap):
        if len(block) <= cap:
            parts.append(block)
            continue
        for line_block in _pack(block.split("\n"), "\n", cap):
            if len(line_block) <= cap:
                parts.append(line_block)
            else:
                # A single line longer than the cap — a table row, a minified blob, a URL
                # wall. Nothing structural left to split on, so cut it.
                parts.extend(line_block[i : i + cap] for i in range(0, len(line_block), cap))

    stripped = [part for part in (part.strip() for part in parts) if part]
    # A body that is entirely whitespace past the cap would otherwise vanish silently; return
    # the original rather than dropping a document on the floor.
    return stripped or [body[:cap]]


def _pack(pieces: list[str], joiner: str, cap: int) -> list[str]:
    """Greedily group ``pieces`` into runs no longer than ``cap``, never splitting a piece.

    A piece longer than the cap on its own is emitted alone and oversized; the caller is
    responsible for splitting it at a finer boundary.
    """
    packed: list[str] = []
    current: list[str] = []
    size = 0
    for piece in pieces:
        addition = len(piece) + (len(joiner) if current else 0)
        if current and size + addition > cap:
            packed.append(joiner.join(current))
            current, size = [piece], len(piece)
        else:
            current.append(piece)
            size += addition
    if current:
        packed.append(joiner.join(current))
    return packed
