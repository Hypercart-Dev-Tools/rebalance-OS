import * as vscode from 'vscode';
import { PulseTreeProvider } from './pulseTreeProvider';

function getConfiguredPulseFilePath(): string | undefined {
  const value = vscode.workspace.getConfiguration('pulseTreeView').get<string>('pulseFilePath');
  return value && value.trim().length > 0 ? value.trim() : undefined;
}

export function activate(context: vscode.ExtensionContext): void {
  const provider = new PulseTreeProvider(getConfiguredPulseFilePath);
  const treeView = vscode.window.createTreeView('pulseTreeView', { treeDataProvider: provider });

  context.subscriptions.push(treeView);

  context.subscriptions.push(
    vscode.commands.registerCommand('pulseTreeView.refresh', () => provider.refresh())
  );

  // Re-render automatically when the user edits the setting itself (a
  // convenience on top of the required manual "Refresh" command, which
  // remains the only way to pick up on-disk file changes in this Phase 1
  // MVP — a file watcher is explicitly Phase 2 scope).
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration('pulseTreeView.pulseFilePath')) {
        provider.refresh();
      }
    })
  );
}

export function deactivate(): void {}
