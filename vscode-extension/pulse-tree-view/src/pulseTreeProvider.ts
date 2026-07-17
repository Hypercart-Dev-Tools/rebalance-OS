import * as vscode from 'vscode';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { parsePulseMarkdown, ParsedPulse, PulseSection } from './pulseParser';

export class PulseTreeItem extends vscode.TreeItem {
  children?: PulseTreeItem[];

  constructor(
    label: string,
    collapsibleState: vscode.TreeItemCollapsibleState,
    options: { description?: string; tooltip?: string; children?: PulseTreeItem[] } = {}
  ) {
    super(label, collapsibleState);
    this.description = options.description;
    this.tooltip = options.tooltip ?? label;
    this.children = options.children;
  }
}

const SECTION_ORDER: { key: keyof ParsedPulse; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: 'yesterday', label: 'Yesterday' },
  { key: 'upcomingMeetings', label: 'Upcoming Meetings' },
  { key: 'assignedIssues', label: 'Assigned Issues' },
];

function expandHome(rawPath: string): string {
  if (rawPath === '~') {
    return os.homedir();
  }
  if (rawPath.startsWith('~/') || rawPath.startsWith('~\\')) {
    return path.join(os.homedir(), rawPath.slice(2));
  }
  return rawPath;
}

function sectionToTreeItem(label: string, section: PulseSection): PulseTreeItem {
  const children =
    section.items.length > 0
      ? section.items.map(
          (item) =>
            new PulseTreeItem(item.text, vscode.TreeItemCollapsibleState.None, {
              tooltip: item.text,
            })
        )
      : [new PulseTreeItem('(nothing here)', vscode.TreeItemCollapsibleState.None)];

  return new PulseTreeItem(label, vscode.TreeItemCollapsibleState.Expanded, {
    description: section.items.length > 0 ? String(section.items.length) : undefined,
    children,
  });
}

/**
 * Reads and parses the configured local pulse markdown file into the
 * Today / Yesterday / Upcoming Meetings / Assigned Issues sidebar tree.
 *
 * Pure local-file reader: no network access, no dependency on the
 * rebalance-OS Python venv or the `pulse-server` daemon being up. If the
 * setting is unset or the file can't be read, renders a single explanatory
 * tree item instead of throwing.
 */
export class PulseTreeProvider implements vscode.TreeDataProvider<PulseTreeItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<PulseTreeItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly getPulseFilePath: () => string | undefined) {}

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: PulseTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: PulseTreeItem): PulseTreeItem[] {
    if (element) {
      return element.children ?? [];
    }
    return this.buildRoot();
  }

  private buildRoot(): PulseTreeItem[] {
    const configuredPath = this.getPulseFilePath();
    if (!configuredPath) {
      return [
        new PulseTreeItem('No pulse file configured', vscode.TreeItemCollapsibleState.None, {
          description: 'Set pulseTreeView.pulseFilePath',
          tooltip:
            'Open Settings and set pulseTreeView.pulseFilePath to your git-pulse-sync clone\'s live-pulse.md, e.g. ~/git-pulse-sync/live-pulse.md',
        }),
      ];
    }

    const resolvedPath = expandHome(configuredPath);
    let content: string;
    try {
      content = fs.readFileSync(resolvedPath, 'utf8');
    } catch {
      return [
        new PulseTreeItem('Pulse file not found', vscode.TreeItemCollapsibleState.None, {
          description: resolvedPath,
          tooltip: `Could not read ${resolvedPath}. Check pulseTreeView.pulseFilePath.`,
        }),
      ];
    }

    const parsed = parsePulseMarkdown(content);
    return SECTION_ORDER.map(({ key, label }) => sectionToTreeItem(label, parsed[key]));
  }
}
