import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({
  html: true, // CLIO writes HTML comments between entries; let them pass through invisibly
  linkify: true,
});

/**
 * The source file may contain Unicode LS/PS line terminators (VS Code's
 * "unusual line terminators" warning) and CRLF. Normalize in memory only —
 * the file on disk is never modified.
 */
export function normalizeLineTerminators(text: string): string {
  return text.replace(/\r\n?/g, '\n').replace(/[\u2028\u2029]/g, '\n');
}

/**
 * Belt-and-braces on top of the webview CSP: drop script blocks, inline event
 * handlers, and javascript: URLs from the rendered HTML.
 */
function sanitize(html: string): string {
  return html
    .replace(/<script[\s\S]*?(<\/script\s*>|$)/gi, '')
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    .replace(/(href|src)\s*=\s*(["']?)\s*javascript:[^"'>\s]*\2/gi, '$1="#"');
}

export function renderMarkdown(text: string): string {
  return sanitize(md.render(text));
}

/**
 * Percent-decode an image path, tolerating malformed escapes.
 *
 * markdown-it normalizes its own `![](…)` URLs, so `100%.png` arrives as
 * `100%25.png` and decodes cleanly. Raw HTML is passed through verbatim
 * (`html: true`), so `<img src="90%.png">` reaches this point undecoded and
 * would throw URIError. Treat an undecodable path as a literal filename.
 */
export function decodePath(src: string): string {
  try {
    return decodeURIComponent(src);
  } catch {
    return src;
  }
}

export function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
