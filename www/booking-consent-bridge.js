(() => {
  'use strict';

  const API = 'https://esthetic.smarbiz.sbs/api/mobile';
  const previousFetch = window.fetch.bind(window);
  let pendingConsent = null;

  function token() {
    return localStorage.getItem('aplus_token') || '';
  }

  function capture(form) {
    const data = new FormData(form);
    pendingConsent = {
      marketing_opt_in: data.get('marketing') === 'on',
      cancellation_terms_accepted: data.get('terms') === 'on',
      privacy_accepted: data.get('privacy') === 'on',
      phone: String(data.get('phone') || '').trim(),
      captured_at: Date.now(),
    };
  }

  document.addEventListener('submit', event => {
    const form = event.target?.closest?.('[data-confirm-form]');
    if (form) capture(form);
  }, true);

  async function persistProfile(consent) {
    if (!consent || !token()) return;
    const response = await previousFetch(`${API}/profile/`, {
      method: 'POST',
      cache: 'no-store',
      headers: {
        'Authorization': `Bearer ${token()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        phone: consent.phone,
        marketing_consent: consent.marketing_opt_in,
      }),
    });
    if (!response.ok && response.status !== 401) {
      throw new Error(`profile_consent_http_${response.status}`);
    }
  }

  window.fetch = async function consentAwareFetch(input, init = {}) {
    const url = typeof input === 'string' ? input : (input?.url || '');
    const method = String(init?.method || input?.method || 'GET').toUpperCase();
    const isBookingPost = method === 'POST' && url.startsWith(API) && /\/booking\/?(?:[?#].*)?$/.test(url);
    if (!isBookingPost) return previousFetch(input, init);

    const consent = pendingConsent && Date.now() - pendingConsent.captured_at < 60_000
      ? pendingConsent
      : null;
    if (!consent) return previousFetch(input, init);

    // The visible form requires terms and privacy. Keep the transport defensive
    // so a programmatic submit can never silently record missing legal consent.
    if (!consent.cancellation_terms_accepted || !consent.privacy_accepted) {
      throw new Error('booking_consent_required');
    }

    await persistProfile(consent);

    let payload = {};
    try {
      payload = typeof init.body === 'string' ? JSON.parse(init.body) : {};
    } catch (_) {}
    payload.marketing_opt_in = consent.marketing_opt_in;
    payload.cancellation_terms_accepted = consent.cancellation_terms_accepted;
    payload.privacy_accepted = consent.privacy_accepted;
    payload.consent_acknowledged = consent.cancellation_terms_accepted && consent.privacy_accepted;

    const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
    headers.set('Content-Type', 'application/json');
    const nextInit = { ...init, headers, body: JSON.stringify(payload) };
    try {
      return await previousFetch(input, nextInit);
    } finally {
      pendingConsent = null;
    }
  };
})();
