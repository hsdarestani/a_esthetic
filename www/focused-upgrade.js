(() => {
  'use strict';

  const API = 'https://esthetic.smarbiz.sbs/api/mobile';
  const token = () => localStorage.getItem('aplus_token') || '';
  let qrObjectUrl = '';

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const money = cents => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format((Number(cents) || 0) / 100);
  const fmt = value => value ? new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—';

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (token()) headers.set('Authorization', `Bearer ${token()}`);
    if (options.json !== undefined) {
      headers.set('Content-Type', 'application/json');
      options.body = JSON.stringify(options.json);
    }
    const response = await fetch(`${API}${path}`, { ...options, headers, cache: 'no-store' });
    const type = response.headers.get('content-type') || '';
    const body = type.includes('application/json') ? await response.json().catch(() => ({})) : null;
    if (!response.ok || body?.ok === false) {
      const error = new Error(body?.error || body?.message || `HTTP ${response.status}`);
      error.status = response.status;
      error.body = body || {};
      throw error;
    }
    return body;
  }

  function upgradeLogin() {
    const logo = document.querySelector('.login-logo');
    if (!logo || logo.dataset.realLogo === '1') return;
    logo.dataset.realLogo = '1';
    logo.innerHTML = '<img class="login-brand-logo" src="./assets/logo.svg" alt="A+ Esthetic"><span>PATIENT APP</span>';
  }

  function upgradeBooking() {
    const main = document.querySelector('.core-main');
    const simpleForm = main?.querySelector('[data-booking]');
    if (!main || !simpleForm || main.dataset.canonicalBook === '1') return;
    main.dataset.canonicalBook = '1';
    main.innerHTML = `
      <div class="canonical-book-intro">
        <span>TERMINBUCHUNG</span>
        <h1>Termin buchen</h1>
        <p>Die Terminbuchung läuft direkt über das zentrale A+ Buchungssystem.</p>
      </div>
      <section class="booking-request-card book-embedded-canonical" aria-label="A+ Terminbuchung">
        <form id="booking-form"></form>
      </section>`;
  }

  function providerButton(provider, info) {
    const isApple = provider === 'apple';
    const label = isApple ? 'Zu Apple Wallet' : 'Zu Google Wallet';
    const icon = isApple ? '' : 'G';
    if (!info?.configured) {
      return `<button type="button" class="wallet-provider is-disabled" disabled><span class="wallet-provider-icon">${icon}</span><span><b>${label}</b><small>Einrichtung noch nicht abgeschlossen</small></span></button>`;
    }
    return `<button type="button" class="wallet-provider" data-wallet-provider="${provider}"><span class="wallet-provider-icon">${icon}</span><span><b>${label}</b><small>Digitale A+ Karte hinzufügen</small></span><i>›</i></button>`;
  }

  function transactionRows(items) {
    const tx = (items || []).filter(item => item.kind === 'credit');
    if (!tx.length) return '<div class="empty">Noch keine Guthabenbewegungen.</div>';
    return tx.map(item => {
      const incoming = item.direction === 'in' || item.direction === 'credit';
      const amount = Math.abs(Number(item.amount_cents) || 0);
      return `<article class="wallet-ledger-row">
        <div class="wallet-ledger-mark ${incoming ? 'is-in' : 'is-out'}">${incoming ? '+' : '−'}</div>
        <div class="wallet-ledger-copy"><strong>${esc(item.description || 'A+ Guthaben')}</strong><span>${fmt(item.created_at)}</span></div>
        <div class="wallet-ledger-amount ${incoming ? 'plus' : 'minus'}">${incoming ? '+' : '−'} ${money(amount)}</div>
      </article>`;
    }).join('');
  }

  async function loadQr(img, fallback) {
    try {
      const response = await fetch(`${API}/wallet-pass/qr/`, {
        headers: { Authorization: `Bearer ${token()}` },
        cache: 'no-store',
      });
      if (!response.ok) throw new Error('qr_failed');
      const blob = await response.blob();
      if (qrObjectUrl) URL.revokeObjectURL(qrObjectUrl);
      qrObjectUrl = URL.createObjectURL(blob);
      img.src = qrObjectUrl;
      img.hidden = false;
      fallback.hidden = true;
    } catch (_) {
      img.hidden = true;
      fallback.hidden = false;
    }
  }

  async function openWalletProvider(provider, button) {
    const original = button.innerHTML;
    button.disabled = true;
    button.classList.add('is-loading');
    try {
      if (provider === 'apple') {
        const response = await fetch(`${API}/wallet-pass/apple/`, {
          headers: { Authorization: `Bearer ${token()}` },
          cache: 'no-store',
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.error || 'wallet_generation_failed');
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'A-Plus-Esthetic.pkpass';
        a.rel = 'noopener';
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      } else {
        const data = await api('/wallet-pass/google/');
        if (!data?.save_url) throw new Error('wallet_generation_failed');
        window.open(data.save_url, '_blank', 'noopener');
      }
    } catch (error) {
      const text = error.message === 'wallet_provider_not_configured'
        ? 'Wallet-Anbieter ist serverseitig noch nicht eingerichtet.'
        : 'Die digitale Karte konnte gerade nicht erstellt werden.';
      showWalletNotice(text);
    } finally {
      button.disabled = false;
      button.classList.remove('is-loading');
      button.innerHTML = original;
    }
  }

  function showWalletNotice(text) {
    const host = document.querySelector('[data-wallet-notice]');
    if (!host) return;
    host.textContent = text;
    host.hidden = false;
  }

  async function upgradeWallet() {
    const main = document.querySelector('.core-main');
    const currentWallet = main?.querySelector('.wallet-hero');
    if (!main || !currentWallet || main.dataset.samsWallet === '1') return;
    main.dataset.samsWallet = '1';
    main.innerHTML = '<div class="wallet-upgrade-loading"><div class="spinner"></div><span>A+ Wallet wird geladen …</span></div>';

    try {
      const [wallet, pass] = await Promise.all([api('/wallet/'), api('/wallet-pass/')]);
      const card = pass.card || {};
      const providers = pass.providers || {};
      const initials = String(card.name || 'A+').split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
      main.innerHTML = `
        <div class="wallet-page-head">
          <span>A+ WALLET</span>
          <h1>Ihre digitale A+ Karte</h1>
          <p>Guthaben, Mitgliedskarte und QR-Code an einem Ort.</p>
        </div>

        <section class="aplus-member-card">
          <div class="member-card-glow"></div>
          <div class="member-card-top">
            <img src="./assets/logo.svg" alt="A+ Esthetic" class="member-card-logo">
            <span class="member-card-tier">${esc(card.tier || 'A+ Member')}</span>
          </div>
          <div class="member-card-name"><small>MITGLIED</small><strong>${esc(card.name || '')}</strong></div>
          <div class="member-card-bottom">
            <div><small>A+ GUTHABEN</small><strong>${money(card.credit_cents ?? wallet.balance_cents)}</strong></div>
            <div class="member-card-number"><small>MITGLIEDSNUMMER</small><strong>${esc(card.member_number || '—')}</strong></div>
          </div>
        </section>

        <section class="wallet-identity-panel">
          <div class="wallet-qr-wrap">
            <div class="wallet-qr-frame"><img data-wallet-qr alt="A+ Wallet QR-Code" hidden><div data-wallet-qr-fallback class="wallet-qr-fallback">${esc(initials || 'A+')}</div></div>
            <div><span>Persönlicher QR-Code</span><strong>In der Praxis vorzeigen</strong><small>Der QR-Code identifiziert nur Ihre A+ Karte.</small></div>
          </div>
          <div class="wallet-provider-grid">
            ${providerButton('apple', providers.apple)}
            ${providerButton('google', providers.google)}
          </div>
          <div class="wallet-provider-notice" data-wallet-notice hidden></div>
        </section>

        <div class="section-title wallet-history-title"><h2>Guthabenverlauf</h2><small>${(wallet.transactions || []).filter(item => item.kind === 'credit').length}</small></div>
        <section class="wallet-ledger">${transactionRows(wallet.transactions)}</section>
        <p class="wallet-legal-note">${esc(pass.note || 'Die A+ Mitgliedskarte ist keine Zahlungskarte.')}</p>`;

      const img = main.querySelector('[data-wallet-qr]');
      const fallback = main.querySelector('[data-wallet-qr-fallback]');
      loadQr(img, fallback);
      main.querySelectorAll('[data-wallet-provider]').forEach(button => {
        button.addEventListener('click', () => openWalletProvider(button.dataset.walletProvider, button));
      });
    } catch (error) {
      main.innerHTML = `<div class="notice error">A+ Wallet konnte nicht geladen werden. ${esc(error.message)}</div>`;
    }
  }

  function run() {
    upgradeLogin();
    upgradeBooking();
    upgradeWallet();
  }

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', run);
  window.addEventListener('pagehide', () => { if (qrObjectUrl) URL.revokeObjectURL(qrObjectUrl); });
  setTimeout(run, 0);
})();