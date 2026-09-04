(() => {
  'use strict';

  const CLUB_ORIGIN = 'https://esthetic.smarbiz.sbs';
  const CLUB_API_PREFIX = '/api/mobile';
  const BOOKING_API_BASE = 'https://book.a-esthetic.de/api/mobile';
  const nativeFetch = window.fetch.bind(window);

  function parsed(value) {
    try { return new URL(value, window.location.href); } catch (_) { return null; }
  }

  function isBookingPath(pathname) {
    if (!pathname.startsWith(CLUB_API_PREFIX)) return false;
    const mobilePath = pathname.slice(CLUB_API_PREFIX.length) || '/';
    return mobilePath === '/booking'
      || mobilePath.startsWith('/booking/')
      || mobilePath === '/slots'
      || mobilePath.startsWith('/slots/');
  }

  function isDashboard(value) {
    const url = parsed(value);
    return !!url && url.origin === CLUB_ORIGIN && url.pathname === `${CLUB_API_PREFIX}/dashboard/`;
  }

  function rewriteUrl(value) {
    const url = parsed(value);
    if (!url || url.origin !== CLUB_ORIGIN || !isBookingPath(url.pathname)) return value;
    const mobilePath = url.pathname.slice(CLUB_API_PREFIX.length);
    return `${BOOKING_API_BASE}${mobilePath}${url.search}${url.hash}`;
  }

  function responseWithJson(source, body) {
    const headers = new Headers(source.headers);
    headers.set('Content-Type', 'application/json; charset=utf-8');
    headers.delete('Content-Length');
    return new Response(JSON.stringify(body), {
      status: source.status,
      statusText: source.statusText,
      headers,
    });
  }

  async function dashboardFromCanonicalBooking(input, init) {
    const localPromise = nativeFetch(input, init);
    const bookingPromise = nativeFetch(`${BOOKING_API_BASE}/booking/`, init).catch(() => null);
    const [localResponse, bookingResponse] = await Promise.all([localPromise, bookingPromise]);
    if (!localResponse.ok || !bookingResponse || !bookingResponse.ok) return localResponse;

    try {
      const [localBody, bookingBody] = await Promise.all([
        localResponse.clone().json(),
        bookingResponse.json(),
      ]);
      if (bookingBody?.ok) {
        const next = bookingBody.next_appointment || null;
        localBody.next_appointment = next ? {
          id: next.id,
          title: next.service,
          service: next.service,
          staff: next.staff,
          starts_at: next.starts_at,
          status: next.status,
          status_code: next.status_code,
          source: 'book',
        } : null;
        localBody.appointments_source = 'book';
      }
      return responseWithJson(localResponse, localBody);
    } catch (_) {
      return localResponse;
    }
  }

  window.fetch = (input, init) => {
    const rawUrl = typeof input === 'string' || input instanceof URL ? String(input) : input?.url;
    if (rawUrl && isDashboard(rawUrl)) {
      return dashboardFromCanonicalBooking(input, init);
    }

    if (typeof input === 'string' || input instanceof URL) {
      return nativeFetch(rewriteUrl(String(input)), init);
    }
    if (typeof Request !== 'undefined' && input instanceof Request) {
      const nextUrl = rewriteUrl(input.url);
      if (nextUrl !== input.url) {
        return nativeFetch(new Request(nextUrl, input), init);
      }
    }
    return nativeFetch(input, init);
  };

  window.APlusBookingApi = Object.freeze({
    baseUrl: BOOKING_API_BASE,
    source: 'book',
    direct: true,
    homeAppointments: true,
  });
})();
