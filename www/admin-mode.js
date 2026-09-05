(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const BOOK_ENTRY = 'https://book.a-esthetic.de/verwaltung/app/';
  const nativeFetch = window.fetch.bind(window);
  let adminState = null;
  let adminCheck = null;
  let redirecting = false;

  const token = () => localStorage.getItem('aplus_token') || '';

  function blankForAdmin() {
    document.documentElement.classList.add('aplus-admin-transition');
    const app = document.getElementById('app');
    if (app) {
      app.innerHTML = '<main style="min-height:100vh;background:#fff;display:grid;place-items:center"><div style="font:14px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;color:#746e62">Verwaltung wird geöffnet…</div></main>';
    }
  }

  function openExactBookAdmin(value = token()) {
    if (!value || redirecting) return;
    redirecting = true;
    adminState = true;
    blankForAdmin();
    // The bearer lives only in the fragment. The Book bridge immediately removes
    // it from the address bar and exchanges it for a normal first-party staff session.
    window.location.replace(`${BOOK_ENTRY}#token=${encodeURIComponent(value)}`);
  }

  async function isAdmin(force = false) {
    const value = token();
    if (!value) {
      adminState = false;
      adminCheck = null;
      return false;
    }
    if (adminState !== null && !force) return adminState;
    if (adminCheck && !force) return adminCheck;

    adminCheck = (async () => {
      try {
        const response = await nativeFetch(`${API_BASE}/admin/`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${value}`, Accept: 'application/json' },
          cache: 'no-store',
        });
        if (response.status === 403) {
          adminState = false;
          return false;
        }
        if (!response.ok) {
          adminState = false;
          return false;
        }
        const data = await response.json().catch(() => ({}));
        adminState = Boolean(data && data.ok && data.admin);
        if (adminState) openExactBookAdmin(value);
        return adminState;
      } catch (_) {
        adminState = false;
        return false;
      } finally {
        adminCheck = null;
      }
    })();
    return adminCheck;
  }

  // Install before app.js. Existing admin sessions are checked before Customer Club
  // can call /me or /dashboard, so an admin never renders the customer navigation.
  window.fetch = async function aplusRoleAwareFetch(input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const isMobileApi = url.startsWith(API_BASE);
    const isLogin = url.includes('/login/');
    const isAdminApi = url.includes('/admin/');

    if (isMobileApi && !isLogin && !isAdminApi && token() && adminState === null) {
      const admin = await isAdmin();
      if (admin || redirecting) return new Promise(() => {});
    }

    const response = await nativeFetch(input, init);

    // New logins declare the role server-side. For admins, consume the response here
    // and navigate before app.js can create/render a Customer Club session.
    if (isMobileApi && isLogin && response.ok) {
      try {
        const data = await response.clone().json();
        if (data && data.token && data.admin === true) {
          localStorage.setItem('aplus_token', data.token);
          openExactBookAdmin(data.token);
          return new Promise(() => {});
        }
        if (data && data.token && data.admin === false) adminState = false;
      } catch (_) {}
    }
    return response;
  };

  // Existing bearer: begin role resolution immediately, before app.js boot executes.
  if (token()) void isAdmin();

  window.APlusAdminMode = {
    open: () => openExactBookAdmin(),
    check: () => isAdmin(true),
  };
})();
