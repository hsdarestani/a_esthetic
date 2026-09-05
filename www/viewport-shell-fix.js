(() => {
  'use strict';

  let scheduled = false;

  function releaseScrollLocks() {
    const html = document.documentElement;
    const body = document.body;
    if (!html || !body) return;

    html.classList.add('aplus-scroll-enabled');
    body.classList.add('aplus-scroll-enabled');

    for (const node of [html, body]) {
      node.style.removeProperty('overflow');
      node.style.removeProperty('overflow-y');
      node.style.removeProperty('height');
      node.style.removeProperty('position');
      node.style.removeProperty('touch-action');
    }
  }

  function anchorNavigationToViewport() {
    const root = document.getElementById('app');
    if (!root) return;

    const nav = root.querySelector('.shell > .nav');
    if (nav && nav.parentElement !== root) {
      // Keep existing click handlers intact while escaping .shell's animation/
      // transform context. A fixed nav under #app is fixed to the viewport.
      root.appendChild(nav);
    }
  }

  function apply() {
    scheduled = false;
    releaseScrollLocks();
    anchorNavigationToViewport();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(apply);
  }

  const root = document.getElementById('app');
  if (root) {
    new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
  }

  window.addEventListener('DOMContentLoaded', schedule, { once: true });
  window.addEventListener('pageshow', schedule);
  window.addEventListener('resize', schedule, { passive: true });
  window.addEventListener('orientationchange', schedule, { passive: true });
  setTimeout(schedule, 0);
})();
