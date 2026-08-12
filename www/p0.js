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

  function toLocalInput(iso) {
    const d = new Date(iso);
    const pad = value => String(value).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function enhanceBooking() {
    const form = document.getElementById('booking-form');
    if (!form || form.dataset.p0Enhanced === '1') return;
    form.dataset.p0Enhanced = '1';

    const service = form.querySelector('[name="service_id"]');
    const staff = form.querySelector('[name="staff_id"]');
    const startsAt = form.querySelector('[name="starts_at"]');
    if (!service || !staff || !startsAt) return;

    const originalLabel = startsAt.closest('label');
    startsAt.type = 'hidden';
    originalLabel.childNodes.forEach(node => {
      if (node.nodeType === Node.TEXT_NODE) node.textContent = '';
    });

    const dateLabel = document.createElement('label');
    dateLabel.textContent = 'Datum';
    const day = document.createElement('input');
    day.type = 'date';
    day.required = true;
    const minDate = new Date();
    minDate.setHours(0, 0, 0, 0);
    day.min = minDate.toISOString().slice(0, 10);
    dateLabel.appendChild(day);

    const slotLabel = document.createElement('label');
    slotLabel.textContent = 'Freie Zeit';
    const slots = document.createElement('select');
    slots.required = true;
    slots.innerHTML = '<option value="">Zuerst Leistung, Team und Datum wählen</option>';
    slotLabel.appendChild(slots);

    originalLabel.parentNode.insertBefore(dateLabel, originalLabel);
    originalLabel.parentNode.insertBefore(slotLabel, originalLabel);
    originalLabel.style.display = 'none';

    async function loadSlots() {
      startsAt.value = '';
      if (!service.value || !staff.value || !day.value) {
        slots.innerHTML = '<option value="">Zuerst Leistung, Team und Datum wählen</option>';
        return;
      }
      slots.disabled = true;
      slots.innerHTML = '<option value="">Freie Zeiten werden geladen…</option>';
      try {
        const data = await p0Api(`/slots/?service_id=${encodeURIComponent(service.value)}&staff_id=${encodeURIComponent(staff.value)}&day=${encodeURIComponent(day.value)}`);
        slots.innerHTML = data.slots.length
          ? '<option value="">Freie Zeit wählen</option>' + data.slots.map(iso => {
              const d = new Date(iso);
              return `<option value="${iso}">${new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit' }).format(d)}</option>`;
            }).join('')
          : '<option value="">An diesem Tag keine freie Zeit</option>';
      } catch (_) {
        slots.innerHTML = '<option value="">Freie Zeiten konnten nicht geladen werden</option>';
      } finally {
        slots.disabled = false;
      }
    }

    service.addEventListener('change', loadSlots);
    staff.addEventListener('change', loadSlots);
    day.addEventListener('change', loadSlots);
    slots.addEventListener('change', () => {
      startsAt.value = slots.value ? toLocalInput(slots.value) : '';
    });

    const hint = document.createElement('div');
    hint.className = 'notice';
    hint.style.marginBottom = '12px';
    hint.textContent = 'Es werden nur tatsächlich freie Zeiten innerhalb der A+ Arbeitszeiten angezeigt.';
    form.parentNode.insertBefore(hint, form);
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
    enhanceBooking();
    enhanceProfile();
  }

  const observer = new MutationObserver(enhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', enhance);
  setTimeout(enhance, 0);
})();
