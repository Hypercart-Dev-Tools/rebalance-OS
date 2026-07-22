"""Static egress guard (GH-195) — all network/LLM/GitHub calls confined to the
two designated boundary modules.

Only ``classify.py`` (ollama) and ``routes.py`` (gh) may contain egress
primitives. Every other ``three_eyes/*.py`` must be egress-free, so "does this
module talk to the outside world?" is answerable by looking at exactly two files.
The pattern matches quoted argv tokens and ``urlopen(`` — precise enough not to
trip on prose/docstrings that merely mention ``gh`` or ``curl``.
"""

from __future__ import annotations

import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "three_eyes"
EXEMPT = {"classify.py", "routes.py"}

# Quoted argv tokens (e.g. subprocess.run(["gh", ...])) + direct urllib + raw sockets.
FORBIDDEN = re.compile(
    r"""["'](?:gh|curl|wget|nc|ollama)["']"""   # egress binary as an argv literal
    r"""|urlopen\("""                            # direct HTTP
    r"""|/dev/tcp"""                             # raw socket
    r"""|["']push["']"""                         # git push as an argv literal
)


def test_no_egress_outside_the_two_boundary_modules():
    offenders = []
    for path in sorted(PKG.glob("*.py")):
        if path.name in EXEMPT:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if FORBIDDEN.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "egress primitive found outside classify.py/routes.py:\n" + "\n".join(offenders)


def test_classify_is_the_only_ollama_caller():
    text = (PKG / "classify.py").read_text()
    assert "urlopen(" in text and "11434" in text, "classify.py should own the ollama call"


def test_routes_is_the_only_gh_caller():
    text = (PKG / "routes.py").read_text()
    assert re.search(r"""["']gh["']""", text), "routes.py should own the gh call"
