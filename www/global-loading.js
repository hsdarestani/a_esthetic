(() => {
  'use strict';
  let pending = 0, timer = 0, layer;
  function ensure() {
    if (layer) return layer;
    layer = document.createElement('div');
    layer.className = 'aplus-global-wait';
    layer.hidden = true;
    layer.innerHTML = '<div role="status" aria-live="polite"><span class="aplus-loader-brand">A+</span><span class="aplus-loader-ring"></span><strong>Einen Moment …</strong><small>Inhalte werden geladen.</small></div>';
    document.body.appendChild(layer);
    return layer;
  }
  function begin() {
    pending += 1;
    clearTimeout(timer);
    timer = setTimeout(() => { if (pending > 0) ensure().hidden = false; }, 180);
  }
  function end() {
    pending = Math.max(0, pending - 1);
    if (!pending) {
      clearTimeout(timer);
      if (layer) layer.hidden = true;
    }
  }
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const options = args[1] || {};
    if (options.aplusSilent) return originalFetch(...args);
    begin();
    try { return await originalFetch(...args); }
    finally { end(); }
  };
  document.addEventListener('submit', event => {
    const button = event.target?.querySelector?.('button[type="submit"]');
    if (!button) return;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    setTimeout(() => { button.disabled = false; button.removeAttribute('aria-busy'); }, 30000);
  }, true);
})();