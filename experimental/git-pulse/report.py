#!/usr/bin/env python3
"""Render a static HTML report from a git-pulse combined TSV export."""

from __future__ import annotations

import argparse
import csv
import html
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = [
    "local_day",
    "local_time",
    "utc_time",
    "device_id",
    "device_name",
    "repo",
    "branch",
    "short_sha",
    "subject",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a readable HTML report from a git-pulse TSV export."
    )
    parser.add_argument("input_tsv", help="Path to the combined TSV report.")
    parser.add_argument(
        "--output",
        help="Output HTML path. Defaults to the input path with a .html suffix.",
    )
    parser.add_argument(
        "--title",
        default="Git Pulse Report",
        help="Report title shown in the page header.",
    )
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing:
            missing_text = ", ".join(missing)
            raise SystemExit(f"Missing required TSV columns: {missing_text}")

        rows: list[dict[str, str]] = []
        for index, raw_row in enumerate(reader, start=2):
            row = {column: (raw_row.get(column, "") or "").strip() for column in REQUIRED_COLUMNS}
            if not any(row.values()):
                continue
            row["_line_number"] = str(index)
            row["_search_text"] = " ".join(
                row[column].lower()
                for column in ("repo", "branch", "short_sha", "subject", "device_name", "device_id")
            )
            rows.append(row)

    rows.sort(key=lambda row: (row["local_day"], row["utc_time"], row["local_time"]), reverse=True)
    return rows


def format_day_label(local_day: str) -> str:
    try:
        return datetime.strptime(local_day, "%Y-%m-%d").strftime("%A, %b %d, %Y")
    except ValueError:
        return local_day


def html_text(value: str) -> str:
    return html.escape(value, quote=True)


def slug(value: str) -> str:
    lowered = value.lower()
    out = []
    for char in lowered:
        if char.isalnum():
            out.append(char)
        else:
            out.append("-")
    slugged = "".join(out).strip("-")
    while "--" in slugged:
        slugged = slugged.replace("--", "-")
    return slugged or "unknown"


def build_options(values: Iterable[str], placeholder: str) -> str:
    option_tags = [f'<option value="">{html_text(placeholder)}</option>']
    for value in sorted(set(values), key=lambda item: item.lower()):
        option_tags.append(f'<option value="{html_text(value)}">{html_text(value)}</option>')
    return "\n".join(option_tags)


def build_quick_filters(counts: Counter[str], filter_name: str, limit: int = 6) -> str:
    buttons = []
    for value, count in counts.most_common(limit):
        buttons.append(
            (
                f'<button class="quick-chip" type="button" '
                f'data-filter-name="{html_text(filter_name)}" '
                f'data-filter-value="{html_text(value)}">'
                f"{html_text(value)} <span>{count}</span></button>"
            )
        )
    return "\n".join(buttons)


def build_stat_card(label: str, value: str, accent: str) -> str:
    return (
        f'<article class="stat-card {accent}">'
        f'<div class="stat-label">{html_text(label)}</div>'
        f'<div class="stat-value">{html_text(value)}</div>'
        f"</article>"
    )


def build_bar_rows(counts: Counter[str], empty_label: str, limit: int = 6) -> str:
    if not counts:
        return f'<div class="empty-mini">{html_text(empty_label)}</div>'

    top = counts.most_common(limit)
    peak = top[0][1]
    rows = []
    for value, count in top:
        percent = max(12, round((count / peak) * 100))
        rows.append(
            (
                '<div class="bar-row">'
                f'<div class="bar-label">{html_text(value)}</div>'
                f'<div class="bar-track"><div class="bar-fill" style="width: {percent}%"></div></div>'
                f'<div class="bar-count">{count}</div>'
                "</div>"
            )
        )
    return "\n".join(rows)


