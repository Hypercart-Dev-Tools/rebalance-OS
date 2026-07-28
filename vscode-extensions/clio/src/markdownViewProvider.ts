import { randomBytes } from 'node:crypto';
import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import { decodePath, escapeHtml, normalizeLineTerminators, renderMarkdown } from './render';

type Mode = 'rendered' | 'source';

const MODE_STATE_KEY = 'sidebarMarkdown.mode';

export class MarkdownViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewId = 'sidebarMarkdown.view';

  private view?: vscode.WebviewView;
  private mode: Mode;
  private updateSeq = 0;
  private watcher?: fs.FSWatcher;
  private watchedFile?: string;
  private updateTimer?: NodeJS.Timeout;

  constructor(private readonly context: vscode.ExtensionContext) {
    this.mode = context.globalState.get<Mode>(MODE_STATE_KEY, 'rendered');
    void vscode.commands.executeCommand('setContext', 'sidebarMarkdown.mode', this.mode);

    context.subscriptions.push(
      vscode.workspace.onDidChangeConfiguration((e) => {
        if (e.affectsConfiguration('sidebarMarkdown')) {
          this.refresh();
        }
      }),
      new vscode.Disposable(() => this.disposeWatcher()),
    );
  }

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    this.applyWebviewOptions();
    webviewView.webview.html = this.buildSkeleton(webviewView.webview);

    webviewView.webview.onDidReceiveMessage((message: { type?: string } | undefined) => {
      if (message?.type === 'chooseFile') {
        void this.chooseFile();
      }
    });

    webviewView.onDidDispose(() => {
      if (this.view === webviewView) {
        this.view = undefined;
      }
    });

    this.refresh();
  }

  refresh(): void {
    this.applyWebviewOptions();
    this.ensureWatcher();
    void this.update();
  }

  setMode(mode: Mode): void {
    if (this.mode === mode) {
      return;
    }
    this.mode = mode;
    void this.context.globalState.update(MODE_STATE_KEY, mode);
    void vscode.commands.executeCommand('setContext', 'sidebarMarkdown.mode', mode);
    void this.update();
  }

  async openInEditor(): Promise<void> {
    const file = this.filePath;
    if (!file) {
      void vscode.window.showInformationMessage('Sidebar Markdown: no file is configured yet.');
      return;
    }
    try {
      await fs.promises.access(file, fs.constants.R_OK);
    } catch {
      void vscode.window.showInformationMessage(
        `Sidebar Markdown: cannot open ${file} — it is missing or unreadable.`,
      );
      return;
    }
    await vscode.window.showTextDocument(vscode.Uri.file(file), { preview: false });
  }

  async chooseFile(): Promise<void> {
    const picked = await vscode.window.showOpenDialog({
      canSelectMany: false,
      openLabel: 'Show in Sidebar',
      filters: { Markdown: ['md', 'markdown', 'mdown', 'txt'], 'All Files': ['*'] },
    });
    if (picked?.[0]) {
      // Application-scoped setting: lands in user settings, visible to every window.
      await this.config.update('file', picked[0].fsPath, vscode.ConfigurationTarget.Global);
    }
  }

  // ---------- configuration ----------

  private get config(): vscode.WorkspaceConfiguration {
    return vscode.workspace.getConfiguration('sidebarMarkdown');
  }

  private get filePath(): string {
    return (this.config.get<string>('file') ?? '').trim();
  }

  private get styleClass(): string {
    return this.config.get<string>('style') === 'clio' ? 'style-clio' : 'style-theme';
  }

  // ---------- rendering ----------

  private async update(): Promise<void> {
    const view = this.view;
    if (!view) {
      return;
    }

    // update() is entered from refresh(), setMode() and the debounced watcher,
    // and awaits a file read in between. Stamp each run so a slow read that
    // finishes late cannot overwrite the result of a newer one.
    const seq = ++this.updateSeq;
    const isCurrent = (): boolean => seq === this.updateSeq;

    const file = this.filePath;
    if (!file) {
      void view.webview.postMessage({ type: 'state', state: 'empty', styleClass: this.styleClass });
      return;
    }

    let raw: string;
    try {
      raw = await fs.promises.readFile(file, 'utf8');
    } catch (error) {
      if (isCurrent()) {
        void view.webview.postMessage({
          type: 'state',
          state: 'error',
          message: `${file} — ${error instanceof Error ? error.message : String(error)}`,
          styleClass: this.styleClass,
        });
      }
      return;
    }

    if (!isCurrent()) {
      return;
    }

    const text = normalizeLineTerminators(raw);

    let html: string;
    try {
      html =
        this.mode === 'rendered'
          ? this.rewriteImageSources(renderMarkdown(text), path.dirname(file), view.webview)
          : `<pre class="source">${escapeHtml(text)}</pre>`;
    } catch (error) {
      // Never let a render failure leave the view frozen on stale content
      // with nothing reported — surface it in the existing error state.
      void view.webview.postMessage({
        type: 'state',
        state: 'error',
        message: `${file} — could not be rendered: ${error instanceof Error ? error.message : String(error)}`,
        styleClass: this.styleClass,
      });
      return;
    }

    void view.webview.postMessage({
      type: 'state',
      state: 'content',
      html,
      mode: this.mode,
      fileName: file,
      styleClass: this.styleClass,
    });
  }

  /** Resolve image paths relative to the markdown file into webview URIs. */
  private rewriteImageSources(html: string, baseDir: string, webview: vscode.Webview): string {
    // markdown-it always emits double quotes, but raw HTML (html: true) may use
    // either — capture the quote character and require the same one to close.
    return html.replace(
      /(<img\b[^>]*?\bsrc=)(["'])((?:(?!\2).)*)\2/gi,
      (match, prefix: string, quote: string, src: string) => {
        if (/^[a-z][a-z0-9+.-]*:/i.test(src) || src.startsWith('//') || src.startsWith('#')) {
          return match;
        }
        const target = vscode.Uri.file(path.resolve(baseDir, decodePath(src)));
        return prefix + quote + webview.asWebviewUri(target).toString() + quote;
      },
    );
  }

  private applyWebviewOptions(): void {
    if (!this.view) {
      return;
    }
    const roots = [vscode.Uri.joinPath(this.context.extensionUri, 'media')];
    if (this.filePath) {
      roots.push(vscode.Uri.file(path.dirname(this.filePath)));
    }
    this.view.webview.options = { enableScripts: true, localResourceRoots: roots };
  }

  private buildSkeleton(webview: vscode.Webview): string {
    const nonce = createNonce();
    const viewCss = webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, 'media', 'view.css'));
    const mainJs = webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, 'media', 'main.js'));
    const csp = [
      "default-src 'none'",
      `style-src ${webview.cspSource}`,
      `img-src ${webview.cspSource} https: data:`,
      `font-src ${webview.cspSource}`,
      `script-src 'nonce-${nonce}'`,
    ].join('; ');

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <link rel="stylesheet" href="${viewCss.toString()}">
</head>
<body class="${this.styleClass} mode-${this.mode}">
  <div id="root"></div>
  <script nonce="${nonce}" src="${mainJs.toString()}"></script>
