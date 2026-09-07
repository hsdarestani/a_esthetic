(() => {
  'use strict';

  const API = 'https://esthetic.smarbiz.sbs/api/mobile';

  function platform() {
    try { return window.Capacitor?.getPlatform?.() || ''; } catch (_) { return ''; }
  }

  function nativeWallet() {
    return window.Capacitor?.Plugins?.CapacitorPassToWallet || null;
  }

  function token() {
    return localStorage.getItem('aplus_token') || '';
  }

  function notice(text) {
    const host = document.querySelector('[data-wallet-notice]');
    if (!host) return;
    host.textContent = text;
    host.hidden = false;
  }

  async function blobToBase64(blob) {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const chunkSize = 0x8000;
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
    }
    return btoa(binary);
  }

  async function addApplePass(button) {
    const plugin = nativeWallet();
    if (!plugin?.addToWallet) return false;

    const original = button.innerHTML;
    button.disabled = true;
    button.classList.add('is-loading');
    try {
      const response = await fetch(`${API}/wallet-pass/apple/`, {
        headers: { Authorization: `Bearer ${token()}` },
        cache: 'no-store',
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || `wallet_http_${response.status}`);
      }

      const blob = await response.blob();
      const base64 = await blobToBase64(blob);
      await plugin.addToWallet({ base64 });
      return true;
    } catch (error) {
      const text = error?.message === 'wallet_provider_not_configured'
        ? 'Apple Wallet ist serverseitig noch nicht eingerichtet.'
        : 'Die A+ Karte konnte gerade nicht zu Apple Wallet hinzugefügt werden.';
      notice(text);
      return true;
    } finally {
      button.disabled = false;
      button.classList.remove('is-loading');
      button.innerHTML = original;
    }
  }

  /*
   * Apple recommends handling .pkpass natively inside WKWebView-based apps.
   * Capture the click before the generic blob-download fallback in focused-upgrade.js.
   */
  document.addEventListener('click', async event => {
    const button = event.target?.closest?.('[data-wallet-provider="apple"]');
    if (!button || platform() !== 'ios' || !nativeWallet()?.addToWallet) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    await addApplePass(button);
  }, true);
})();
