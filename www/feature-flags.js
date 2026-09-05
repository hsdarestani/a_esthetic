(() => {
  'use strict';

  // Deferred customer-facing modules. Their implementation/data is retained so
  // they can be re-enabled later without rebuilding the feature from scratch.
  const DISABLED_SELECTORS = [
    '[data-p1-route="plans"]',
    '[data-p2-route="shop"]',
    '[data-p3-route]',
    '.more-grid [data-route="messages"]',
  ];

  function isDisabledTarget(node) {
    if (!(node instanceof Element)) return false;
    return DISABLED_SELECTORS.some(selector => node.closest(selector));
  }

  function cleanup() {
    DISABLED_SELECTORS.forEach(selector => {
      document.querySelectorAll(selector).forEach(node => node.remove());
    });
  }

  // Block a stale button between insertion and MutationObserver cleanup.
  document.addEventListener('click', event => {
    if (!isDisabledTarget(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);

  const observer = new MutationObserver(cleanup);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', cleanup);
  setTimeout(cleanup, 0);
})();
