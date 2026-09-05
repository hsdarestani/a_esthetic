(() => {
  'use strict';

  let scheduled = false;

  function keepFirst(selector) {
    const nodes = [...document.querySelectorAll(selector)];
    nodes.slice(1).forEach(node => node.remove());
  }

  function cleanProfileHub() {
    scheduled = false;
    const heading = [...document.querySelectorAll('.pagehead h1')]
      .find(node => node.textContent.trim() === 'Mehr');
    const grid = heading?.closest('.content')?.querySelector('.more-grid');
    if (!grid) return;

    keepFirst('[data-ops-center]');
    keepFirst('[data-ops-admin]');

    // Keep the two operational entries together at the end of the first menu.
    const notifications = grid.querySelector('[data-ops-center]');
    const admin = grid.querySelector('[data-ops-admin]');
    if (notifications) grid.appendChild(notifications);
    if (admin) grid.appendChild(admin);
    grid.dataset.opsStable = '1';
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(cleanProfileHub);
  }

  const root = document.getElementById('app') || document.documentElement;
  new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', schedule);
  window.addEventListener('pageshow', schedule);
  setTimeout(schedule, 0);
})();
