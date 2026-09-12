(() => {
  'use strict';

  const root = document.documentElement;

  function visible(element) {
    if (!element || !element.isConnected) return false;
    const style = getComputedStyle(element);
    return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) !== 0 && element.getClientRects().length > 0;
  }

  function nativePlatform() {
    let value = '';
    try { value = window.Capacitor?.getPlatform?.() || ''; } catch (_) {}
    if (!value && window.Capacitor && /Android/i.test(navigator.userAgent)) value = 'android';
    if (!value && window.Capacitor && /iPhone|iPad|iPod/i.test(navigator.userAgent)) value = 'ios';
    return value === 'android' || value === 'ios' ? value : '';
  }

  function neutralizeClosedLayers() {
    document.querySelectorAll('.settings-overlay[aria-hidden="true"], .overlay[aria-hidden="true"], .modal[aria-hidden="true"], .sheet[aria-hidden="true"]').forEach(layer => {
      layer.style.pointerEvents = 'none';
    });
  }

  function recoverScroll() {
    neutralizeClosedLayers();
    if (!document.body) return;

    for (const node of [root, document.body]) {
      node.style.removeProperty('height');
      node.style.removeProperty('max-height');
      node.style.removeProperty('position');
      node.style.removeProperty('top');
      node.style.removeProperty('bottom');
      node.style.removeProperty('touch-action');
      node.style.setProperty('overflow-x', 'hidden', 'important');
      node.style.setProperty('overflow-y', 'auto', 'important');
      node.style.setProperty('touch-action', 'auto', 'important');
    }

    for (const node of [document.getElementById('app'), document.querySelector('.core-shell'), document.querySelector('.core-main')]) {
      if (!node) continue;
      node.style.removeProperty('height');
      node.style.removeProperty('max-height');
      node.style.removeProperty('position');
      node.style.removeProperty('top');
      node.style.setProperty('overflow-y', 'visible', 'important');
      node.style.setProperty('touch-action', 'auto', 'important');
    }

    document.body.classList.remove('no-scroll', 'scroll-lock', 'scroll-locked', 'modal-open', 'is-locked');
    root.classList.remove('no-scroll', 'scroll-lock', 'scroll-locked', 'modal-open', 'is-locked');
    if (nativePlatform()) root.classList.add('aplus-native-scroll-ready');
  }

  let queued = false;
  function queueRecovery() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      recoverScroll();
    });
  }

  recoverScroll();
  document.addEventListener('DOMContentLoaded', recoverScroll, { once: true });
  window.addEventListener('pageshow', recoverScroll);
  window.addEventListener('focus', recoverScroll);
  window.addEventListener('hashchange', recoverScroll);
  window.addEventListener('resize', queueRecovery, { passive: true });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) recoverScroll(); });
  document.addEventListener('click', queueRecovery, true);
  document.addEventListener('touchend', queueRecovery, { capture: true, passive: true });

  const app = document.getElementById('app');
  if (app) new MutationObserver(queueRecovery).observe(app, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'aria-hidden', 'style'] });

  [0, 80, 250, 600, 1200, 2500].forEach(delay => setTimeout(recoverScroll, delay));
})();
