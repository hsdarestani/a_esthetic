(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const token = () => localStorage.getItem('aplus_token') || '';
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const fmt = value => new Intl.DateTimeFormat('de-DE', {
    weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
  }).format(new Date(value));

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) {
      const error = new Error(body.message || body.error || 'Die Aktion konnte nicht durchgeführt werden.');
      error.code = body.error;
      throw error;
    }
    return body;
  }

  function target() {
    const form = document.getElementById('booking-form');
    if (!form) return null;
    return form.closest('.booking-request-card') || form.closest('.card');
  }

  function mount() {
    const anchor = target();
    if (!anchor || document.getElementById('book-appointment-manager')) return;
    const section = document.createElement('section');
    section.id = 'book-appointment-manager';
    section.className = 'card book-appointment-manager';
    section.innerHTML = '<h2>Termine verwalten</h2><p class="empty">Termine werden geladen…</p>';
    anchor.insertAdjacentElement('afterend', section);
    load(section);
  }

  async function load(section) {
    try {
      const data = await api('/booking/manageable/');
      render(section, data);
    } catch (error) {
      section.innerHTML = `<h2>Termine verwalten</h2><p class="empty">${esc(error.message)}</p><div class="actions"><button class="btn ghost" type="button" data-book-manager-retry>Erneut versuchen</button></div>`;
      section.querySelector('[data-book-manager-retry]')?.addEventListener('click', () => load(section));
    }
  }

  function render(section, data) {
    section.innerHTML = `<h2>Termine verwalten</h2>
      <p class="muted">Umbuchung oder Stornierung ist bis ${Number(data.change_deadline_hours) || 24} Stunden vor dem Termin möglich.</p>
      <div data-book-manager-list>
        ${data.appointments.length ? data.appointments.map(item => `
          <div class="book-manager-item" data-appointment-id="${esc(item.id)}" style="padding:14px 0;border-bottom:1px solid rgba(0,0,0,.08)">
            <div class="row">
              <div class="row-main"><b>${esc(item.service)}</b><small>${esc(fmt(item.starts_at))} · ${esc(item.staff)}</small></div>
              <span class="badge">${esc(item.status)}</span>
            </div>
            ${item.change_allowed ? `<div class="actions" style="margin-top:10px"><button class="btn ghost" type="button" data-book-reschedule="${esc(item.id)}">Umbuchen</button><button class="btn ghost" type="button" data-book-cancel="${esc(item.id)}">Stornieren</button></div>` : '<p class="muted">Änderungsfrist abgelaufen.</p>'}
            <div data-book-editor></div>
          </div>`).join('') : '<p class="empty">Keine kommenden Termine.</p>'}
      </div>`;

    section.querySelectorAll('[data-book-cancel]').forEach(button => button.addEventListener('click', async () => {
      if (!confirm('Diesen Termin wirklich stornieren?')) return;
      button.disabled = true;
      try {
        await api(`/booking/${button.dataset.bookCancel}/change/`, { method: 'POST', body: JSON.stringify({ action: 'cancel' }) });
        await load(section);
        document.dispatchEvent(new CustomEvent('aplus:booking-changed'));
      } catch (error) {
        alert(error.message);
        button.disabled = false;
      }
    }));

    section.querySelectorAll('[data-book-reschedule]').forEach(button => button.addEventListener('click', () => {
      const item = data.appointments.find(row => row.id === button.dataset.bookReschedule);
      if (!item) return;
      const host = button.closest('[data-appointment-id]').querySelector('[data-book-editor]');
      showEditor(host, item, data.staff, section);
    }));
  }

  function showEditor(host, appointment, staff, section) {
    const eligible = staff.filter(person => (person.service_ids || []).map(Number).includes(Number(appointment.service_id)));
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const min = today.toISOString().slice(0, 10);
    const maxDate = new Date(today.getTime() + 56 * 86400000).toISOString().slice(0, 10);
    host.innerHTML = `<div class="separator"></div><form class="form" data-book-reschedule-form>
      <label>Behandler/in<select name="staff_id" required>${eligible.map(person => `<option value="${person.id}" ${Number(person.id) === Number(appointment.staff_id) ? 'selected' : ''}>${esc(person.name)}</option>`).join('')}</select></label>
      <label>Datum<input name="day" type="date" min="${min}" max="${maxDate}" required></label>
      <label>Freie Zeit<select name="slot" required disabled><option value="">Datum wählen</option></select></label>
      <div class="actions"><button class="btn primary" type="submit" disabled>Neuen Termin speichern</button><button class="btn ghost" type="button" data-book-editor-close>Abbrechen</button></div>
    </form>`;

    const form = host.querySelector('form');
    const day = form.elements.day;
    const provider = form.elements.staff_id;
    const slot = form.elements.slot;
    const submit = form.querySelector('[type="submit"]');

    async function slots() {
      submit.disabled = true;
      slot.disabled = true;
      slot.innerHTML = '<option value="">Freie Zeiten werden geladen…</option>';
      if (!day.value || !provider.value) return;
      try {
        const result = await api(`/slots/?service_id=${encodeURIComponent(appointment.service_id)}&staff_id=${encodeURIComponent(provider.value)}&day=${encodeURIComponent(day.value)}&exclude_appointment_id=${encodeURIComponent(appointment.id)}`);
        slot.innerHTML = result.slots.length
          ? '<option value="">Zeit wählen</option>' + result.slots.map(value => `<option value="${esc(value)}">${new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit' }).format(new Date(value))}</option>`).join('')
          : '<option value="">Keine freie Zeit</option>';
        slot.disabled = !result.slots.length;
      } catch (error) {
        slot.innerHTML = `<option value="">${esc(error.message)}</option>`;
      }
    }

    day.addEventListener('change', slots);
    provider.addEventListener('change', slots);
    slot.addEventListener('change', () => { submit.disabled = !slot.value; });
    form.querySelector('[data-book-editor-close]').addEventListener('click', () => { host.innerHTML = ''; });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      submit.disabled = true;
      submit.textContent = 'Wird gespeichert…';
      try {
        await api(`/booking/${appointment.id}/change/`, {
          method: 'POST',
          body: JSON.stringify({ action: 'reschedule', staff_id: Number(provider.value), starts_at: slot.value }),
        });
        await load(section);
        document.dispatchEvent(new CustomEvent('aplus:booking-changed'));
      } catch (error) {
        alert(error.message);
        submit.disabled = false;
        submit.textContent = 'Neuen Termin speichern';
      }
    });
  }

  const observer = new MutationObserver(() => mount());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', mount);
  document.addEventListener('aplus:booking-changed', () => {
    const section = document.getElementById('book-appointment-manager');
    if (section) load(section);
  });
  setTimeout(mount, 0);
})();
