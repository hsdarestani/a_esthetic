(() => {
  'use strict';

  const LOGO = './assets/logo.svg';
  let queued = false;

  const logoImg = (cls = 'official-brand-logo') => {
    const img = document.createElement('img');
    img.src = LOGO;
    img.alt = 'A+ Esthetic';
    img.className = cls;
    img.dataset.officialLogo = '1';
    img.decoding = 'async';
    return img;
  };

  function fillHost(host, extraClass = '') {
    if (!host || host.querySelector('img[data-official-logo="1"]')) return;
    host.textContent = '';
    host.classList.add('official-logo-host');
    if (extraClass) host.classList.add(extraClass);
    host.appendChild(logoImg());
  }

  function protectBookingClicks() {
    const form = document.getElementById('booking-form');
    if (!form || form.dataset.doctolibFlow !== '1') return;

    document.querySelectorAll('.service-sheet').forEach(sheet => sheet.remove());
    document.body.classList.remove('service-sheet-open');

    const layer = form.querySelector('[data-confirm-layer]');
    if (layer?.hidden) {
      layer.style.display = 'none';
      layer.style.pointerEvents = 'none';
    } else if (layer) {
      layer.style.removeProperty('display');
      layer.style.removeProperty('pointer-events');
    }
  }

  function applyOfficialLogo() {
    // The full 1024×1024 brand artwork is only suitable for dedicated logo hosts.
    // Do not inject it into tiny decorative lotus/nav hosts: Android WebView can
    // render the intrinsic SVG size outside those containers and cover the page.
    document.querySelectorAll('.brandmark').forEach(node => fillHost(node));
    document.querySelectorAll('.boot-logo').forEach(node => fillHost(node));
    protectBookingClicks();
  }

  function schedule() {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      applyOfficialLogo();
    });
  }

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', applyOfficialLogo);
  setTimeout(applyOfficialLogo, 0);
})();
