(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const token = () => localStorage.getItem('aplus_token') || '';
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const pad = value => String(value).padStart(2, '0');
  const dayKey = date => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

  async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) {
      const error = new Error(body.error || 'request_failed');
      error.body = body;
      throw error;
    }
    return body;
  }

  function treatmentIcon(name = '') {
    const n = name.toLowerCase();
    if (n.includes('botox')) return '<svg viewBox="0 0 24 24"><path d="m7.2 16.8 8.9-8.9M13.7 5.8l4.5 4.5M15.8 3.7l4.5 4.5M6 15.8l2.2 2.2-2.7 2.7-2.2-2.2L6 15.8Z"/><path d="m3.8 20.2-1.9 1.9M18.2 3.7 20 1.9"/></svg>';
    if (n.includes('hyal')) return '<svg viewBox="0 0 24 24"><path d="M12 2.7S6.4 9.2 6.4 14a5.6 5.6 0 0 0 11.2 0C17.6 9.2 12 2.7 12 2.7Z"/><path d="M9.2 14.3c.3 1.6 1.3 2.5 2.8 2.8"/></svg>';
    if (n.includes('laser') || n.includes('haar')) return '<svg viewBox="0 0 24 24"><path d="M4 19 14.2 8.8M15.8 3.3v3.4M14.1 5h3.4M19.5 8.5l1.8 1.8M18.6 13h2.6"/><path d="m4.2 14.8 5 5-2 2-5-5 2-2Z"/></svg>';
    if (n.includes('infusion')) return '<svg viewBox="0 0 24 24"><path d="M8 3h8v3.2a4 4 0 0 1-1 2.7l-1.4 1.5v7.1H10.4v-7.1L9 8.9a4 4 0 0 1-1-2.7V3Z"/><path d="M9 6h6M12 17.5v3.7M9.5 21.2h5"/></svg>';
    if (n.includes('micro') || n.includes('rf')) return '<svg viewBox="0 0 24 24"><path d="M5 5h14v14H5zM9 5v14M15 5v14M5 9h14M5 15h14"/></svg>';
    if (n.includes('skin')) return '<svg viewBox="0 0 24 24"><path d="M10.2 3.2S6 8.2 6 11.7a4.2 4.2 0 0 0 8.4 0c0-3.5-4.2-8.5-4.2-8.5Z"/><path d="M18 13v6M15 16h6"/></svg>';
    return '<svg viewBox="0 0 24 24"><path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="8.5"/></svg>';
  }

  const providerPhotos = {
    'Frau Ariane Regaei': 'https://book.a-esthetic.de/static/booking/staff/ariane-regaei.jpg?v=e0a400ebbcee',
    'Qamar Hameed': 'https://book.a-esthetic.de/static/booking/staff/doctor-male.jpg',
  };

  const stateFor = () => ({
    data: null,
    profile: null,
    service: null,
    staff: null,
    startsAt: '',
    slotLabel: '',
    dateLabel: '',
    availability: [],
    dayIndex: 0,
    requestId: 0,
  });

  function formatDay(key) {
    const date = new Date(`${key}T12:00:00`);
    return {
      weekday: new Intl.DateTimeFormat('de-DE', { weekday: 'long' }).format(date),
      short: new Intl.DateTimeFormat('de-DE', { weekday: 'short' }).format(date).replace('.', ''),
      day: new Intl.DateTimeFormat('de-DE', { day: '2-digit' }).format(date),
      month: new Intl.DateTimeFormat('de-DE', { month: 'short' }).format(date).replace('.', ''),
      full: new Intl.DateTimeFormat('de-DE', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' }).format(date),
    };
  }

  function timeLabel(value) {
    return new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit' }).format(new Date(value));
  }

  function appointmentRows(items = []) {
    if (!items.length) return '<p class="book-empty">Noch keine Termine.</p>';
    return items.map(item => `<div class="book-appointment-row"><div><b>${esc(item.service)}</b><small>${esc(new Intl.DateTimeFormat('de-DE', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' }).format(new Date(item.starts_at)))}</small></div><span>${esc(item.status || '')}</span></div>`).join('');
  }

  async function loadAvailability(state, root) {
    const id = ++state.requestId;
    root.innerHTML = '<div class="book-slot-empty">Freie Termine werden geladen …</div>';
    const today = new Date();
    today.setHours(12, 0, 0, 0);
    const days = Array.from({ length: 28 }, (_, offset) => {
      const d = new Date(today);
      d.setDate(today.getDate() + offset);
      return dayKey(d);
    });
    const results = [];
    let cursor = 0;
    async function worker() {
      while (cursor < days.length) {
        const day = days[cursor++];
        try {
          const data = await api(`/slots/?service_id=${encodeURIComponent(state.service.id)}&staff_id=${encodeURIComponent(state.staff.id)}&day=${encodeURIComponent(day)}`);
          if (Array.isArray(data.slots) && data.slots.length) results.push({ date: day, slots: data.slots });
        } catch (_) {}
      }
    }
    await Promise.all(Array.from({ length: 5 }, worker));
    if (id !== state.requestId) return;
    state.availability = results.sort((a, b) => a.date.localeCompare(b.date));
    state.dayIndex = 0;
    renderAvailability(state, root);
  }

  function renderAvailability(state, root) {
    if (!state.availability.length) {
      root.innerHTML = '<div class="book-slot-empty book-slot-empty-card">Für diese Kombination sind in den nächsten Wochen aktuell keine freien Online-Termine verfügbar.</div>';
      return;
    }
    root.innerHTML = `
      <div class="book-availability-picker">
        <div class="book-date-carousel-shell">
          <button class="book-date-nav" type="button" data-date-prev aria-label="Vorherige Tage">‹</button>
          <div class="book-date-rail" data-date-rail>
            ${state.availability.map((day, index) => {
              const label = formatDay(day.date);
              return `<button type="button" class="book-date-chip ${index === state.dayIndex ? 'is-active' : ''}" data-day-index="${index}"><span>${esc(label.short)}</span><strong>${esc(label.day)}</strong><small>${esc(label.month)}</small><em>${day.slots.length}</em></button>`;
            }).join('')}
          </div>
          <button class="book-date-nav" type="button" data-date-next aria-label="Nächste Tage">›</button>
        </div>
        <div class="book-time-panel">
          <div class="book-time-panel-head"><div><span>Freie Zeiten</span><strong data-selected-day-title></strong></div><small data-selected-day-count></small></div>
          <div class="book-time-grid" data-time-slots></div>
        </div>
      </div>`;

    const rail = root.querySelector('[data-date-rail]');
    root.querySelector('[data-date-prev]')?.addEventListener('click', () => rail.scrollBy({ left: -260, behavior: 'smooth' }));
    root.querySelector('[data-date-next]')?.addEventListener('click', () => rail.scrollBy({ left: 260, behavior: 'smooth' }));
    root.querySelectorAll('[data-day-index]').forEach(button => button.addEventListener('click', () => selectDay(state, root, Number(button.dataset.dayIndex))));
    selectDay(state, root, state.dayIndex, false);
  }

  function selectDay(state, root, index, scroll = true) {
    const day = state.availability[index];
    if (!day) return;
    state.dayIndex = index;
    state.startsAt = '';
    const label = formatDay(day.date);
    root.querySelectorAll('.book-date-chip').forEach((button, i) => button.classList.toggle('is-active', i === index));
    const title = root.querySelector('[data-selected-day-title]');
    const count = root.querySelector('[data-selected-day-count]');
    const times = root.querySelector('[data-time-slots]');
    if (title) title.textContent = `${label.weekday}, ${label.day}. ${label.month}`;
    if (count) count.textContent = `${day.slots.length} freie ${day.slots.length === 1 ? 'Zeit' : 'Zeiten'}`;
    if (times) {
      times.innerHTML = day.slots.map(slot => `<button type="button" class="book-slot" data-slot="${esc(slot)}">${esc(timeLabel(slot))}</button>`).join('');
      times.querySelectorAll('[data-slot]').forEach(button => button.addEventListener('click', () => {
        state.startsAt = button.dataset.slot;
        state.slotLabel = timeLabel(state.startsAt);
        state.dateLabel = label.full;
        showStep(root.closest('[data-book-root]'), 4);
        renderSummary(state, root.closest('[data-book-root]'));
      }));
    }
    if (scroll) root.querySelector(`.book-date-chip[data-day-index="${index}"]`)?.scrollIntoView({ behavior:'smooth', block:'nearest', inline:'center' });
  }

  function showStep(host, step) {
    host.querySelectorAll('[data-book-step]').forEach(section => section.classList.toggle('is-active', Number(section.dataset.bookStep) === step));
    host.querySelectorAll('[data-book-progress]').forEach(dot => {
      const n = Number(dot.dataset.bookProgress);
      dot.classList.toggle('is-active', n === Math.min(step, 4));
      dot.classList.toggle('is-done', step > n);
    });
    host.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function renderSummary(state, host) {
    const target = host.querySelector('[data-book-summary]');
    if (!target) return;
    target.innerHTML = `
      <div class="book-summary-row"><span>Behandlung</span><strong>${esc(state.service?.name || '')}</strong></div>
      <div class="book-summary-row"><span>Behandler</span><strong>${esc(state.staff?.name || '')}</strong></div>
      <div class="book-summary-row"><span>Datum</span><strong>${esc(state.dateLabel)}</strong></div>
      <div class="book-summary-row"><span>Uhrzeit</span><strong>${esc(state.slotLabel)}</strong></div>`;
  }

  async function mount(form) {
    if (!form || form.dataset.bookExact === '1') return;
    form.dataset.bookExact = '1';
    form.dataset.modernBooking = '1';
    form.dataset.doctolibFlow = '1';

    const card = form.closest('.booking-request-card');
    if (!card) return;
    card.classList.add('book-booking-card-host');
    card.innerHTML = '<div class="book-slot-empty">Terminbuchung wird geladen …</div>';

    const state = stateFor();
    try {
      const [data, profile] = await Promise.all([
        api('/booking/'),
        api('/profile/').catch(() => null),
      ]);
      state.data = data;
      state.profile = profile;
    } catch (_) {
      card.innerHTML = '<div class="book-error">Die Terminbuchung konnte nicht geladen werden. Bitte versuchen Sie es erneut.</div>';
      return;
    }

    const memberName = String(state.profile?.member?.name || '').trim();
    const nameParts = memberName.split(/\s+/).filter(Boolean);
    const firstName = nameParts.length > 1 ? nameParts.slice(0, -1).join(' ') : (nameParts[0] || '');
    const lastName = nameParts.length > 1 ? nameParts[nameParts.length - 1] : (nameParts[0] || '');
    const email = state.profile?.profile?.email || '';
    const phone = state.profile?.profile?.phone || '';

    card.innerHTML = `
      <div class="book-flow" data-book-root>
        <div class="book-progress" aria-label="Buchungsfortschritt">
          <span class="book-progress-dot is-active" data-book-progress="1">1</span><span class="book-progress-line"></span>
          <span class="book-progress-dot" data-book-progress="2">2</span><span class="book-progress-line"></span>
          <span class="book-progress-dot" data-book-progress="3">3</span><span class="book-progress-line"></span>
          <span class="book-progress-dot" data-book-progress="4">4</span>
        </div>

        <section class="book-step is-active" data-book-step="1">
          <div class="book-step-head"><span>01</span><div><h2>Behandlung wählen</h2><p>Was dürfen wir für dich einplanen?</p></div></div>
          <div class="book-choice-grid" data-services></div>
        </section>

        <section class="book-step" data-book-step="2">
          <button class="book-back" type="button" data-back="1">← Zurück</button>
          <div class="book-step-head"><span>02</span><div><h2>Ärztin oder Arzt wählen</h2><p>Wähle, bei wem du deinen Termin buchen möchtest.</p></div></div>
          <div class="book-choice-grid book-staff-grid" data-staff></div>
        </section>

        <section class="book-step" data-book-step="3">
          <button class="book-back" type="button" data-back="2">← Zurück</button>
          <div class="book-step-head"><span>03</span><div><h2>Freien Termin wählen</h2><p>Wische durch die verfügbaren Tage und wähle darunter direkt deine Uhrzeit.</p></div></div>
          <div data-slots></div>
        </section>

        <section class="book-step" data-book-step="4">
          <button class="book-back" type="button" data-back="3">← Zurück</button>
          <div class="book-step-head"><span>04</span><div><h2>Deine Kontaktdaten</h2><p>Fast geschafft – prüfe deine Daten und sichere deinen Termin.</p></div></div>
          <form class="book-details-form" data-confirm-form>
            <div class="book-field-row">
              <label>Vorname<input value="${esc(firstName)}" readonly></label>
              <label>Nachname<input value="${esc(lastName)}" readonly></label>
            </div>
            <div class="book-field-row">
              <label>E-Mail<input type="email" value="${esc(email)}" readonly></label>
              <label>Telefon<input name="phone" type="tel" value="${esc(phone)}" maxlength="40" placeholder="+49 …"></label>
            </div>
            <div class="book-summary" data-book-summary></div>
            <div class="book-consent-stack">
              <label class="book-privacy-check"><input name="marketing" type="checkbox" checked><span>Ich möchte als Erstes von Aktionen, Angeboten und Neuigkeiten von A+Esthetic erfahren.</span></label>
              <label class="book-privacy-check"><input name="terms" type="checkbox" required><span>Ich stimme den Stornierungsbedingungen von A+Esthetic zu.</span></label>
              <label class="book-privacy-check"><input name="privacy" type="checkbox" required><span>Ich stimme der Verarbeitung meiner Angaben zur Terminorganisation zu und habe die Datenschutzhinweise gelesen.</span></label>
            </div>
            <button class="book-primary" type="submit">Jetzt Termin buchen</button>
          </form>
        </section>

        <section class="book-step book-success" data-book-step="5">
          <div class="book-success-mark">✓</div><div class="book-eyebrow">Termin gespeichert</div><h2>Vielen Dank.</h2>
          <p>Dein Termin wurde erfolgreich gespeichert.</p>
          <div class="book-summary" data-success-summary></div>
          <button class="book-primary" type="button" data-new-booking>Weiteren Termin buchen</button>
        </section>
      </div>
      <section class="book-my-appointments"><h2>Deine Termine</h2><div data-appointments>${appointmentRows(state.data.appointments)}</div></section>`;

    const host = card.querySelector('[data-book-root]');
    const services = host.querySelector('[data-services]');
    services.innerHTML = state.data.services.length ? state.data.services.map(service => `
      <button type="button" class="book-choice-card book-treatment-card" data-service-id="${service.id}">
        <span class="book-treatment-icon">${treatmentIcon(service.name)}</span>
        <strong>${esc(service.name)}</strong>
        <p>Dein Termin wird individuell auf die Behandlung abgestimmt.</p>
        <div class="book-meta"><span>${Number(service.duration_minutes) || 0} Min.</span><span>${esc(service.price_label || '')}</span></div>
      </button>`).join('') : '<div class="book-slot-empty">Zurzeit sind keine Online-Termine freigeschaltet.</div>';

    services.querySelectorAll('[data-service-id]').forEach(button => button.addEventListener('click', () => {
      state.service = state.data.services.find(item => Number(item.id) === Number(button.dataset.serviceId));
      state.staff = null;
      state.startsAt = '';
      const staffRoot = host.querySelector('[data-staff]');
      const eligible = state.data.staff.filter(item => (item.service_ids || []).map(Number).includes(Number(state.service.id)));
      staffRoot.innerHTML = eligible.length ? eligible.map(item => {
        const initials = item.name.split(/\s+/).slice(0, 2).map(part => part[0]).join('');
        const photo = providerPhotos[item.name];
        return `<button type="button" class="book-choice-card book-staff-card" data-staff-id="${item.id}"><span class="book-staff-avatar">${photo ? `<img src="${esc(photo)}" alt="${esc(item.name)}">` : esc(initials)}</span><span class="book-staff-copy"><strong>${esc(item.name)}</strong><span class="book-doctor-badge">${item.name.toLowerCase().includes('frau') ? 'Ärztin' : 'Arzt'}</span><small>Ästhetische Medizin</small></span><span class="book-staff-arrow">›</span></button>`;
      }).join('') : '<div class="book-slot-empty">Für diese Behandlung sind aktuell keine Online-Termine freigeschaltet.</div>';
      staffRoot.querySelectorAll('[data-staff-id]').forEach(staffButton => staffButton.addEventListener('click', async () => {
        state.staff = eligible.find(item => Number(item.id) === Number(staffButton.dataset.staffId));
        state.startsAt = '';
        showStep(host, 3);
        await loadAvailability(state, host.querySelector('[data-slots]'));
      }));
      showStep(host, 2);
    }));

    host.querySelectorAll('[data-back]').forEach(button => button.addEventListener('click', () => showStep(host, Number(button.dataset.back))));

    host.querySelector('[data-confirm-form]')?.addEventListener('submit', async event => {
      event.preventDefault();
      if (!state.service || !state.staff || !state.startsAt) return;
      const button = event.currentTarget.querySelector('button[type="submit"]');
      const formData = new FormData(event.currentTarget);
      button.disabled = true;
      button.textContent = 'Wird gebucht…';
      try {
        const nextPhone = String(formData.get('phone') || '').trim();
        const oldPhone = String(state.profile?.profile?.phone || '').trim();
        if (nextPhone && nextPhone !== oldPhone) {
          await api('/profile/', { method: 'POST', body: JSON.stringify({ phone: nextPhone, marketing_consent: formData.get('marketing') === 'on' }) });
        }
        await api('/booking/', {
          method: 'POST',
          headers: { 'Idempotency-Key': `app-${state.service.id}-${state.staff.id}-${state.startsAt}` },
          body: JSON.stringify({ service_id: Number(state.service.id), staff_id: Number(state.staff.id), starts_at: state.startsAt, consent_acknowledged: true }),
        });
        const success = host.querySelector('[data-success-summary]');
        success.innerHTML = host.querySelector('[data-book-summary]').innerHTML;
        showStep(host, 5);
        const refreshed = await api('/booking/').catch(() => null);
        if (refreshed) card.querySelector('[data-appointments]').innerHTML = appointmentRows(refreshed.appointments);
      } catch (error) {
        const messages = { time_not_available:'Diese Zeit ist inzwischen nicht mehr verfügbar. Bitte wähle eine andere Uhrzeit.', staff_not_found:'Dieser Behandler ist aktuell nicht verfügbar.', service_not_found:'Diese Behandlung ist aktuell nicht verfügbar.' };
        alert(messages[error.message] || 'Die Buchung konnte nicht gespeichert werden. Bitte versuche es erneut.');
        button.disabled = false;
        button.textContent = 'Jetzt Termin buchen';
      }
    });

    host.querySelector('[data-new-booking]')?.addEventListener('click', () => {
      state.service = null; state.staff = null; state.startsAt = ''; state.availability = [];
      showStep(host, 1);
    });
  }

  function run() {
    const form = document.getElementById('booking-form');
    if (form && !form.dataset.bookExact) mount(form);
  }

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', run);
  setTimeout(run, 0);
})();
