// Webview client: receives ready-to-display state from the extension host,
// keeps scroll position across refreshes and view show/hide.
(function () {
  const vscode = acquireVsCodeApi();
  const root = document.getElementById('root');
  let currentKey = '';

  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg || msg.type !== 'state') {
      return;
    }

    document.body.className = msg.styleClass + ' mode-' + (msg.mode || 'rendered');

    if (msg.state === 'content') {
      const key = (msg.fileName || '') + '|' + msg.mode;
      const sameDoc = key === currentKey;
      const previousScroll = window.scrollY;
      currentKey = key;
      root.innerHTML = msg.html;
      restoreScroll(sameDoc ? previousScroll : savedScrollFor(key));
    } else {
      currentKey = '';
      showPlaceholder(msg);
    }
  });

  function showPlaceholder(msg) {
    root.textContent = '';
    const box = document.createElement('div');
    box.className = 'placeholder';

    const p = document.createElement('p');
    p.textContent =
      msg.state === 'error'
        ? 'The configured markdown file could not be read.'
        : 'No markdown file is configured yet.';
    box.appendChild(p);

    if (msg.message) {
      const detail = document.createElement('p');
      detail.className = 'detail';
      detail.textContent = msg.message;
      box.appendChild(detail);
    }

    const button = document.createElement('button');
    button.textContent = 'Choose Markdown File…';
    button.addEventListener('click', () => vscode.postMessage({ type: 'chooseFile' }));
    box.appendChild(button);

    root.appendChild(box);
  }

  // ---------- scroll persistence ----------

  function savedScrollFor(key) {
    const state = vscode.getState();
    return state && state.key === key ? state.scrollY : 0;
  }

  function restoreScroll(y) {
    if (y > 0) {
      requestAnimationFrame(() => window.scrollTo(0, y));
    }
  }

  let scrollTimer;
  window.addEventListener('scroll', () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      if (currentKey) {
        vscode.setState({ key: currentKey, scrollY: window.scrollY });
      }
    }, 100);
  });

  // ---------- in-page anchor links ----------
  // External links are opened by VS Code's default webview link handler;
  // fragment links need manual scrolling.
  document.addEventListener('click', (event) => {
    const anchor = event.target instanceof Element ? event.target.closest('a[href^="#"]') : null;
    if (!anchor) {
      return;
    }
    event.preventDefault();
    const id = decodeURIComponent(anchor.getAttribute('href').slice(1));
    const target = document.getElementById(id) || document.querySelector('[name="' + CSS.escape(id) + '"]');
    if (target) {
      target.scrollIntoView();
    }
  });
})();
