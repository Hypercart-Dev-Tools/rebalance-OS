import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { decodePath, escapeHtml, normalizeLineTerminators, renderMarkdown } from '../src/render';

describe('normalizeLineTerminators', () => {
  it('converts CRLF and lone CR to LF', () => {
    assert.equal(normalizeLineTerminators('a\r\nb\rc'), 'a\nb\nc');
  });

  it('converts the Unicode LS/PS terminators VS Code warns about', () => {
    assert.equal(normalizeLineTerminators('a\u2028b\u2029c'), 'a\nb\nc');
  });

  it('leaves plain LF text untouched', () => {
    assert.equal(normalizeLineTerminators('a\nb\n'), 'a\nb\n');
  });
});

describe('escapeHtml', () => {
  it('escapes the characters that would open a tag or entity', () => {
    assert.equal(escapeHtml('<a> & </a>'), '&lt;a&gt; &amp; &lt;/a&gt;');
  });

  it('escapes the ampersand first so escapes are not double-encoded', () => {
    assert.equal(escapeHtml('&lt;'), '&amp;lt;');
  });
});

describe('decodePath', () => {
  it('percent-decodes a well-formed path', () => {
    assert.equal(decodePath('my%20image.png'), 'my image.png');
  });

  // Regression: a raw HTML <img src="90%.png"> reaches the decoder undecoded
  // because html:true passes it through verbatim. decodeURIComponent throws
  // URIError on it, which used to escape update() as an unhandled rejection
  // and freeze the view on stale content.
  it('returns the literal path when the percent-escape is malformed', () => {
    assert.equal(decodePath('90%.png'), '90%.png');
    assert.equal(decodePath('file%zz.png'), 'file%zz.png');
    assert.doesNotThrow(() => decodePath('%'));
  });
});

describe('renderMarkdown', () => {
  it('renders ordinary markdown', () => {
    assert.match(renderMarkdown('# Title'), /<h1>Title<\/h1>/);
  });

  it('keeps HTML comments, which CLIO writes between entries', () => {
    assert.match(renderMarkdown('<!-- clio:id:1 -->\n\ntext'), /<!-- clio:id:1 -->/);
  });

  it('strips script blocks', () => {
    assert.doesNotMatch(renderMarkdown('<script>alert(1)</script>'), /<script/i);
  });

  it('strips an unterminated script block', () => {
    assert.doesNotMatch(renderMarkdown('<script>alert(1)'), /<script/i);
  });

  it('strips inline event handlers', () => {
    const html = renderMarkdown('<img src=x onerror=alert(1)>');
    assert.doesNotMatch(html, /onerror/i);
    assert.match(html, /<img src=x>/);
  });

  it('neutralizes javascript: hrefs', () => {
    const html = renderMarkdown('<a href="javascript:alert(1)">x</a>');
    assert.doesNotMatch(html, /javascript:/i);
    assert.match(html, /href="#"/);
  });

  it('does not treat markdown inside a fenced block as HTML', () => {
    const html = renderMarkdown('```\n<script>alert(1)</script>\n```');
    assert.match(html, /&lt;script&gt;/);
  });
});
