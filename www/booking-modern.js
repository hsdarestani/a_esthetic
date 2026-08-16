(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const DAY_COUNT = 14;
  const INITIAL_SLOT_LIMIT = 8;

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

  function serviceGlyph(name = '') {
    const n = name.toLowerCase();
    if (n.includes('laser')) return '✦';
    if (n.includes('botox')) return 'B';
    if (n.includes('hyal')) return 'H';
    if (n.includes('prp')) return 'P';
    if (n.includes('skin')) return 'S';
    if (n.includes('infusion')) return 'I';
    if (n.includes('microneed')) return 'RF';
    if (n.includes('lipoly')) return 'L';
    return 'A+';
  }

  function slotPeriod(value) {
    const hour = new Date(value).getHours();
    if (hour < 12) return 'morning';
    if (hour < 17) return 'afternoon';
    return 'evening';
  }

  const periodMeta = {
    morning: 'Vormittag',
    afternoon: 'Nachmittag',
    evening: 'Abend'
  };

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
    let currentSlots = [];
    let activePeriod = 'afternoon';
    let showAllTimes = false;

    const getServiceId = () => typeof options.getServiceId === 'function'
      ? Number(options.getServiceId()) || 0
      : Number(options.serviceId) || 0;

    container.innerHTML = `
      <div class="smart-picker-gate" aria-live="polite">
        <span class="smart-picker-gate-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4M17 3v4M3 10h18"/><path d="m8.5 15 2 2 5-5"/></svg>
        </span>
        <div class="smart-picker-gate-copy"><small>Schritt 2</small><b>Datum & Uhrzeit</b><span>Wählen Sie zuerst oben Ihre Behandlung aus.</span></div>
      </div>
      <div class="smart-picker" aria-label="Wunschtermin auswählen">
        <div class="smart-picker-head">
          <div><small>Wunschtermin</small><strong>Datum & Uhrzeit</strong></div>
          <span class="smart-picker-status" data-picker-status>Termin wählen</span>
        </div>
        <div class="smart-days" data-picker-days></div>
        <div class="smart-times-head"><b>Freie Zeiten</b><span data-picker-day-label></span></div>
        <div class="smart-periods" data-picker-periods hidden></div>
        <div class="smart-times" data-picker-times></div>
        <div class="smart-choice" data-picker-choice hidden></div>
      </div>`;

    const daysEl = container.querySelector('[data-picker-days]');
    const periodsEl = container.querySelector('[data-picker-periods]');
    const timesEl = container.querySelector('[data-picker-times]');
    const dayLabelEl = container.querySelector('[data-picker-day-label]');
    const statusEl = container.querySelector('[data-picker-status]');
    const choiceEl = container.querySelector('[data-picker-choice]');

    function centerActiveDay(behavior = 'smooth') {
      const active = daysEl.querySelector('.smart-day.active');
      if (!active) return;
      const target = active.offsetLeft - Math.max(0, (daysEl.clientWidth - active.offsetWidth) / 2);
      daysEl.scrollTo({ left: Math.max(0, target), behavior });
    }

    function renderDays() {
      daysEl.innerHTML = allDays.map((key, index) => {
        const date = dayDate(key);
        return `<button type="button" class="smart-day ${key === selectedDay ? 'active' : ''}" data-day="${key}" aria-pressed="${key === selectedDay ? 'true' : 'false'}">
          <span>${index === 0 ? 'Heute' : weekday(key)}</span>
          <b>${pad(date.getDate())}</b>
          <small>${month(key)}</small>
        </button>`;
      }).join('');
      requestAnimationFrame(() => centerActiveDay('smooth'));
    }

    function clearSelection() {
      selectedSlot = '';
      choiceEl.hidden = true;
      choiceEl.innerHTML = '';
      statusEl.textContent = 'Termin wählen';
      options.onSelect?.('');
    }

    function groupedSlots() {
      const groups = { morning: [], afternoon: [], evening: [] };
      currentSlots.forEach(slot => groups[slotPeriod(slot)].push(slot));
      return groups;
    }

    function renderPeriodTabs(groups) {
      const available = Object.keys(periodMeta).filter(key => groups[key].length);
      if (!available.length) {
        periodsEl.hidden = true;
        periodsEl.innerHTML = '';
        return;
      }
      if (!available.includes(activePeriod)) activePeriod = available[0];
      periodsEl.hidden = available.length <= 1;
      periodsEl.innerHTML = available.map(key => `
        <button type="button" class="smart-period ${activePeriod === key ? 'active' : ''}" data-period="${key}">
          <span>${periodMeta[key]}</span><small>${groups[key].length}</small>
        </button>`).join('');
    }

    function renderVisibleSlots() {
      if (!currentSlots.length) {
        periodsEl.hidden = true;
        periodsEl.innerHTML = '';
        timesEl.innerHTML = '<div class="smart-picker-empty"><b>Keine freie Zeit</b><span>Wählen Sie einfach einen anderen Tag.</span></div>';
        return;
      }
      const groups = groupedSlots();
      renderPeriodTabs(groups);
      const periodSlots = groups[activePeriod] || [];
      const visible = showAllTimes ? periodSlots : periodSlots.slice(0, INITIAL_SLOT_LIMIT);
      timesEl.innerHTML = visible.map(slot => `<button type="button" class="smart-time ${slot === selectedSlot ? 'active' : ''}" data-slot="${slot}">${slotTime(slot)}</button>`).join('');
      if (!showAllTimes && periodSlots.length > INITIAL_SLOT_LIMIT) {
        timesEl.insertAdjacentHTML('beforeend', `<button type="button" class="smart-more-times" data-more-times>+ ${periodSlots.length - INITIAL_SLOT_LIMIT} weitere Zeiten</button>`);
      }
    }

    async function loadDay() {
      clearSelection();
      showAllTimes = false;
      currentSlots = [];
      const serviceId = getServiceId();
      container.classList.toggle('picker-service-ready', !!serviceId);
      if (!serviceId) {
        periodsEl.hidden = true;
        periodsEl.innerHTML = '';
        timesEl.innerHTML = '';
        dayLabelEl.textContent = '';
        return;
      }

      renderDays();
      const selectedDate = dayDate(selectedDay);
      dayLabelEl.textContent = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: 'long' }).format(selectedDate);
      const id = ++requestId;
      periodsEl.hidden = true;
      periodsEl.innerHTML = '';
      timesEl.innerHTML = '<div class="smart-picker-loading"><i></i><i></i><i></i><i></i><i></i><i></i></div>';
      statusEl.textContent = 'Freie Zeiten…';
      try {
        const slots = await fetchSlots(serviceId, selectedDay, options.excludeAppointmentId || '');
        if (id !== requestId) return;
        currentSlots = slots;
        statusEl.textContent = slots.length ? `${slots.length} frei` : 'Ausgebucht';
        const groups = groupedSlots();
        const available = Object.keys(periodMeta).filter(key => groups[key].length);
        activePeriod = available.includes('afternoon') ? 'afternoon' : (available[0] || 'afternoon');
        renderVisibleSlots();
      } catch (_) {
        if (id !== requestId) return;
        statusEl.textContent = 'Nicht verfügbar';
        periodsEl.hidden = true;
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

    periodsEl.addEventListener('click', event => {
      const button = event.target.closest('[data-period]');
      if (!button) return;
      activePeriod = button.dataset.period;
      showAllTimes = false;
      renderVisibleSlots();
    });

    timesEl.addEventListener('click', event => {
      const more = event.target.closest('[data-more-times]');
      if (more) {
        showAllTimes = true;
        renderVisibleSlots();
        return;
      }
      const button = event.target.closest('[data-slot]');
      if (!button) return;
      selectedSlot = button.dataset.slot;
      timesEl.querySelectorAll('[data-slot]').forEach(item => item.classList.toggle('active', item === button));
      choiceEl.hidden = false;
      choiceEl.innerHTML = `<span class="smart-choice-check">✓</span><div><small>Ihr Wunschtermin</small><b>${choiceLabel(selectedSlot)}</b></div>`;
      statusEl.textContent = 'Ausgewählt';
      options.onSelect?.(selectedSlot);
    });

    if (getServiceId()) {
      renderDays();
      loadDay();
    } else {
      container.classList.remove('picker-service-ready');
    }

    return {
      refresh() { loadDay(); },
      reset() { clearSelection(); loadDay(); },
      value() { return selectedSlot; }
    };
  }

  function mountServiceChooser(form, service) {
    if (!service || service.dataset.modernService === '1') return;
    const label = service.closest('label');
    if (!label) return;
    service.dataset.modernService = '1';
    service.classList.add('service-native-select');

    const options = [...service.options].filter(option => option.value);
    const chooser = document.createElement('div');
    chooser.className = 'service-chooser';
    chooser.innerHTML = `
      <button type="button" class="service-trigger" aria-haspopup="dialog" aria-expanded="false">
        <span class="service-trigger-icon">A+</span>
        <span class="service-trigger-copy"><small>Behandlung</small><b>Behandlung auswählen</b><em>Passenden Termin finden</em></span>
        <span class="service-trigger-arrow">›</span>
      </button>
      <div class="service-sheet" hidden>
        <button type="button" class="service-sheet-backdrop" data-close-services aria-label="Schließen"></button>
        <div class="service-sheet-panel" role="dialog" aria-modal="true" aria-label="Behandlung auswählen">
          <div class="service-sheet-handle"></div>
          <div class="service-sheet-head"><div><small>Schritt 1</small><h3>Behandlung wählen</h3></div><button type="button" data-close-services aria-label="Schließen">×</button></div>
          <div class="service-list">
            ${options.map(option => {
              const [title, duration = ''] = option.textContent.split('·').map(v => v.trim());
              return `<button type="button" class="service-option" data-service-value="${option.value}" data-service-title="${title.replace(/"/g, '&quot;')}" data-service-duration="${duration.replace(/"/g, '&quot;')}">
                <span class="service-option-icon">${serviceGlyph(title)}</span>
                <span class="service-option-copy"><b>${title}</b><small>${duration || 'Termin nach Verfügbarkeit'}</small></span>
                <span class="service-option-check">✓</span>
              </button>`;
            }).join('')}
          </div>
        </div>
      </div>`;
    label.appendChild(chooser);

    const trigger = chooser.querySelector('.service-trigger');
    const sheet = chooser.querySelector('.service-sheet');
    const icon = chooser.querySelector('.service-trigger-icon');
    const title = chooser.querySelector('.service-trigger-copy b');
    const subtitle = chooser.querySelector('.service-trigger-copy em');

    const close = () => {
      sheet.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('service-sheet-open');
    };
    const open = () => {
      sheet.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      document.body.classList.add('service-sheet-open');
    };

    trigger.addEventListener('click', open);
    chooser.querySelectorAll('[data-close-services]').forEach(button => button.addEventListener('click', close));
    chooser.querySelectorAll('[data-service-value]').forEach(button => button.addEventListener('click', () => {
      service.value = button.dataset.serviceValue;
      icon.textContent = serviceGlyph(button.dataset.serviceTitle || '');
      title.textContent = button.dataset.serviceTitle || 'Behandlung';
      subtitle.textContent = button.dataset.serviceDuration || 'Termin nach Verfügbarkeit';
      chooser.querySelectorAll('.service-option').forEach(item => item.classList.toggle('active', item === button));
      close();
      service.dispatchEvent(new Event('change', { bubbles: true }));
    }));

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !sheet.hidden) close();
    });
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
    mountServiceChooser(form, service);

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
      setTimeout(() => host.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80);
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
