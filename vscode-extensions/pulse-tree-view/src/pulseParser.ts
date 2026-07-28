/**
 * Parser for rebalance-OS's rendered "pulse" markdown file (written by
 * `src/rebalance/ingest/pulse.py::render_pulse_markdown()` / the hourly
 * `pulse-sync` job — typically named `live-pulse.md` inside a configured
 * `git-pulse-sync` clone).
 *
 * This is deliberately free of any `vscode` import so it can be unit
 * tested with a plain Node test runner, independent of the VS Code
 * extension host.
 *
 * Real section headings this parser keys off (confirmed against
 * `render_pulse_markdown()`):
 *   ## Current Day
 *     ### What I've been working on
 *     ### Watched repos (external activity)
 *     ### Upcoming Meetings
 *     ### GitHub Issues assigned to me (last 7 days)
 *     ### Sleuth (Slack) reminders assigned to/by me
 *   ## Yesterday
 *     ### What I worked on yesterday
 *
 * Phase 1 scope only tracks 4 of those: Today ("What I've been working
 * on"), Yesterday, Upcoming Meetings, and Assigned Issues. The other real
 * sections (Watched repos, Sleuth reminders) are intentionally not
 * surfaced as their own tree sections yet — out of scope for this lane.
 */

export interface PulseItem {
  /** Bullet/line text with leading "- " markdown stripped, otherwise verbatim. */
  text: string;
  /** True for the generator's italic empty-state lines, e.g. "_No upcoming meetings today._" */
  isPlaceholder: boolean;
  /** True for a bold sub-group label line, e.g. "**Obsidian vault edits**" (no leading "- "). */
  isGroupLabel: boolean;
}

export interface PulseSection {
  title: string;
  /** Every non-heading line captured for this section, in file order (blank lines dropped). */
  rawLines: string[];
  /** Parsed leaf/group rows derived from rawLines. */
  items: PulseItem[];
}

export interface ParsedPulse {
  today: PulseSection;
  yesterday: PulseSection;
  upcomingMeetings: PulseSection;
  assignedIssues: PulseSection;
}

type SectionKey = keyof ParsedPulse;

const SECTION_MATCHERS: { key: SectionKey; title: string; match: (line: string) => boolean }[] = [
  { key: 'today', title: 'Today', match: (l) => l.startsWith("### What I've been working on") },
  { key: 'upcomingMeetings', title: 'Upcoming Meetings', match: (l) => l.startsWith('### Upcoming Meetings') },
  {
    key: 'assignedIssues',
    title: 'Assigned Issues',
    // Prefix match tolerates the generator's "(last 7 days)" suffix drifting.
    match: (l) => l.startsWith('### GitHub Issues assigned to me'),
  },
  { key: 'yesterday', title: 'Yesterday', match: (l) => l.startsWith('### What I worked on yesterday') },
];

function emptySection(title: string): PulseSection {
  return { title, rawLines: [], items: [] };
}

/**
 * Buckets every line of the pulse markdown into one of the 4 tracked
 * sections (or discards it, if it belongs to an untracked section like
 * "Watched repos"). A line belongs to whichever tracked section heading
 * most recently preceded it; any other markdown heading (of any `#`
 * depth) closes the currently tracked section.
 */
function bucketLines(content: string): Record<SectionKey, string[]> {
  const buckets: Record<SectionKey, string[]> = {
    today: [],
    yesterday: [],
    upcomingMeetings: [],
    assignedIssues: [],
  };

  let active: SectionKey | null = null;

  for (const rawLine of content.split(/\r?\n/)) {
    const trimmed = rawLine.trim();

    const matched = SECTION_MATCHERS.find((m) => m.match(trimmed));
    if (matched) {
      active = matched.key;
      continue; // don't store the heading line itself
    }

    if (trimmed.startsWith('#')) {
      // Any other heading (##, ###, ####, ...) ends the tracked section.
      active = null;
      continue;
    }

    if (active) {
      buckets[active].push(rawLine);
    }
  }

  return buckets;
}

/** Turns a tracked section's raw lines into renderable items (blank lines dropped). */
function extractItems(rawLines: string[]): PulseItem[] {
  const items: PulseItem[] = [];
  for (const line of rawLines) {
    const trimmed = line.trim();
    if (trimmed.length === 0) {
      continue;
    }
    const isBullet = trimmed.startsWith('- ');
    const text = isBullet ? trimmed.slice(2).trim() : trimmed;
    const isPlaceholder = /^_.*_$/.test(trimmed);
    const isGroupLabel = !isBullet && trimmed.startsWith('**');
    items.push({ text, isPlaceholder, isGroupLabel });
  }
  return items;
}

/** Parses a full pulse markdown document into the 4 Phase-1 tree sections. */
export function parsePulseMarkdown(content: string): ParsedPulse {
  const buckets = bucketLines(content);
  const result = {} as ParsedPulse;
  for (const { key, title } of SECTION_MATCHERS) {
    const section = emptySection(title);
    section.rawLines = buckets[key];
    section.items = extractItems(buckets[key]);
    result[key] = section;
  }
  return result;
}
