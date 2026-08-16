(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';

  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const authToken = () => localStorage.getItem('aplus_token') || '';

  async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (authToken()) headers.Authorization = `Bearer ${authToken()}`;
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

  const formatDateTime = value => new Intl.DateTimeFormat('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));

  function errorText(code) {
    const labels = {
      change_deadline_passed: 'Änderungen sind weniger als 24 Stunden vor dem Termin nicht mehr direkt in der App möglich.',
      time_not_available: 'Diese Zeit ist inzwischen nicht mehr verfügbar.',
      staff_not_found: 'Der gewählte Ansprechpartner ist nicht verfügbar.',
      appointment_not_changeable: 'Dieser Termin kann nicht mehr geändert werden.',
      appointment_not_found: 'Termin nicht gefunden.',
    };
    return labels[code] || 'Die Terminänderung konnte nicht gespeichert werden.';
  }

  function refreshBooking() {
    const refresh = document.querySelector('[data-refresh]');
    if (refresh) {
      refresh.click();
      return;
    }
    document.getElementById('p0-appointment-management')?.remove();
    setTimeout(enhanceBookingManagement, 50);
  }

  async function loadSlots(serviceId, staffId, day, select) {
    select.disabled = true;
    select.innerHTML = '<option value="">Freie Zeiten werden geladen…</option>';
    try {
      const data = await api(`/slots/?service_id=${encodeURIComponent(serviceId)}&staff_id=${encodeURIComponent(staffId)}&day=${encodeURIComponent(day)}`);
      select.innerHTML = data.slots.length
        ? '<option value="">Freie Zeit wählen</option>' + data.slots.map(slot => {
            const label = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit' }).format(new Date(slot));
            return `<option value="${esc(slot)}">${esc(label)}</option>`;
          }).join('')
        : '<option value="">An diesem Tag keine freie Zeit</option>';
    } catch (_) {
      select.innerHTML = '<option value="">Freie Zeiten konnten nicht geladen werden</option>';
    } finally {
      select.disabled = false;
    }
  }

  function buildRescheduleEditor(appointment, staffOptions, container) {
    container.innerHTML = '';
    const editor = document.createElement('div');
    editor.className = 'form reschedule-modern';
    editor.innerHTML = `
      <div data-reschedule-picker></div>
      <div class="actions">
        <button class="btn primary" type="button" data-save-reschedule disabled>Umbuchung speichern</button>
        <button class="btn ghost" type="button" data-close-reschedule>Abbrechen</button>
      </div>`;
    container.appendChild(editor);

    const save = editor.querySelector('[data-save-reschedule]');
    let selectedSlot = '';
    const host = editor.querySelector('[data-reschedule-picker]');
    if (!window.APlusBookingPicker) {
      host.innerHTML = '<div class="notice">Die Terminauswahl konnte nicht geladen werden. Bitte öffnen Sie die Seite erneut.</div>';
      return;
    }

    window.APlusBookingPicker.mountStandalone(host, {
      serviceId: appointment.service_id,
      excludeAppointmentId: appointment.id,
      onSelect: value => {
        selectedSlot = value || '';
        save.disabled = !selectedSlot;
      },
    });

    editor.querySelector('[data-close-reschedule]').addEventListener('click', () => { container.innerHTML = ''; });
    save.addEventListener('click', async () => {
      if (!selectedSlot) return;
      save.disabled = true;
      save.textContent = 'Wird gespeichert…';
      try {
        await api(`/booking/${appointment.id}/change/`, {
          method: 'POST',
          body: JSON.stringify({ action: 'reschedule', starts_at: selectedSlot }),
        });
        refreshBooking();
      } catch (error) {
        alert(errorText(error.message));
        save.disabled = false;
        save.textContent = 'Umbuchung speichern';
      }
    });
  }

  async function enhanceBookingManagement() {
    if (!authToken() || !document.getElementById('booking-form')) return;
    if (document.getElementById('p0-appointment-management')) return;

    const formCard = document.getElementById('booking-form')?.closest('.card');
    if (!formCard) return;

    const card = document.createElement('section');
    card.className = 'card';
    card.id = 'p0-appointment-management';
    card.innerHTML = '<h2>Termine verwalten</h2><p class="empty">Termine werden geladen…</p>';
    formCard.insertAdjacentElement('afterend', card);

    try {
      const data = await api('/booking/manageable/');
      if (!data.appointments.length) {
        card.innerHTML = '<h2>Termine verwalten</h2><p class="empty">Keine anstehenden Termine zum Verwalten.</p>';
        return;
      }

      card.innerHTML = `
        <h2>Termine verwalten</h2>
        <p class="muted">Stornieren oder auf eine tatsächlich freie Zeit umbuchen. Direkte Änderungen sind bis ${Number(data.change_deadline_hours) || 24} Stunden vor dem Termin möglich.</p>
        <div data-managed-list></div>`;
      const list = card.querySelector('[data-managed-list]');

      data.appointments.forEach(appointment => {
        const row = document.createElement('div');
        row.className = 'row';
        row.style.alignItems = 'flex-start';
        row.innerHTML = `
          <div class="row-main">
            <b>${esc(appointment.service)}</b>
            <small>${esc(formatDateTime(appointment.starts_at))}</small>
            ${appointment.change_allowed ? '' : '<small>Änderungsfrist abgelaufen – bitte A+ Esthetic kontaktieren.</small>'}
            <div class="actions" style="margin-top:8px">
              <button class="btn ghost" type="button" data-reschedule ${appointment.change_allowed ? '' : 'disabled'}>Umbuchen</button>
              <button class="btn danger" type="button" data-cancel ${appointment.change_allowed ? '' : 'disabled'}>Stornieren</button>
            </div>
            <div data-reschedule-container></div>
          </div>`;
        list.appendChild(row);

        const editorContainer = row.querySelector('[data-reschedule-container]');
        row.querySelector('[data-reschedule]').addEventListener('click', () => {
          buildRescheduleEditor(appointment, data.staff, editorContainer);
        });
        row.querySelector('[data-cancel]').addEventListener('click', async event => {
          if (!confirm('Diesen Termin wirklich stornieren?')) return;
          const button = event.currentTarget;
          button.disabled = true;
          button.textContent = 'Wird storniert…';
          try {
            await api(`/booking/${appointment.id}/change/`, {
              method: 'POST',
              body: JSON.stringify({ action: 'cancel' }),
            });
            refreshBooking();
          } catch (error) {
            alert(errorText(error.message));
            button.disabled = false;
            button.textContent = 'Stornieren';
          }
        });
      });
    } catch (_) {
      card.innerHTML = '<h2>Termine verwalten</h2><p class="empty">Terminverwaltung konnte nicht geladen werden.</p>';
    }
  }

  const observer = new MutationObserver(() => { enhanceBookingManagement(); });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', enhanceBookingManagement);
  setTimeout(enhanceBookingManagement, 0);
})();
