(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const BOOK_ENTRY = 'https://book.a-esthetic.de/verwaltung/app/';
  const nativeFetch = window.fetch.bind(window);
  let adminState = null;
  let adminCheck = null;
  let redirecting = false;

  const token = () => localStorage.getItem('aplus_token') || '';

  function consumeBookLogout() {
    const params = new URLSearchParams(window.location.search || '');
    if (params.get('admin_logout') !== '1') return false;

    localStorage.removeItem('aplus_token');
    sessionStorage.removeItem('aplus_admin_resume');
    adminState = false;
    adminCheck = null;
    redirecting = false;

    params.delete('admin_logout');
    const query = params.toString();
    const clean = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash || ''}`;
    window.history.replaceState(null, '', clean);
    return true;
  }

  const justLoggedOut = consumeBookLogout();

  function blankForAdmin() {
    document.documentElement.classList.add('aplus-admin-transition');
    const app = document.getElementById('app');
    if (app) {
      app.innerHTML = '<main style="min-height:100vh;background:#fff;display:grid;place-items:center"><div style="font:14px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;color:#746e62">Verwaltung wird geöffnet…</div></main>';
    }
  }

  function clearAdminToken() {
    localStorage.removeItem('aplus_token');
    sessionStorage.removeItem('aplus_admin_resume');
    adminState = false;
    adminCheck = null;
    redirecting = false;
  }

  function showAdminGateway() {
    if (!token() || justLoggedOut || redirecting) return;
    document.documentElement.classList.add('aplus-admin-transition');
    const app = document.getElementById('app');
    if (!app) return;
    app.innerHTML = `
      <main style="min-height:100vh;background:#f6f3ec;display:grid;place-items:center;padding:24px;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;color:#29261f">
        <section style="width:min(100%,380px);background:#fff;border:1px solid #e9e1d3;border-radius:22px;padding:28px;box-sizing:border-box;box-shadow:0 16px 50px #6b5a3d14;text-align:center">
          <div style="width:54px;height:54px;margin:0 auto 16px;border-radius:50%;display:grid;place-items:center;background:#d8a73b;color:#fff;font:700 21px Georgia,serif">A+</div>
          <h1 style="font:600 24px Georgia,serif;margin:0 0 8px">Verwaltung</h1>
          <p style="margin:0 0 22px;color:#756f64;font-size:14px;line-height:1.5">Die Admin-Anmeldung ist vorhanden. Die Verwaltung wird aus Sicherheitsgründen nicht automatisch erneut geöffnet.</p>
          <button type="button" data-admin-open style="width:100%;border:0;border-radius:12px;padding:13px 16px;background:#29261f;color:#fff;font-weight:650;cursor:pointer">Verwaltung öffnen</button>
          <button type="button" data-admin-logout style="width:100%;border:0;background:transparent;color:#8a2c23;padding:13px 16px;margin-top:6px;cursor:pointer">Abmelden</button>
        </section>
      </main>`;
    app.querySelector('[data-admin-open]')?.addEventListener('click', () => openExactBookAdmin());
    app.querySelector('[data-admin-logout]')?.addEventListener('click', () => {
      clearAdminToken();
      window.location.reload();
    });
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
    if (!value || justLoggedOut) {
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
        if (adminState) showAdminGateway();
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

  // Install before core-app.js. Existing admin sessions are resolved before the
  // customer surface can call /me. Existing tokens stop at an explicit gateway
  // instead of silently re-entering Book after a logout.
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

    // A fresh admin login is an explicit user action, so it may enter Book directly.
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

  if (!justLoggedOut && token()) void isAdmin();

  window.APlusAdminMode = {
    open: () => openExactBookAdmin(),
    check: () => isAdmin(true),
    logout: () => {
      clearAdminToken();
      window.location.reload();
    },
  };
})();
