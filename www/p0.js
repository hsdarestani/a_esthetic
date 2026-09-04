(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const AUTH_BASE = 'https://esthetic.smarbiz.sbs/accounts';

  function token() {
    return localStorage.getItem('aplus_token') || '';
  }

  async function p0Api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) {
      const error = new Error(body.error || 'request_failed');
      error.status = response.status;
      throw error;
    }
    return body;
  }

  function enhanceLogin() {
    const card = document.querySelector('.auth-card');
    if (!card || card.querySelector('.p0-auth-actions')) return;
    const legal = card.querySelector('.legal-links');
    if (!legal) return;
    const row = document.createElement('div');
    row.className = 'p0-auth-actions';
    row.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0;';
    row.innerHTML = `
      <a class="btn ghost" href="${AUTH_BASE}/signup/" target="_blank" rel="noopener">Konto erstellen</a>
      <a class="btn ghost" href="${AUTH_BASE}/password/reset/" target="_blank" rel="noopener">Passwort vergessen</a>`;
    legal.parentNode.insertBefore(row, legal);
  }

  async function enhanceProfile() {
    const profileForm = document.getElementById('profile-form');
    if (!profileForm || document.getElementById('p0-privacy-tools')) return;
    const cards = document.querySelectorAll('.content .card');
    const anchor = cards[cards.length - 1] || profileForm.closest('.card');

    const card = document.createElement('section');
    card.className = 'card';
    card.id = 'p0-privacy-tools';
    card.innerHTML = `
      <h2>Geräte & Daten</h2>
      <p class="muted">Aktive Sitzungen verwalten oder eine Datenkopie Ihres Customer-Club-Kontos erstellen.</p>
      <div id="p0-devices"><p class="empty">Geräte werden geladen…</p></div>
      <div class="actions">
        <button class="btn ghost" type="button" id="p0-export">Datenkopie herunterladen</button>
      </div>`;
    anchor.insertAdjacentElement('afterend', card);

    try {
      const data = await p0Api('/devices/');
      const target = card.querySelector('#p0-devices');
      target.innerHTML = data.devices.length ? data.devices.map(device => `
        <div class="row">
          <div class="row-main">
            <b>${device.current ? 'Dieses Gerät' : 'Gerät'}</b>
            <small>${device.device_name || 'A+ Esthetic App'} · ${new Date(device.last_seen_at).toLocaleString('de-DE')}</small>
          </div>
          ${device.revoked_at ? '<span class="badge">Abgemeldet</span>' : `<button class="btn ghost" type="button" data-p0-revoke="${device.id}">Abmelden</button>`}
        </div>`).join('') : '<p class="empty">Keine aktiven Geräte gefunden.</p>';

      target.querySelectorAll('[data-p0-revoke]').forEach(button => button.addEventListener('click', async () => {
        if (!confirm('Diese Gerätesitzung wirklich abmelden?')) return;
        try {
          await p0Api(`/devices/${button.dataset.p0Revoke}/revoke/`, { method: 'POST', body: '{}' });
          if (button.closest('.row')?.querySelector('b')?.textContent === 'Dieses Gerät') {
            localStorage.removeItem('aplus_token');
            location.reload();
            return;
          }
          button.textContent = 'Abgemeldet';
          button.disabled = true;
        } catch (_) {
          alert('Die Gerätesitzung konnte nicht abgemeldet werden.');
        }
      }));
    } catch (_) {
      card.querySelector('#p0-devices').innerHTML = '<p class="empty">Geräte konnten nicht geladen werden.</p>';
    }

    card.querySelector('#p0-export')?.addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = 'Daten werden erstellt…';
      try {
        const response = await fetch(`${API_BASE}/export/`, {
          headers: { Authorization: `Bearer ${token()}` },
        });
        if (!response.ok) throw new Error('export_failed');
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'a-plus-esthetic-daten.json';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
      } catch (_) {
        alert('Die Datenkopie konnte nicht erstellt werden.');
      } finally {
        button.disabled = false;
        button.textContent = 'Datenkopie herunterladen';
      }
    });
  }

  function enhance() {
    enhanceLogin();
    enhanceProfile();
  }

  const observer = new MutationObserver(enhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', enhance);
  setTimeout(enhance, 0);
})();
