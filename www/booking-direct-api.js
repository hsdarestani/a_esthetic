(() => {
  'use strict';

  const CLUB_ORIGIN = 'https://esthetic.smarbiz.sbs';
  const CLUB_API_PREFIX = '/api/mobile';
  const BOOKING_API_BASE = 'https://book.a-esthetic.de/api/mobile';
  const nativeFetch = window.fetch.bind(window);

  function isBookingPath(pathname) {
    if (!pathname.startsWith(CLUB_API_PREFIX)) return false;
    const mobilePath = pathname.slice(CLUB_API_PREFIX.length) || '/';
    return mobilePath === '/booking'
      || mobilePath.startsWith('/booking/')
      || mobilePath === '/slots'
      || mobilePath.startsWith('/slots/');
  }

  function rewriteUrl(value) {
    try {
      const url = new URL(value, window.location.href);
      if (url.origin !== CLUB_ORIGIN || !isBookingPath(url.pathname)) return value;
      const mobilePath = url.pathname.slice(CLUB_API_PREFIX.length);
      return `${BOOKING_API_BASE}${mobilePath}${url.search}${url.hash}`;
    } catch (_) {
      return value;
    }
  }

  window.fetch = (input, init) => {
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
  });
})();
