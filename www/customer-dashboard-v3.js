(() => {
  'use strict';

  const APP_ORIGIN = 'https://app.a-esthetic.de';
  const API = `${APP_ORIGIN}/api/mobile`;
  const ICONS = { ...window.AEstheticIconSet, book: window.AEstheticIconSet.appointments };

  const iconWrap = (name) => `<span class="dash-action-icon" aria-hidden="true">${ICONS[name]}</span>`;

  function fixBottomNav() {
    document.querySelectorAll('.nav-btn[data-route]').forEach((button) => {
      const route = button.dataset.route;
      const icon = button.querySelector(':scope > span:first-child');
      if (!icon || !ICONS[route] || icon.dataset.v3Icon === route) return;
      icon.innerHTML = ICONS[route];
      icon.dataset.v3Icon = route;
    });
  }

  function decorateAction(node, name) {
    if (!node || node.dataset.v3Decorated === '1') return;
    node.dataset.v3Decorated = '1';
    node.insertAdjacentHTML('afterbegin', iconWrap(name));
    const text = document.createElement('span');
    text.className = 'dash-action-copy';
    [...node.children].filter((child) => !child.classList.contains('dash-action-icon')).forEach((child) => text.appendChild(child));
    node.appendChild(text);
  }

  async function openGoogleReview(button) {
    if (button.dataset.loading === '1') return;
    button.dataset.loading = '1';
    button.classList.add('is-loading');
    const popup = window.open('about:blank', '_blank');
    try {
      const token = localStorage.getItem('aplus_token') || '';
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await fetch(`${API}/reviews/`, { headers, cache: 'no-store' });
      const data = await response.json();
      if (!response.ok || !data.review_url) throw new Error('review_url_missing');
      fetch(`${API}/reviews/`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'opened' }),
        cache: 'no-store'
      }).catch(() => {});
      if (popup) popup.location.href = data.review_url;
      else window.location.href = data.review_url;
    } catch (_) {
      if (popup) popup.close();
      button.classList.remove('is-loading');
      button.dataset.loading = '';
    }
  }

  function addReviewToDashboard(main) {
    if (!main || main.querySelector('[data-dashboard-google-review]')) return;
    const points = main.querySelector('.dash-points');
    if (!points) return;
    const review = document.createElement('button');
    review.type = 'button';
    review.className = 'dash-google-review';
    review.dataset.dashboardGoogleReview = '1';
    review.innerHTML = `${iconWrap('google')}<span class="dash-google-copy"><small>GOOGLE BEWERTUNG</small><strong>Erfahrung teilen</strong><em>250 Punkte erst nach echter Verifizierung</em></span><span class="dash-google-arrow">↗</span>`;
    review.addEventListener('click', () => openGoogleReview(review));
    points.insertAdjacentElement('afterend', review);
  }

  function polishDashboard() {
    const main = document.querySelector('.core-main');
    if (!main || !main.querySelector('.dash-hero')) return;
    const actions = main.querySelectorAll('.dash-actions .dash-action');
    decorateAction(actions[0], 'book');
    decorateAction(actions[1], 'phone');
    decorateAction(actions[2], 'instagram');
    decorateAction(actions[3], 'directions');
    main.querySelector('[data-dashboard-google-review]')?.remove();
  }

  function simplifyPoints() {
    const main = document.querySelector('.core-main');
    if (!main) return;
    const reviewTask = main.querySelector('[data-review-route]');
    if (reviewTask) reviewTask.remove();
    const grid = main.querySelector('.point-task-grid');
    if (grid && grid.children.length === 1) grid.classList.add('is-single');

    // Old in-app review form is intentionally no longer part of the customer UX.
    const reviewForm = main.querySelector('[data-review-submit]');
    if (reviewForm) {
      const pointsNav = document.querySelector('.nav-btn[data-route="points"]');
      pointsNav?.click();
    }
  }

  let queued = false;
  function enhance() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      fixBottomNav();
      polishDashboard();
      simplifyPoints();
    });
  }

  new MutationObserver(enhance).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', enhance, { once: true });
  window.addEventListener('pageshow', enhance);
  setTimeout(enhance, 0);
})();
