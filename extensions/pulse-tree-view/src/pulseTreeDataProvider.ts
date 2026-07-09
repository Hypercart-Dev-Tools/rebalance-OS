import * as vscode from 'vscode';
import { PulseTreeItem } from './pulseTreeItem';

/**
 * Phase 0 spike: hardcoded fixture data shaped to match the REAL section
 * structure of live-pulse.md (see PROJECT/2-WORKING/GH-123-VSCODE-PULSE-TREE-VIEW.md
 * "Spike findings" for the source excerpts this was built from). Validates
 * that VS Code's TreeDataProvider API renders this shape correctly before
 * Phase 1 replaces getRootSections() with a real parser reading
 * `pulseTreeView.pulseFilePath`.
 */
export class PulseTreeDataProvider implements vscode.TreeDataProvider<PulseTreeItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<PulseTreeItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: PulseTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: PulseTreeItem): Thenable<PulseTreeItem[]> {
    if (!element) {
      return Promise.resolve(this.getRootSections());
    }
    return Promise.resolve(element.children ?? []);
  }

  private getRootSections(): PulseTreeItem[] {
    const today = new PulseTreeItem(
      'Today',
      vscode.TreeItemCollapsibleState.Expanded,
      undefined,
      undefined,
      'calendar',
      [
        new PulseTreeItem(
          'sleuth-app — feat: unify bucketed display for Daily Digest (v1.4.55)',
          vscode.TreeItemCollapsibleState.None,
          'commit',
          undefined,
          'git-commit'
        ),
        new PulseTreeItem(
          'pdda #29 — warn when git-pulse projection destination is dirty or behind',
          vscode.TreeItemCollapsibleState.None,
          'PR (open)',
          'https://github.com/Hypercart-Dev-Tools/pdda/pull/29',
          'git-pull-request'
        )
      ]
    );

    const yesterday = new PulseTreeItem(
      'Yesterday',
      vscode.TreeItemCollapsibleState.Collapsed,
      undefined,
      undefined,
      'history',
      [
        new PulseTreeItem(
          'sleuth-app — 14 commits, 8 comments',
          vscode.TreeItemCollapsibleState.None,
          undefined,
          undefined,
          'git-commit'
        )
      ]
    );

    const meetings = new PulseTreeItem(
      'Upcoming Meetings',
      vscode.TreeItemCollapsibleState.Collapsed,
      undefined,
      undefined,
      'watch',
      [
        new PulseTreeItem(
          'End of Day Check-In',
          vscode.TreeItemCollapsibleState.None,
          '5:00 PM–5:15 PM',
          undefined,
          'clock'
        )
      ]
    );

    const assigned = new PulseTreeItem(
      'Assigned Issues (last 7 days)',
      vscode.TreeItemCollapsibleState.Collapsed,
      undefined,
      undefined,
      'checklist',
      [
        new PulseTreeItem(
          'pdda #15 — Fresh installs self-inflict ~30 governance warns',
          vscode.TreeItemCollapsibleState.None,
          'updated Jul 8',
          'https://github.com/Hypercart-Dev-Tools/pdda/issues/15',
          'issue-opened'
        )
      ]
    );

    return [today, yesterday, meetings, assigned];
  }
}
