import * as vscode from 'vscode';
import { PulseTreeDataProvider } from './pulseTreeDataProvider';

export function activate(context: vscode.ExtensionContext): void {
  const provider = new PulseTreeDataProvider();
  const view = vscode.window.createTreeView('pulseTreeView.mainView', {
    treeDataProvider: provider
  });

  context.subscriptions.push(view);
  context.subscriptions.push(
    vscode.commands.registerCommand('pulseTreeView.refresh', () => provider.refresh())
  );
}

export function deactivate(): void {}
