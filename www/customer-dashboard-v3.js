(() => {
  'use strict';

  const API = 'https://esthetic.smarbiz.sbs/api/mobile';
  const ICONS = {
    dashboard: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10.2 12 4l8 6.2v8.3a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5v-8.3Z"/><path d="M9 20v-6h6v6"/></svg>',
    appointments: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5.5" width="17" height="15" rx="3"/><path d="M8 3.5v4M16 3.5v4M3.5 10h17"/><path d="M8 14h3M8 17h6"/></svg>',
    records: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3.5h7l4 4v13H7a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2Z"/><path d="M14 3.5v4h4M8.5 12h6M8.5 15.5h6"/></svg>',
    points: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.3 19.2 7v10L12 20.7 4.8 17V7L12 3.3Z"/><path d="m8.2 12 2.5 2.5 5.1-5.2"/></svg>',
    friends: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.4-3.35 2.35-5.1 5.5-5.1s5.1 1.75 5.5 5.1"/><path d="M15.5 7.5h5M18 5v5M14.8 13.2c2.55.35 4.05 1.85 4.4 4.3"/></svg>',
    book: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5.5" width="17" height="15" rx="3"/><path d="M8 3.5v4M16 3.5v4M3.5 10h17"/><path d="M8 14h8"/></svg>',
    phone: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7.2 3.8 10 8.1 8.3 10a14.3 14.3 0 0 0 5.7 5.7l1.9-1.7 4.3 2.8c.5.3.7.9.5 1.4-.6 1.6-2.1 2.7-3.8 2.7C9.3 20.9 3.1 14.7 3.1 7.1c0-1.7 1.1-3.2 2.7-3.8.5-.2 1.1 0 1.4.5Z"/></svg>',
    instagram: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.4" cy="6.7" r=".8" fill="currentColor" stroke="none"/></svg>',
    google: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 12.2c0-.7-.1-1.3-.2-1.9H12v3.6h4.8a4.1 4.1 0 0 1-1.8 2.7v2.3h2.9c1.7-1.6 2.6-3.9 2.6-6.7Z"/><path d="M12 21c2.4 0 4.5-.8 5.9-2.1L15 16.6c-.8.5-1.8.9-3 .9-2.3 0-4.3-1.6-5-3.7H4v2.4A9 9 0 0 0 12 21Z"/><path d="M7 13.8a5.4 5.4 0 0 1 0-3.6V7.8H4a9 9 0 0 0 0 8.4l3-2.4Z"/><path d="M12 6.5c1.3 0 2.5.5 3.4 1.3L18 5.2A8.7 8.7 0 0 0 4 7.8l3 2.4c.7-2.1 2.7-3.7 5-3.7Z"/></svg>'
  };

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
    addReviewToDashboard(main);
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