</body>
</html>`;
  }

  // ---------- file watching ----------

  private ensureWatcher(): void {
    const file = this.filePath;
    if (this.watchedFile === file && this.watcher) {
      return;
    }
    this.disposeWatcher();
    this.watchedFile = file;
    if (!file) {
      return;
    }

    // Watch the parent directory rather than the file itself: most editors
    // (and CLIO, presumably) save via atomic rename, which breaks a watch
    // bound directly to the inode.
    const dir = path.dirname(file);
    const base = path.basename(file);
    try {
      const watcher = fs.watch(dir, (_event, filename) => {
        if (!filename || filename.toString() === base) {
          this.scheduleUpdate();
        }
      });
      // FSWatcher is an EventEmitter: an unhandled 'error' event throws. Tear
      // the watcher down instead so a later ensureWatcher() can rebuild it.
      watcher.on('error', () => this.disposeWatcher());
      this.watcher = watcher;
    } catch {
      // Directory does not exist; update() will surface the read error.
    }
  }

  private scheduleUpdate(): void {
    clearTimeout(this.updateTimer);
    this.updateTimer = setTimeout(() => void this.update(), 150);
  }

  private disposeWatcher(): void {
    this.watcher?.close();
    this.watcher = undefined;
    this.watchedFile = undefined;
    clearTimeout(this.updateTimer);
  }
}

function createNonce(): string {
  return randomBytes(24).toString('base64');
}