def build_day_sections(rows: list[dict[str, str]]) -> str:
    grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["local_day"]].append(row)

    day_sections: list[str] = []
    for local_day in sorted(grouped, reverse=True):
        items = grouped[local_day]
        repo_count = len({row["repo"] for row in items})
        device_count = len({row["device_id"] for row in items})
        sections = [
            (
                f'<section class="day-group" data-day="{html_text(local_day)}">'
                '<header class="day-header">'
                '<div>'
                f'<div class="day-kicker">{html_text(local_day)}</div>'
                f'<h2>{html_text(format_day_label(local_day))}</h2>'
                "</div>"
                '<div class="day-count">'
                f"<strong>{len(items)}</strong> commits"
                f'<span>{repo_count} repos, {device_count} devices</span>'
                "</div>"
                "</header>"
                '<div class="entries">'
            )
        ]

        for row in items:
            repo_class = f"repo-{slug(row['repo'])}"
            entry = (
                f'<article class="entry {repo_class}" '
                f'data-repo="{html_text(row["repo"])}" '
                f'data-branch="{html_text(row["branch"])}" '
                f'data-device="{html_text(row["device_id"])}" '
                f'data-search="{html_text(row["_search_text"])}">'
                '<div class="entry-rail">'
                f'<div class="entry-time">{html_text(row["local_time"])}</div>'
                f'<div class="entry-utc">{html_text(row["utc_time"])}</div>'
                "</div>"
                '<div class="entry-body">'
                f'<div class="entry-subject">{html_text(row["subject"])}</div>'
                '<div class="entry-meta">'
                f'<span class="pill repo-pill">{html_text(row["repo"])}</span>'
                f'<span class="pill branch-pill">{html_text(row["branch"])}</span>'
                f'<span class="pill sha-pill">{html_text(row["short_sha"])}</span>'
                f'<span class="pill device-pill">{html_text(row["device_name"])}</span>'
                "</div>"
                "</div>"
                "</article>"
            )
            sections.append(entry)

        sections.append("</div></section>")
        day_sections.append("\n".join(sections))

    return "\n".join(day_sections)


