(() => {
  'use strict';

  function markNativePlatform() {
    let value = '';
    try { value = window.Capacitor?.getPlatform?.() || ''; } catch (_) {}
    if (!value && window.Capacitor && /iPhone|iPad|iPod/i.test(navigator.userAgent)) value = 'ios';
    if (!value && window.Capacitor && /Android/i.test(navigator.userAgent)) value = 'android';
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

  function beginLogout(target) {
    const logout = target?.closest?.('[data-logout]');
    if (!logout) return;
    const overlay = logout.closest('.settings-overlay');
    if (overlay) {
      overlay.dataset.nativeClosing = '1';
      overlay.setAttribute('aria-hidden', 'true');
    }
    unlockDocument();
    // Do not prevent or stop the original logout event. Core-app keeps ownership
    // of authentication; this only removes the stale WKWebView sheet afterwards.
    setTimeout(removeSettingsSheets, 0);
    setTimeout(removeSettingsSheets, 120);
  }

  function cleanupIfLoggedOut() {
    const token = localStorage.getItem('aplus_token') || '';
    const loginVisible = Boolean(document.querySelector('.login-shell, [data-login]'));
    if (!token || loginVisible) removeSettingsSheets();
  }

  markNativePlatform();
  document.addEventListener('click', event => beginLogout(event.target), true);
  document.addEventListener('touchend', event => beginLogout(event.target), true);

  const app = document.getElementById('app');
  if (app) {
    new MutationObserver(cleanupIfLoggedOut).observe(app, { childList: true, subtree: true });
  }

  window.addEventListener('pageshow', () => {
    markNativePlatform();
    cleanupIfLoggedOut();
  });
  window.addEventListener('pagehide', removeSettingsSheets);
  setTimeout(cleanupIfLoggedOut, 0);
})();
