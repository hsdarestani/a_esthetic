(() => {
  'use strict';

  const root = document.documentElement;

  function visible(element) {
    if (!element || !element.isConnected) return false;
    const style = getComputedStyle(element);
    return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) !== 0 && element.getClientRects().length > 0;
  }

  function hasOpenBlockingLayer() {
    const selectors = [
      '.settings-overlay',
      '.modal.is-open',
      '.sheet.is-open',
      '.overlay.is-open',
      '[role="dialog"][aria-hidden="false"]'
    ];
    return selectors.some(selector => Array.from(document.querySelectorAll(selector)).some(visible));
  }

  function neutralizeClosedLayers() {
    document.querySelectorAll('.settings-overlay[aria-hidden="true"], .overlay[aria-hidden="true"], .modal[aria-hidden="true"], .sheet[aria-hidden="true"]').forEach(layer => {
      layer.style.pointerEvents = 'none';
    });
  }

  function recoverScroll() {
    neutralizeClosedLayers();
    if (!document.body || hasOpenBlockingLayer()) return;

    for (const node of [root, document.body]) {
      node.style.removeProperty('overflow');
      node.style.removeProperty('overflow-y');
      node.style.removeProperty('height');
      node.style.removeProperty('max-height');
      node.style.removeProperty('position');
      node.style.removeProperty('top');
      node.style.removeProperty('touch-action');
    }

    document.body.classList.remove('no-scroll', 'scroll-lock', 'scroll-locked', 'modal-open', 'is-locked');
    root.classList.remove('no-scroll', 'scroll-lock', 'scroll-locked', 'modal-open', 'is-locked');
  }

  let queued = false;
  function queueRecovery() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      recoverScroll();
    });
  }

  recoverScroll();
  document.addEventListener('DOMContentLoaded', recoverScroll, { once: true });
  window.addEventListener('pageshow', recoverScroll);
  window.addEventListener('focus', recoverScroll);
  window.addEventListener('hashchange', recoverScroll);

  const app = document.getElementById('app');
  if (app) new MutationObserver(queueRecovery).observe(app, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'aria-hidden', 'style'] });

  setTimeout(recoverScroll, 0);
  setTimeout(recoverScroll, 250);
  setTimeout(recoverScroll, 900);
})();
