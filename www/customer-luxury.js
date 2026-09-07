(() => {
  'use strict';

  const icons = {
    appointments: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5.5" width="17" height="15" rx="3"/><path d="M8 3.5v4M16 3.5v4M3.5 10h17"/><path d="M8 14h3M8 17h6"/></svg>',
    reviews: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.72 5.51 6.08.88-4.4 4.29 1.04 6.06L12 16.88l-5.44 2.86 1.04-6.06-4.4-4.29 6.08-.88L12 3Z"/></svg>',
    friends: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.4-3.35 2.35-5.1 5.5-5.1s5.1 1.75 5.5 5.1"/><path d="M15.5 7.5h5M18 5v5M14.8 13.2c2.55.35 4.05 1.85 4.4 4.3"/></svg>',
    wallet: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7.2A2.7 2.7 0 0 1 6.7 4.5h10.8A2.5 2.5 0 0 1 20 7v10.2a2.3 2.3 0 0 1-2.3 2.3H6.3A2.3 2.3 0 0 1 4 17.2V7.2Z"/><path d="M4 8h13.2A2.8 2.8 0 0 1 20 10.8v3.7h-5.1a2.6 2.6 0 0 1 0-5.2H20"/><circle cx="15" cy="11.9" r=".7" fill="currentColor" stroke="none"/></svg>',
    records: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3.5h7l4 4v13H7a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2Z"/><path d="M14 3.5v4h4M8.5 12h6M8.5 15.5h6"/></svg>',
    settings: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.1"/><path d="M19.1 13.8a7.6 7.6 0 0 0 .05-3.6l2-1.55-2-3.45-2.48 1a7.7 7.7 0 0 0-3.12-1.8L13.2 2h-4l-.35 2.4a7.7 7.7 0 0 0-3.12 1.8l-2.48-1-2 3.45 2 1.55a7.6 7.6 0 0 0 .05 3.6l-2.05 1.55 2 3.45 2.53-1.02a7.7 7.7 0 0 0 3.07 1.77L9.2 22h4l.35-2.45a7.7 7.7 0 0 0 3.07-1.77l2.53 1.02 2-3.45-2.05-1.55Z"/></svg>'
  };

  function enhanceShell() {
    const shell = document.querySelector('.core-shell');
    if (!shell) return;

    const active = shell.querySelector('.nav-btn.is-active[data-route]');
    const route = active?.dataset.route || '';
    ['appointments','reviews','friends','wallet','records'].forEach(name => shell.classList.remove(`route-${name}`));
    if (route) shell.classList.add(`route-${route}`);

    shell.querySelectorAll('.nav-btn[data-route]').forEach(button => {
      const mark = button.querySelector(':scope > span:first-child');
      const name = button.dataset.route;
      if (mark && icons[name] && mark.dataset.luxIcon !== name) {
        mark.innerHTML = icons[name];
        mark.dataset.luxIcon = name;
      }
    });

    const settings = shell.querySelector('[data-settings]');
    if (settings && settings.dataset.luxIcon !== '1') {
      settings.innerHTML = icons.settings;
      settings.dataset.luxIcon = '1';
    }

    const main = shell.querySelector('.core-main');
    if (!main) return;
    main.dataset.route = route;

    if (route === 'reviews') {
      main.querySelectorAll('.card').forEach(card => {
        if (card.querySelector('[data-review-submit]')) card.classList.add('review-entry-card');
      });
    }
    if (route === 'friends') {
      main.querySelectorAll('.card').forEach(card => {
        if (card.querySelector('[data-referral]')) card.classList.add('referral-compose-card');
      });
    }
  }

  function enhanceSettings() {
    document.querySelectorAll('.settings-overlay').forEach(overlay => {
      if (overlay.dataset.luxury === '1') return;
      overlay.dataset.luxury = '1';
      overlay.querySelector('.settings-card')?.classList.add('luxury-settings-card');
    });
  }

  let queued = false;
  function run() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      enhanceShell();
      enhanceSettings();
    });
  }

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', run, { once: true });
  window.addEventListener('pageshow', run);
  setTimeout(run, 0);
})();
