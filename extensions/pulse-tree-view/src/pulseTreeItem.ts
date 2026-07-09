import * as vscode from 'vscode';

/**
 * One node in the pulse tree — either a section header (has children, no
 * command) or a leaf item (a commit/issue/meeting; may open a URL on click).
 */
export class PulseTreeItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
    description?: string,
    url?: string,
    iconId?: string,
    public readonly children?: PulseTreeItem[]
  ) {
    super(label, collapsibleState);
    this.description = description;
    if (iconId) {
      this.iconPath = new vscode.ThemeIcon(iconId);
    }
    if (url) {
      this.command = {
        command: 'vscode.open',
        title: 'Open',
        arguments: [vscode.Uri.parse(url)]
      };
    }
  }
}
