"""Static egress guard (GH-195) — all network/LLM/GitHub calls confined to the
two designated boundary modules.

Only ``classify.py`` (ollama) and ``routes.py`` (gh) may contain egress
primitives. Every other ``three_eyes/*.py`` must be egress-free, so "does this
module talk to the outside world?" is answerable by looking at exactly two files.
The pattern matches quoted argv tokens and ``urlopen(`` — precise enough not to
trip on prose/docstrings that merely mention ``gh`` or ``curl``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "three_eyes"
EXEMPT = {"classify.py", "routes.py"}

#: Network-capable stdlib/3rd-party module roots. Importing any of these outside
#: the two boundary modules is a potential hidden egress path (GH-195 review B5).
NETWORK_IMPORTS = {
    "socket", "ssl", "http", "urllib", "ftplib", "smtplib", "telnetlib",
    "poplib", "imaplib", "requests", "httpx", "aiohttp", "asyncio",
}

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


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_network_imports_outside_boundary_modules():
    """AST check: no network-capable module is imported outside classify/routes.

    Complements the regex guard — it catches an egress path that imports
    `socket`/`http.client`/`requests` etc. without a quoted-argv token the regex
    would see (GH-195 review B5).
    """
    offenders = []
    for path in sorted(PKG.glob("*.py")):
        if path.name in EXEMPT:
            continue
        tree = ast.parse(path.read_text())
        bad = _import_roots(tree) & NETWORK_IMPORTS
        if bad:
            offenders.append(f"{path.name}: imports {sorted(bad)}")
    assert not offenders, "network import outside classify.py/routes.py:\n" + "\n".join(offenders)


def test_no_os_system_anywhere():
    """`os.system`/`os.popen` shell out to a string — forbidden everywhere in the package."""
    offenders = []
    for path in sorted(PKG.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os" and node.func.attr in ("system", "popen")):
                offenders.append(f"{path.name}:{node.lineno}: os.{node.func.attr}")
    assert not offenders, "os.system/os.popen found:\n" + "\n".join(offenders)


def test_classify_is_the_only_ollama_caller():
    text = (PKG / "classify.py").read_text()
    assert "urlopen(" in text and "11434" in text, "classify.py should own the ollama call"


def test_routes_is_the_only_gh_caller():
    text = (PKG / "routes.py").read_text()
    assert re.search(r"""["']gh["']""", text), "routes.py should own the gh call"
