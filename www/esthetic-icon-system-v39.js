/* A+ Esthetic signature icon set: warm, optical-weighted, unified 24px symbols.
   One source for tabs, shortcuts, membership actions and customer dashboard. */
(() => {
  'use strict';
  const svg = inner => '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + inner + '</svg>';
  const icons = {
    dashboard: svg('<path d="M3.5 10.7 12 4l8.5 6.7v8.4a1.9 1.9 0 0 1-1.9 1.9H5.4a1.9 1.9 0 0 1-1.9-1.9Z" fill="currentColor" fill-opacity=".10"/><path d="M9.2 21v-7.5h5.6V21"/><path d="M2.5 11.4 12 3.8l9.5 7.6"/>'),
    appointments: svg('<rect x="3.6" y="5.5" width="16.8" height="15.1" rx="3.1" fill="currentColor" fill-opacity=".10"/><path d="M7.8 3.6v4M16.2 3.6v4M3.6 10h16.8"/><path d="m9.2 15.4 1.9 2 4.1-4.4"/>'),
    records: svg('<path d="M5.3 4.2h9.4l4 4v11.4a1.7 1.7 0 0 1-1.7 1.7H7a1.7 1.7 0 0 1-1.7-1.7Z" fill="currentColor" fill-opacity=".10"/><path d="M14.7 4.2v4h4M9 12.7h6.2M9 16.2h6.2"/>'),
    points: svg('<circle cx="12" cy="12" r="9.1" fill="currentColor" fill-opacity=".10"/><path d="m12 6.3 1.45 4.1L17.5 12l-4.05 1.6L12 17.7l-1.45-4.1L6.5 12l4.05-1.6Z" fill="currentColor" stroke="none"/><path d="M19.6 4.3v3.1M18.05 5.85h3.1" stroke-width="1.4"/>'),
    friends: svg('<circle cx="9" cy="8.3" r="3.15" fill="currentColor" fill-opacity=".12"/><path d="M3.5 20v-1.8a5.5 5.5 0 0 1 11 0V20Z"/><path d="M16 6.3c1.9.15 3.2 1.5 3.2 3.3 0 1.8-1.3 3.1-3.2 3.3M17 15.1c2.2.5 3.5 1.9 3.5 4.2"/>'),
    settings: svg('<circle cx="12" cy="12" r="8.8" stroke-opacity=".55"/><path d="M12 5.1v1.6M12 17.3v1.6M5.1 12h1.6M17.3 12h1.6M7.12 7.12l1.15 1.15M15.73 15.73l1.15 1.15M16.88 7.12l-1.15 1.15M8.27 15.73l-1.15 1.15"/><circle cx="12" cy="12" r="3.1" fill="currentColor" fill-opacity=".13"/>'),
    phone: svg('<path d="m7 3.7 3 4.5-2 1.9a14.2 14.2 0 0 0 5.8 5.8l1.9-2 4.6 3c.4.3.6.8.4 1.3a3.8 3.8 0 0 1-3.8 2.6A14.7 14.7 0 0 1 3.2 7.2a3.8 3.8 0 0 1 2.5-3.8c.5-.2 1-.1 1.3.3Z" fill="currentColor" fill-opacity=".10"/>'),
    instagram: svg('<rect x="3.3" y="3.3" width="17.4" height="17.4" rx="5.4" fill="currentColor" fill-opacity=".09"/><circle cx="12" cy="12" r="4"/><circle cx="17.3" cy="6.8" r=".95" fill="currentColor" stroke="none"/>'),
    directions: svg('<path d="M12 21.4s-6.2-5-6.2-11.3a6.2 6.2 0 0 1 12.4 0C18.2 16.4 12 21.4 12 21.4Z" fill="currentColor" fill-opacity=".10"/><circle cx="12" cy="10" r="2.3"/>'),
    membership: svg('<rect x="2.7" y="5" width="18.6" height="14.2" rx="3.1" fill="currentColor" fill-opacity=".12"/><path d="M2.7 9.4h18.6M6.8 15.2h4.4"/><path d="m16.9 12.9.6 1.8 1.8.6-1.8.6-.6 1.8-.6-1.8-1.8-.6 1.8-.6Z" fill="currentColor" stroke="none"/>'),
    benefits: svg('<path d="m12 2.8 1.9 6.9L21 12l-7.1 2.3L12 21.2l-1.9-6.9L3 12l7.1-2.3Z" fill="currentColor" fill-opacity=".16"/><circle cx="12" cy="12" r="2.2" fill="currentColor" stroke="none"/>'),
    review: svg('<path d="M4.3 5.1h15.4v11.2H9l-4.7 3.8V5.1Z" fill="currentColor" fill-opacity=".10"/><path d="m12 7.5 1.1 2.5 2.7.3-2.1 1.8.6 2.6-2.3-1.4-2.3 1.4.6-2.6-2.1-1.8 2.7-.3Z" stroke-width="1.35"/>'),
    google: svg('<circle cx="12" cy="12" r="8.3" stroke-opacity=".45"/><path d="M19.6 12h-7.4M16.9 12c0 3.1-1.9 4.9-4.9 4.9a5 5 0 0 1 0-9.8c1.4 0 2.5.5 3.4 1.4"/>')
  };
  window.AEstheticIconSet = Object.freeze(icons);
})();