def render_html(title: str, input_path: Path, rows: list[dict[str, str]]) -> str:
    repo_counts = Counter(row["repo"] for row in rows)
    branch_counts = Counter(row["branch"] for row in rows)
    device_counts = Counter(row["device_name"] for row in rows)
    day_counts = Counter(row["local_day"] for row in rows)

    first_day = min(day_counts) if day_counts else "-"
    last_day = max(day_counts) if day_counts else "-"
    busiest_day = day_counts.most_common(1)[0] if day_counts else ("-", 0)
    top_repo = repo_counts.most_common(1)[0] if repo_counts else ("-", 0)
    top_branch = branch_counts.most_common(1)[0] if branch_counts else ("-", 0)

    stat_cards = "\n".join(
        [
            build_stat_card("Commits", str(len(rows)), "accent-sand"),
            build_stat_card("Active days", str(len(day_counts)), "accent-rose"),
            build_stat_card("Repos", str(len(repo_counts)), "accent-mint"),
            build_stat_card("Devices", str(len(device_counts)), "accent-ink"),
        ]
    )

    summary_bars = "\n".join(
        [
            '<section class="summary-panel">',
            "<h3>Repo mix</h3>",
            build_bar_rows(repo_counts, "No repos in this report."),
            "</section>",
            '<section class="summary-panel">',
            "<h3>Branch mix</h3>",
            build_bar_rows(branch_counts, "No branches in this report."),
            "</section>",
        ]
    )

    empty_state = ""
    if not rows:
        empty_state = (
            '<section class="empty-state">'
            "<h2>No rows found</h2>"
            "<p>The TSV parsed correctly, but there were no commit rows to render.</p>"
            "</section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_text(title)}</title>
  <style>
    :root {{
      --bg: #f5efe4;
      --bg-deep: #d7c0a2;
      --panel: rgba(255, 251, 245, 0.88);
      --panel-strong: #fffdf8;
      --ink: #182028;
      --muted: #58606a;
      --line: rgba(24, 32, 40, 0.12);
      --shadow: 0 20px 60px rgba(61, 45, 27, 0.14);
      --sand: #c77d4a;
      --rose: #a64b5f;
      --mint: #1d7b6f;
      --ink-accent: #29435c;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(199, 125, 74, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(29, 123, 111, 0.14), transparent 24%),
        linear-gradient(180deg, #f6f1e8 0%, var(--bg) 45%, #efe5d7 100%);
    }}

    .shell {{
      width: min(1240px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 32px 0 64px;
    }}

    .hero {{
      position: relative;
      overflow: hidden;
      padding: 32px;
      border: 1px solid rgba(255, 255, 255, 0.6);
      border-radius: 28px;
      background:
        linear-gradient(135deg, rgba(255, 248, 240, 0.94), rgba(250, 244, 234, 0.86)),
        linear-gradient(45deg, rgba(199, 125, 74, 0.04), rgba(41, 67, 92, 0.06));
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }}

    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -80px -80px auto;
      width: 220px;
      height: 220px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(199, 125, 74, 0.18), transparent 70%);
      pointer-events: none;
    }}

    .eyebrow {{
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--rose);
    }}

    h1, h2, h3 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      line-height: 1.05;
    }}

    h1 {{
      margin-top: 10px;
      font-size: clamp(2.4rem, 5vw, 4.4rem);
      letter-spacing: -0.04em;
    }}

    .hero-copy {{
      max-width: 880px;
      margin-top: 14px;
      font-size: 1.02rem;
      line-height: 1.6;
      color: var(--muted);
    }}

    .hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 18px;
      margin-top: 18px;
      color: var(--muted);
      font-size: 0.96rem;
    }}

    .hero-meta strong {{
      color: var(--ink);
    }}

    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 24px;
    }}

    .stat-card {{
      padding: 18px 18px 16px;
      border-radius: 22px;
      border: 1px solid rgba(24, 32, 40, 0.08);
      background: rgba(255, 253, 249, 0.86);
    }}

    .stat-card.accent-sand {{
      box-shadow: inset 0 0 0 1px rgba(199, 125, 74, 0.18);
    }}

    .stat-card.accent-rose {{
      box-shadow: inset 0 0 0 1px rgba(166, 75, 95, 0.18);
    }}

    .stat-card.accent-mint {{
      box-shadow: inset 0 0 0 1px rgba(29, 123, 111, 0.2);
    }}

    .stat-card.accent-ink {{
      box-shadow: inset 0 0 0 1px rgba(41, 67, 92, 0.18);
    }}

    .stat-label {{
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--muted);
    }}

    .stat-value {{
      margin-top: 8px;
      font-size: clamp(1.6rem, 3vw, 2.5rem);
      font-weight: 800;
      letter-spacing: -0.04em;
    }}

    .controls {{
      position: sticky;
      top: 0;
      z-index: 10;
      margin-top: 22px;
      padding: 18px;
      border-radius: 24px;
      border: 1px solid rgba(24, 32, 40, 0.08);
      background: rgba(255, 252, 246, 0.92);
      box-shadow: 0 12px 34px rgba(61, 45, 27, 0.12);
      backdrop-filter: blur(12px);
    }}

    .control-grid {{
      display: grid;
      grid-template-columns: 2fr repeat(3, minmax(0, 1fr)) auto;
      gap: 12px;
      align-items: end;
    }}

    label {{
      display: block;
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
      margin-bottom: 6px;
    }}

    input,
    select,
    button {{
      width: 100%;
      min-height: 48px;
      padding: 0 14px;
      border: 1px solid rgba(24, 32, 40, 0.12);
      border-radius: 14px;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.82);
      font: inherit;
    }}

    button {{
      font-weight: 700;
      cursor: pointer;
      background: linear-gradient(135deg, #21405e, #2a5777);
      color: #fffaf2;
    }}

    .quick-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}

    .quick-chip {{
      width: auto;
      min-height: 38px;
      padding: 0 14px;
      border-radius: 999px;
      border: 1px solid rgba(24, 32, 40, 0.1);
      background: rgba(255, 250, 241, 0.92);
      color: var(--ink);
      font-weight: 700;
    }}

    .quick-chip span {{
      color: var(--muted);
    }}

    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-top: 24px;
    }}

    .summary-panel {{
      padding: 22px;
      border-radius: 24px;
      border: 1px solid rgba(24, 32, 40, 0.08);
      background: var(--panel);
      box-shadow: var(--shadow);
    }}

    .summary-panel h3 {{
      font-size: 1.45rem;
      margin-bottom: 14px;
    }}

    .bar-row {{
      display: grid;
      grid-template-columns: minmax(120px, 220px) 1fr auto;
      gap: 12px;
      align-items: center;
      margin-top: 12px;
    }}

    .bar-label,
    .bar-count {{
      font-size: 0.95rem;
    }}

    .bar-label {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .bar-track {{
      height: 12px;
      overflow: hidden;
      border-radius: 999px;
      background: rgba(24, 32, 40, 0.08);
    }}

    .bar-fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--sand), var(--mint));
    }}

    .timeline {{
      margin-top: 24px;
    }}

    .timeline-status {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
      color: var(--muted);
      font-size: 0.95rem;
    }}

    .day-group {{
      margin-top: 18px;
      padding: 20px;
      border-radius: 28px;
      border: 1px solid rgba(24, 32, 40, 0.08);
      background: var(--panel);
      box-shadow: var(--shadow);
    }}

    .day-header {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: end;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--line);
    }}

    .day-kicker {{
      font-size: 0.76rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--rose);
    }}

    .day-header h2 {{
      margin-top: 6px;
      font-size: clamp(1.5rem, 3vw, 2.2rem);
    }}

    .day-count {{
      text-align: right;
      white-space: nowrap;
    }}

    .day-count strong {{
      display: block;
      font-size: 1.75rem;
      letter-spacing: -0.04em;
    }}

    .day-count span {{
      color: var(--muted);
      font-size: 0.92rem;
    }}

    .entries {{
      display: grid;
      gap: 12px;
      margin-top: 16px;
    }}

    .entry {{
      display: grid;
      grid-template-columns: 150px minmax(0, 1fr);
      gap: 16px;
      padding: 16px;
      border-radius: 20px;
      border: 1px solid rgba(24, 32, 40, 0.08);
      background: var(--panel-strong);
    }}

    .entry-rail {{
      padding-right: 14px;
      border-right: 1px solid var(--line);
    }}

    .entry-time {{
      font-weight: 800;
      letter-spacing: -0.02em;
    }}

    .entry-utc {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.86rem;
      word-break: break-word;
    }}

    .entry-subject {{
      font-size: 1.04rem;
      line-height: 1.45;
      font-weight: 700;
    }}

    .entry-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}

    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 0 10px;
      border-radius: 999px;
      border: 1px solid rgba(24, 32, 40, 0.1);
      font-size: 0.82rem;
      font-weight: 700;
      background: rgba(255, 250, 241, 0.9);
    }}

    .repo-pill {{
      background: rgba(199, 125, 74, 0.12);
      color: #7f441d;
    }}

    .branch-pill {{
      background: rgba(41, 67, 92, 0.09);
      color: var(--ink-accent);
    }}

    .sha-pill {{
      background: rgba(24, 32, 40, 0.08);
    }}

    .device-pill {{
      background: rgba(29, 123, 111, 0.1);
      color: #165d55;
    }}

    .empty-state,
    .empty-mini {{
      color: var(--muted);
    }}

    [hidden] {{
      display: none !important;
    }}

    @media (max-width: 960px) {{
      .stats,
      .summary-grid,
      .control-grid {{
        grid-template-columns: 1fr 1fr;
      }}

      .control-grid > div:last-child {{
        grid-column: 1 / -1;
      }}
    }}

    @media (max-width: 720px) {{
      .shell {{
        width: min(100vw - 20px, 1240px);
        padding-top: 18px;
      }}

      .hero,
      .controls,
      .summary-panel,
      .day-group {{
        border-radius: 22px;
      }}

      .stats,
      .summary-grid,
      .control-grid {{
        grid-template-columns: 1fr;
      }}

      .day-header,
      .timeline-status,
      .entry {{
        grid-template-columns: 1fr;
        display: block;
      }}

      .day-count {{
        margin-top: 12px;
        text-align: left;
      }}

      .entry-rail {{
        margin-bottom: 12px;
        padding-right: 0;
        padding-bottom: 12px;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}

      .bar-row {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">Static HTML export</div>
      <h1>{html_text(title)}</h1>
      <div class="hero-copy">
        Easier to scan than the raw TSV: day-grouped timeline, commit summaries, and instant browser-side filtering across repos, branches, devices, SHAs, and subjects.
      </div>
      <div class="hero-meta">
        <div><strong>Source:</strong> {html_text(input_path.name)}</div>
        <div><strong>Range:</strong> {html_text(first_day)} to {html_text(last_day)}</div>
        <div><strong>Top repo:</strong> {html_text(top_repo[0])} ({top_repo[1]})</div>
        <div><strong>Top branch:</strong> {html_text(top_branch[0])} ({top_branch[1]})</div>
        <div><strong>Busiest day:</strong> {html_text(busiest_day[0])} ({busiest_day[1]})</div>
      </div>
      <div class="stats">
        {stat_cards}
      </div>
    </section>

    <section class="controls">
      <div class="control-grid">
        <div>
          <label for="search">Search the work</label>
          <input id="search" type="search" placeholder="subject, repo, branch, sha, device">
        </div>
        <div>
          <label for="repoFilter">Repo</label>
          <select id="repoFilter">
            {build_options(repo_counts.keys(), "All repos")}
          </select>
        </div>
        <div>
          <label for="branchFilter">Branch</label>
          <select id="branchFilter">
            {build_options(branch_counts.keys(), "All branches")}
          </select>
        </div>
        <div>
          <label for="deviceFilter">Device</label>
          <select id="deviceFilter">
            {build_options(device_counts.keys(), "All devices")}
          </select>
        </div>
        <div>
          <label for="clearFilters">Reset</label>
          <button id="clearFilters" type="button">Clear filters</button>
        </div>
      </div>

      <div class="quick-row">
        {build_quick_filters(repo_counts, "repo")}
      </div>
    </section>

    <div class="summary-grid">
      {summary_bars}
    </div>

    <section class="timeline">
      <div class="timeline-status">
        <div id="visibleSummary">{len(rows)} commits shown</div>
        <div>{len(day_counts)} day groups</div>
      </div>
      {empty_state}
      {build_day_sections(rows)}
    </section>
  </div>

  <script>
    const searchEl = document.getElementById("search");
    const repoEl = document.getElementById("repoFilter");
    const branchEl = document.getElementById("branchFilter");
    const deviceEl = document.getElementById("deviceFilter");
    const clearEl = document.getElementById("clearFilters");
    const visibleSummaryEl = document.getElementById("visibleSummary");
    const dayGroups = Array.from(document.querySelectorAll(".day-group"));
    const quickChips = Array.from(document.querySelectorAll(".quick-chip"));

    function applyFilters() {{
      const search = searchEl.value.trim().toLowerCase();
      const repo = repoEl.value;
      const branch = branchEl.value;
      const device = deviceEl.value;

      let visibleEntries = 0;
      let visibleDays = 0;

      for (const dayGroup of dayGroups) {{
        const entries = Array.from(dayGroup.querySelectorAll(".entry"));
        let dayVisible = 0;

        for (const entry of entries) {{
          const matches =
            (!search || entry.dataset.search.includes(search)) &&
            (!repo || entry.dataset.repo === repo) &&
            (!branch || entry.dataset.branch === branch) &&
            (!device || entry.dataset.device === device);

          entry.hidden = !matches;
          if (matches) {{
            dayVisible += 1;
            visibleEntries += 1;
          }}
        }}

        dayGroup.hidden = dayVisible === 0;
        if (dayVisible > 0) {{
          visibleDays += 1;
        }}
      }}

      visibleSummaryEl.textContent = `${{visibleEntries}} commits shown across ${{visibleDays}} day groups`;
    }}

    for (const element of [searchEl, repoEl, branchEl, deviceEl]) {{
      element.addEventListener("input", applyFilters);
      element.addEventListener("change", applyFilters);
    }}

    clearEl.addEventListener("click", () => {{
      searchEl.value = "";
      repoEl.value = "";
      branchEl.value = "";
      deviceEl.value = "";
      applyFilters();
    }});

    for (const chip of quickChips) {{
      chip.addEventListener("click", () => {{
        const target = chip.dataset.filterName;
        const value = chip.dataset.filterValue;
        if (target === "repo") {{
          repoEl.value = value;
          applyFilters();
        }}
      }});
    }}

    applyFilters();
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_tsv).expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"Input TSV not found: {input_path}")

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_path.with_suffix(".html")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = read_rows(input_path)
    output_path.write_text(render_html(args.title, input_path, rows), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
