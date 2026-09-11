(() => {
  'use strict';

  function nativePlatform() {
    let value = '';
    try { value = window.Capacitor?.getPlatform?.() || ''; } catch (_) {}
    if (!value && window.Capacitor && /iPhone|iPad|iPod/i.test(navigator.userAgent)) value = 'ios';
    if (!value && window.Capacitor && /Android/i.test(navigator.userAgent)) value = 'android';
    return value === 'ios' || value === 'android' ? value : '';
  }

  function markNativePlatform() {
    const value = nativePlatform();
    if (value) document.documentElement.classList.add(`aplus-${value}`);
  }

  function unlockDocument() {
    document.documentElement.style.overflow = '';
    document.body.style.overflow = '';
    document.documentElement.classList.add('native-sheet-reset');
    requestAnimationFrame(() => document.documentElement.classList.remove('native-sheet-reset'));
  }

  function removeSettingsSheets() {
    document.querySelectorAll('.settings-overlay').forEach(overlay => {
      overlay.dataset.nativeClosing = '1';
      overlay.setAttribute('aria-hidden', 'true');
      requestAnimationFrame(() => overlay.remove());
    });
    unlockDocument();
  }

  function beginLogout(target, eventType = 'click') {
    // This workaround only belongs to the Capacitor WebView. On normal mobile web,
    // removing the settings sheet on touchend can delete the logout button before
    // the browser dispatches its synthetic click, leaving the user logged in.
    if (!nativePlatform()) return;

    const logout = target?.closest?.('[data-logout]');
    if (!logout) return;

    unlockDocument();

    if (eventType === 'touchend') {
      // Keep the target alive long enough for core-app's click handler to clear the
      // token and render the login screen. Cleanup is only a native fallback.
      setTimeout(removeSettingsSheets, 400);
      return;
    }

    const overlay = logout.closest('.settings-overlay');
    if (overlay) {
      overlay.dataset.nativeClosing = '1';
      overlay.setAttribute('aria-hidden', 'true');
    }
    // Click propagation is synchronous, so core-app owns the actual logout first.
    setTimeout(removeSettingsSheets, 0);
    setTimeout(removeSettingsSheets, 120);
  }

  function cleanupIfLoggedOut() {
    const token = localStorage.getItem('aplus_token') || '';
    const loginVisible = Boolean(document.querySelector('.login-shell, [data-login]'));
    if (!token || loginVisible) removeSettingsSheets();
  }

  markNativePlatform();
  document.addEventListener('click', event => beginLogout(event.target, 'click'), true);
  document.addEventListener('touchend', event => beginLogout(event.target, 'touchend'), true);

  const app = document.getElementById('app');
  if (app) {
    new MutationObserver(cleanupIfLoggedOut).observe(app, { childList: true, subtree: true });
  }

  window.addEventListener('pageshow', () => {
    markNativePlatform();
    cleanupIfLoggedOut();
  });
  window.addEventListener('pagehide', () => {
    if (nativePlatform()) removeSettingsSheets();
  });
  setTimeout(cleanupIfLoggedOut, 0);
})();
