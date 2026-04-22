#!/usr/bin/env python3
"""Mechanical validator for filled-in git-pulse recap prose.

Runs regex and length-cap checks against the TLDR, FOCUS, and OBSERVATIONS
sections of a recap file. Violations are flagged with the specific rule and
the offending fragment. Exit code is 0 if clean, 1 if any violations, 2 on
parse errors.

Each rule is a small named function so individual rules can be disabled via
`--disable <rule_name>` if one turns out to be too strict in practice.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


# -------- regex primitives --------

SHA_TOKEN_RE = re.compile(r"\b[a-f0-9]{7,40}\b")
BACKTICK_SPAN_RE = re.compile(r"`([^`\n]+)`")
CONV_COMMIT_RE = re.compile(
    r"\b(feat|fix|chore|docs|refactor|test|perf|style|build|ci)"
    r"(\([^)]+\))?:",
    re.IGNORECASE,
)
FILENAME_RE = re.compile(
    r"\b[\w-]+\.(md|py|js|ts|tsx|jsx|json|yaml|yml|toml|sh|php|sql|html|css|tsv|csv)\b",
    re.IGNORECASE,
)
ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Violation:
    rule: str
    fragment: str
    message: str


def _truncate(text: str, limit: int = 80) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _count_sentences(text: str) -> int:
    text = text.strip()
    if not text:
        return 0
    return sum(1 for part in SENTENCE_SPLIT_RE.split(text) if part.strip())


def _fragment_is_inside_backticks(text: str, start: int, end: int) -> bool:
    for bt in BACKTICK_SPAN_RE.finditer(text):
        if bt.start() < start and end <= bt.end():
            return True
    return False


# -------- content rules (apply to all section types) --------

def check_sha_tokens(text: str) -> list[Violation]:
    """Flag bare SHA-like tokens. Skips matches inside backticks (the
    backtick rule covers those so violations aren't double-counted)."""
    violations: list[Violation] = []
    for m in SHA_TOKEN_RE.finditer(text):
        if _fragment_is_inside_backticks(text, m.start(), m.end()):
            continue
        violations.append(
            Violation(
                rule="sha_token",
                fragment=m.group(),
                message=(
                    f"Contains SHA-like token '{m.group()}'. "
                    "Describe the theme instead of naming specific commits."
                ),
            )
        )
    return violations


def check_backticks_wrap_sha_or_filename(text: str) -> list[Violation]:
    """Flag backticks that wrap SHA-like or filename-like content. Bare
    backticks (e.g. around repo names or branches) are allowed — the skills
    themselves use them that way."""
    violations: list[Violation] = []
    for m in BACKTICK_SPAN_RE.finditer(text):
        inner = m.group(1)
        if SHA_TOKEN_RE.search(inner):
            violations.append(
                Violation(
                    rule="backtick_sha",
                    fragment=m.group(),
                    message=(
                        f"Backticks wrap a SHA-like token: {m.group()}. "
                        "Remove the reference to the specific commit."
                    ),
                )
            )
        elif FILENAME_RE.search(inner):
            violations.append(
                Violation(
                    rule="backtick_filename",
                    fragment=m.group(),
                    message=(
                        f"Backticks wrap a filename: {m.group()}. "
                        "Refer to the subsystem or theme, not the file."
                    ),
                )
            )
    return violations


def check_conv_commit_prefix(text: str) -> list[Violation]:
    """Flag conventional-commit prefixes (e.g. `feat:`, `fix(scope):`)."""
    violations: list[Violation] = []
    for m in CONV_COMMIT_RE.finditer(text):
        violations.append(
            Violation(
                rule="conv_commit_prefix",
                fragment=m.group(),
                message=(
                    f"Contains conventional-commit prefix '{m.group()}'. "
                    "Describe the theme, not the commit type."
                ),
            )
        )
    return violations


def check_filename_token(text: str) -> list[Violation]:
    """Flag bare filenames like `config.yaml` in prose."""
    violations: list[Violation] = []
    for m in FILENAME_RE.finditer(text):
        violations.append(
            Violation(
                rule="filename",
                fragment=m.group(),
                message=(
                    f"Contains filename '{m.group()}'. "
                    "Refer to the subsystem or theme, not the file."
                ),
            )
        )
    return violations


def check_iso_date(text: str) -> list[Violation]:
    """Flag ISO dates (YYYY-MM-DD). Dates belong in the Appendix."""
    violations: list[Violation] = []
    for m in ISO_DATE_RE.finditer(text):
        violations.append(
            Violation(
                rule="iso_date",
                fragment=m.group(),
                message=(
                    f"Contains ISO date '{m.group()}'. "
                    "Dates belong in the Appendix; prose should describe shape and tempo."
                ),
            )
        )
    return violations


CONTENT_RULES = [
    check_sha_tokens,
    check_backticks_wrap_sha_or_filename,
    check_conv_commit_prefix,
    check_filename_token,
    check_iso_date,
]


# -------- length-cap rules (per section type) --------

def check_tldr_length(text: str) -> list[Violation]:
    n = _count_sentences(text)
    if n > 2:
        return [
            Violation(
                rule="tldr_length",
                fragment=_truncate(text),
                message=f"TLDR is {n} sentences; max 2. Compress.",
            )
        ]
    return []


def check_focus_length(text: str) -> list[Violation]:
    n = _count_sentences(text)
    if n > 3:
        return [
            Violation(
                rule="focus_length",
                fragment=_truncate(text),
                message=f"FOCUS is {n} sentences; max 3. Compress.",
            )
        ]
    return []


def check_observations_length(text: str) -> list[Violation]:
    bullets = [line for line in text.split("\n") if line.lstrip().startswith("-")]
    violations: list[Violation] = []
    if len(bullets) > 5:
        violations.append(
            Violation(
                rule="observations_bullets",
                fragment=f"{len(bullets)} bullets",
                message=f"OBSERVATIONS has {len(bullets)} bullets; max 5.",
            )
        )
    for i, bullet in enumerate(bullets, start=1):
        content = bullet.lstrip().lstrip("-").strip()
        n = _count_sentences(content)
        if n > 2:
            violations.append(
                Violation(
                    rule="observations_bullet_length",
                    fragment=_truncate(bullet),
                    message=f"OBSERVATIONS bullet #{i} is {n} sentences; max 2.",
                )
            )
    return violations


LENGTH_RULES = {
    "tldr": [check_tldr_length],
    "focus": [check_focus_length],
    "observations": [check_observations_length],
}


def validate_section(
    text: str,
    section_type: str,
    disabled_rules: set[str] | None = None,
) -> list[Violation]:
    """Run all applicable rules against text. section_type ∈ {tldr, focus, observations}."""
    disabled_rules = disabled_rules or set()
    violations: list[Violation] = []
    for rule in CONTENT_RULES:
        violations.extend(rule(text))
    for rule in LENGTH_RULES.get(section_type, []):
        violations.extend(rule(text))
    return [v for v in violations if v.rule not in disabled_rules]


# -------- recap file parsing --------

TLDR_PLACEHOLDER_RE = re.compile(r"<!--\s*TLDR:", re.IGNORECASE)
FOCUS_PLACEHOLDER_RE = re.compile(r"<!--\s*FOCUS:", re.IGNORECASE)
OBSERVATIONS_PLACEHOLDER_RE = re.compile(r"<!--\s*OBSERVATIONS:", re.IGNORECASE)

SUMMARY_BLOCK_RE = re.compile(
    r"## Summary\s*\n(?:-[^\n]*\n)+\s*\n(?P<body>.*?)\n## By Repo",
    re.DOTALL,
)
FOCUS_BLOCK_RE = re.compile(
    r"### `(?P<repo>[^`]+)` — [^\n]*\n\n"
    r"(?:- [^\n]+\n)+\s*\n"
    r"(?P<body>.*?)"
    r"\n\*\*Commit themes:\*\*",
    re.DOTALL,
)
OBSERVATIONS_BLOCK_RE = re.compile(
    r"## Observations\s*\n+(?P<body>.*?)\n## Appendix",
    re.DOTALL,
)


def extract_sections(recap_text: str) -> dict[str, list[tuple[str, str]]]:
    """Return filled sections keyed by type. Sections that still contain
    placeholder markers are treated as unfilled and skipped."""
    result: dict[str, list[tuple[str, str]]] = {
        "tldr": [],
        "focus": [],
        "observations": [],
    }

    m = SUMMARY_BLOCK_RE.search(recap_text)
    if m:
        body = m.group("body").strip()
        if body and not TLDR_PLACEHOLDER_RE.search(body):
            result["tldr"].append(("TLDR", body))

    for fm in FOCUS_BLOCK_RE.finditer(recap_text):
        body = fm.group("body").strip()
        repo = fm.group("repo")
        if body and not FOCUS_PLACEHOLDER_RE.search(body):
            result["focus"].append((f"FOCUS:{repo}", body))

    om = OBSERVATIONS_BLOCK_RE.search(recap_text)
    if om:
        body = om.group("body").strip()
        if body and not OBSERVATIONS_PLACEHOLDER_RE.search(body):
            result["observations"].append(("OBSERVATIONS", body))

    return result


# -------- CLI --------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate filled-in TLDR/FOCUS/OBSERVATIONS sections of a "
            "git-pulse recap. Exits non-zero if any rule violations are "
            "found so the output is not committed silently."
        )
    )
    parser.add_argument(
        "recap",
        help="Path to a filled recap markdown file.",
    )
    parser.add_argument(
        "--disable",
        action="append",
        default=[],
        metavar="RULE",
        help=(
            "Disable an individual rule by name (repeatable). Rules: "
            "sha_token, backtick_sha, backtick_filename, conv_commit_prefix, "
            "filename, iso_date, tldr_length, focus_length, "
            "observations_bullets, observations_bullet_length."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the 'All sections pass.' line on clean runs.",
    )
    args = parser.parse_args()

    path = Path(args.recap).expanduser()
    if not path.is_file():
        print(f"recap not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text()
    sections = extract_sections(text)

    if not any(sections.values()):
        print(
            f"No filled sections found in {path} (placeholders still present?)",
            file=sys.stderr,
        )
        return 2

    disabled = set(args.disable)
    total_violations = 0

    for section_type, items in sections.items():
        for label, content in items:
            violations = validate_section(content, section_type, disabled)
            if not violations:
                continue
            total_violations += len(violations)
            print(f"## {label}")
            for v in violations:
                print(f"  [{v.rule}] {v.message}")
                print(f"      fragment: {v.fragment!r}")
            print()

    if total_violations:
        plural = "s" if total_violations != 1 else ""
        print(
            f"VIOLATIONS: {total_violations} violation{plural} across "
            f"{sum(len(v) for v in sections.values())} filled section(s)",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        print(f"All {sum(len(v) for v in sections.values())} filled sections pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
