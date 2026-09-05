(() => {
  'use strict';

  // The More/Profile surface is observed by several UI enhancers. Without a guard,
  // each DOM mutation can start another /admin/ probe before the first one returns,
  // which floods the browser and makes the Profile tab look frozen.
  const nativeFetch = window.fetch.bind(window);
  let adminProbeInFlight = false;

  const requestUrl = input => {
    if (typeof input === 'string') return input;
    return input?.url || '';
  };

  const requestMethod = (input, init = {}) => String(init.method || input?.method || 'GET').toUpperCase();

  window.fetch = async function guardedFetch(input, init = {}) {
    const url = requestUrl(input);
    const method = requestMethod(input, init);

    if (method === 'GET' && url.includes('/api/mobile/admin/')) {
      if (adminProbeInFlight) {
        return new Response(JSON.stringify({ ok: false, error: 'admin_check_in_progress' }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      adminProbeInFlight = true;
      try {
        return await nativeFetch(input, init);
      } finally {
        adminProbeInFlight = false;
      }
    }

    // Never leave the real profile request spinning forever on a bad connection.
    if (method === 'GET' && url.includes('/api/mobile/profile/')) {
      let timeoutId;
      try {
        return await Promise.race([
          nativeFetch(input, init),
          new Promise((_, reject) => {
            timeoutId = setTimeout(() => reject(new Error('profile_request_timeout')), 10000);
          }),
        ]);
      } finally {
        clearTimeout(timeoutId);
      }
    }

    return nativeFetch(input, init);
  };

  function keepSingle(selector) {
    const nodes = [...document.querySelectorAll(selector)];
    nodes.slice(1).forEach(node => node.remove());
  }

  let cleanupQueued = false;
  function cleanup() {
    if (cleanupQueued) return;
    cleanupQueued = true;
    requestAnimationFrame(() => {
      cleanupQueued = false;
      keepSingle('[data-ops-admin]');
      keepSingle('[data-ops-center]');
    });
  }

  const observer = new MutationObserver(cleanup);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', cleanup);
})();
