(() => {
  'use strict';

  // Build 6 introduced the native PushNotifications plugin before the Android
  // Firebase application was provisioned. ops.js enhances the DOM through a
  // MutationObserver and can consequently ask the native bridge to register
  // more than once during a single session. On affected Android WebViews this
  // can destabilize the process. Keep Android registration disabled until a
  // real google-services/Firebase setup is shipped in a later native build.
  function guardAndroidPush() {
    const cap = window.Capacitor;
    const plugin = cap?.Plugins?.PushNotifications;
    const platform = typeof cap?.getPlatform === 'function' ? cap.getPlatform() : '';
    if (!plugin || platform !== 'android' || plugin.__aestheticSafeGuard === true) return;

    plugin.__aestheticSafeGuard = true;
    plugin.register = async () => ({ disabled: true, reason: 'firebase_not_provisioned' });
  }

  guardAndroidPush();
  window.addEventListener('DOMContentLoaded', guardAndroidPush, { once: true });

  const bellSvg = `
    <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/>
      <path d="M10 21h4"/>
    </svg>`;

  function fixNotificationChrome() {
    const functional = document.querySelector('.topbar .ops-bell');
    const decorative = document.querySelector('.topbar .luxury-bell:not(.ops-bell)');

    if (functional && functional.dataset.runtimeBell !== '1') {
      functional.dataset.runtimeBell = '1';
      functional.classList.add('runtime-notification-bell');
      functional.innerHTML = `${bellSvg}<span class="notification-dot runtime-dot" hidden></span>`;
      functional.setAttribute('aria-label', 'Benachrichtigungen');
    }
    if (decorative) {
      decorative.setAttribute('aria-hidden', 'true');
      decorative.tabIndex = -1;
      decorative.classList.add('runtime-hidden-bell');
    }
  }

  let queued = false;
  const schedule = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      guardAndroidPush();
      fixNotificationChrome();
    });
  };

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', schedule, { once: true });
  setTimeout(schedule, 0);
})();
