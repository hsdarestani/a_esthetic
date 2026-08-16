(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const DAY_COUNT = 21;

  const authToken = () => localStorage.getItem('aplus_token') || '';
  const pad = value => String(value).padStart(2, '0');
  const dayKey = date => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const dayDate = key => new Date(`${key}T12:00:00`);
  const weekday = key => new Intl.DateTimeFormat('de-DE', { weekday: 'short' }).format(dayDate(key)).replace('.', '');
  const month = key => new Intl.DateTimeFormat('de-DE', { month: 'short' }).format(dayDate(key)).replace('.', '');
  const slotTime = value => new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit' }).format(new Date(value));
  const choiceLabel = value => new Intl.DateTimeFormat('de-DE', {
    weekday: 'long', day: '2-digit', month: 'long', hour: '2-digit', minute: '2-digit'
  }).format(new Date(value));

  function days() {
    const result = [];
    const start = new Date();
    start.setHours(12, 0, 0, 0);
    for (let i = 0; i < DAY_COUNT; i += 1) {
      const current = new Date(start);
      current.setDate(start.getDate() + i);
      result.push(dayKey(current));
    }
    return result;
  }

  async function fetchSlots(serviceId, day, excludeAppointmentId = '') {
    const params = new URLSearchParams({ service_id: String(serviceId), day });
    if (excludeAppointmentId) params.set('exclude_appointment_id', String(excludeAppointmentId));
    const headers = {};
    if (authToken()) headers.Authorization = `Bearer ${authToken()}`;
    const response = await fetch(`${API_BASE}/slots/?${params.toString()}`, { headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) throw new Error(body.error || 'slots_failed');
    return Array.isArray(body.slots) ? body.slots : [];
  }

  function mount(container, options = {}) {
    if (!container || container.dataset.smartPicker === '1') return null;
    container.dataset.smartPicker = '1';

    const allDays = days();
    let selectedDay = allDays[0];
    let selectedSlot = '';
    let requestId = 0;

    container.innerHTML = `
      <div class="smart-picker" aria-label="Wunschtermin auswählen">
        <div class="smart-picker-head">
          <div><small>Wunschtermin</small><strong>Datum & Uhrzeit</strong></div>
          <span class="smart-picker-status" data-picker-status>Termin wählen</span>
        </div>
        <div class="smart-days" data-picker-days></div>
        <div class="smart-times-head"><b>Freie Zeiten</b><span data-picker-day-label></span></div>
        <div class="smart-times" data-picker-times><div class="smart-picker-empty">Bitte zuerst eine Terminart auswählen.</div></div>
        <div class="smart-choice" data-picker-choice hidden></div>
      </div>`;

    const daysEl = container.querySelector('[data-picker-days]');
    const timesEl = container.querySelector('[data-picker-times]');
    const dayLabelEl = container.querySelector('[data-picker-day-label]');
    const statusEl = container.querySelector('[data-picker-status]');
    const choiceEl = container.querySelector('[data-picker-choice]');

    const getServiceId = () => typeof options.getServiceId === 'function'
      ? Number(options.getServiceId()) || 0
      : Number(options.serviceId) || 0;

    function renderDays() {
      daysEl.innerHTML = allDays.map((key, index) => {
        const date = dayDate(key);
        return `<button type="button" class="smart-day ${key === selectedDay ? 'active' : ''}" data-day="${key}" aria-pressed="${key === selectedDay ? 'true' : 'false'}">
          <span>${index === 0 ? 'Heute' : weekday(key)}</span>
          <b>${pad(date.getDate())}</b>
          <small>${month(key)}</small>
        </button>`;
      }).join('');
      const active = daysEl.querySelector('.smart-day.active');
      active?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
    }

    function clearSelection() {
      selectedSlot = '';
      choiceEl.hidden = true;
      choiceEl.innerHTML = '';
      statusEl.textContent = 'Termin wählen';
      options.onSelect?.('');
    }

    function renderSlots(slots) {
      if (!slots.length) {
        timesEl.innerHTML = '<div class="smart-picker-empty"><b>Keine freie Zeit</b><span>Wählen Sie einfach einen anderen Tag.</span></div>';
        return;
      }
      timesEl.innerHTML = slots.map(slot => `<button type="button" class="smart-time ${slot === selectedSlot ? 'active' : ''}" data-slot="${slot}">${slotTime(slot)}</button>`).join('');
    }

    async function loadDay() {
      clearSelection();
      renderDays();
      const serviceId = getServiceId();
      const selectedDate = dayDate(selectedDay);
      dayLabelEl.textContent = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: 'long' }).format(selectedDate);
      if (!serviceId) {
        timesEl.innerHTML = '<div class="smart-picker-empty">Bitte zuerst eine Terminart auswählen.</div>';
        return;
      }
      const id = ++requestId;
      timesEl.innerHTML = '<div class="smart-picker-loading"><i></i><i></i><i></i><i></i><i></i><i></i></div>';
      statusEl.textContent = 'Freie Zeiten…';
      try {
        const slots = await fetchSlots(serviceId, selectedDay, options.excludeAppointmentId || '');
        if (id !== requestId) return;
        statusEl.textContent = slots.length ? `${slots.length} frei` : 'Ausgebucht';
        renderSlots(slots);
      } catch (_) {
        if (id !== requestId) return;
        statusEl.textContent = 'Nicht verfügbar';
        timesEl.innerHTML = '<div class="smart-picker-empty"><b>Zeiten konnten nicht geladen werden</b><span>Bitte versuchen Sie es erneut.</span><button type="button" data-retry-slots>Erneut laden</button></div>';
        timesEl.querySelector('[data-retry-slots]')?.addEventListener('click', loadDay);
      }
    }

    daysEl.addEventListener('click', event => {
      const button = event.target.closest('[data-day]');
      if (!button) return;
      selectedDay = button.dataset.day;
      loadDay();
    });

    timesEl.addEventListener('click', event => {
      const button = event.target.closest('[data-slot]');
      if (!button) return;
      selectedSlot = button.dataset.slot;
      timesEl.querySelectorAll('[data-slot]').forEach(item => item.classList.toggle('active', item === button));
      choiceEl.hidden = false;
      choiceEl.innerHTML = `<span class="smart-choice-check">✓</span><div><small>Ihr Wunschtermin</small><b>${choiceLabel(selectedSlot)}</b></div>`;
      statusEl.textContent = 'Ausgewählt';
      options.onSelect?.(selectedSlot);
    });

    renderDays();
    loadDay();

    return {
      refresh() { loadDay(); },
      reset() { clearSelection(); loadDay(); },
      value() { return selectedSlot; }
    };
  }

  function mountBookingForm(form) {
    if (!form || form.dataset.modernBooking === '1') return;
    const service = form.querySelector('[name="service_id"]');
    const hidden = form.querySelector('[name="starts_at"]');
    const host = form.querySelector('[data-booking-picker]');
    const submit = form.querySelector('button[type="submit"]');
    if (!service || !hidden || !host || !submit) return;

    form.dataset.modernBooking = '1';
    hidden.value = '';
    submit.disabled = true;

    const picker = mount(host, {
      getServiceId: () => service.value,
      onSelect: value => {
        hidden.value = value || '';
        submit.disabled = !(service.value && hidden.value);
      }
    });

    service.addEventListener('change', () => {
      hidden.value = '';
      submit.disabled = true;
      picker?.reset();
    });
  }

  function run() {
    mountBookingForm(document.getElementById('booking-form'));
  }

  window.APlusBookingPicker = {
    mountStandalone(container, options) { return mount(container, options); }
  };

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', run);
  setTimeout(run, 0);
})();
