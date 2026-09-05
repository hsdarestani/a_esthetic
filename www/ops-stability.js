(() => {
  'use strict';

  let scheduled = false;

  function dedupeWithin(grid, selector) {
    const nodes = [...grid.querySelectorAll(selector)];
    if (nodes.length <= 1) return false;
    nodes.slice(1).forEach(node => node.remove());
    return true;
  }

  function cleanProfileHub() {
    scheduled = false;
    const heading = [...document.querySelectorAll('.pagehead h1')]
      .find(node => node.textContent.trim() === 'Mehr');
    const grid = heading?.closest('.content')?.querySelector('.more-grid');
    if (!grid) return;

    // Only mutate the DOM when an actual duplicate exists. Never append/move the
    // surviving nodes here: moving an existing node fires MutationObserver again
    // and previously created an endless feedback loop on the profile hub.
    dedupeWithin(grid, '[data-ops-center]');
    dedupeWithin(grid, '[data-ops-admin]');
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(cleanProfileHub);
  }

  const root = document.getElementById('app') || document.documentElement;
  new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', schedule, { once: true });
  window.addEventListener('pageshow', schedule);
  setTimeout(schedule, 0);
})();
