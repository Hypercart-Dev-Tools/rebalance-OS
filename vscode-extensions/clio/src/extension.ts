import * as vscode from 'vscode';
import { MarkdownViewProvider } from './markdownViewProvider';

export function activate(context: vscode.ExtensionContext): void {
  const provider = new MarkdownViewProvider(context);

  context.subscriptions.push(
    // No retainContextWhenHidden: the webview persists its own scroll position
    // through getState/setState, so keeping the hidden context resident would
    // cost memory for a benefit that is already covered.
    vscode.window.registerWebviewViewProvider(MarkdownViewProvider.viewId, provider),
    vscode.commands.registerCommand('sidebarMarkdown.chooseFile', () => provider.chooseFile()),
    vscode.commands.registerCommand('sidebarMarkdown.refresh', () => provider.refresh()),
    vscode.commands.registerCommand('sidebarMarkdown.showSource', () => provider.setMode('source')),
    vscode.commands.registerCommand('sidebarMarkdown.showRendered', () => provider.setMode('rendered')),
    vscode.commands.registerCommand('sidebarMarkdown.openInEditor', () => provider.openInEditor()),
  );
}

export function deactivate(): void {}
