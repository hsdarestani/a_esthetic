(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const WINDOW_DAYS = 21;
  const MAX_LOOKAHEAD_DAYS = 84;
  const DATE_BATCH = 6;
  const SLOT_PREVIEW = 6;

  const token = () => localStorage.getItem('aplus_token') || '';
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) {
      const error = new Error(body.error || 'request_failed');
      error.status = response.status;
      error.body = body;
      throw error;
    }
    return body;
  }

  const pad = value => String(value).padStart(2, '0');
  const dayKey = date => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const dateFromOffset = offset => {
    const date = new Date();
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() + offset);
    return date;
  };
  const fullDate = key => new Intl.DateTimeFormat('de-DE', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  }).format(new Date(`${key}T12:00:00`));
  const shortTime = value => new Intl.DateTimeFormat('de-DE', {
    hour: '2-digit', minute: '2-digit'
  }).format(new Date(value));
  const fullDateTime = value => new Intl.DateTimeFormat('de-DE', {
    weekday: 'long', day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
  }).format(new Date(value));

  function errorText(code) {
    const labels = {
      time_not_available: 'Diese Zeit wurde gerade vergeben. Bitte wählen Sie eine andere freie Zeit.',
      service_not_found: 'Diese Terminart ist aktuell nicht mehr verfügbar.',
      start_time_too_soon: 'Bitte wählen Sie einen späteren Termin.',
      authentication_required: 'Bitte melden Sie sich erneut an.',
      staff_not_found: 'Für diese Terminart ist aktuell kein passender Termin verfügbar.',
      invalid_appointment: 'Die Terminanfrage konnte so nicht gespeichert werden.'
    };
    return labels[code] || 'Die Terminanfrage konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.';
  }

  function serviceGlyph(name = '') {
    const n = name.toLowerCase();
    if (n.includes('botox')) return 'B';
    if (n.includes('hyal')) return 'H';
    if (n.includes('haar') || n.includes('laser')) return '✦';
    if (n.includes('infusion')) return 'I';
    if (n.includes('prp')) return 'P';
    if (n.includes('skin')) return 'S';
    if (n.includes('micro')) return 'RF';
    if (n.includes('lipoly')) return 'L';
    if (n.includes('kontroll')) return 'K';
    return 'A+';
  }

  async function parallelMap(items, limit, worker) {
    const results = new Array(items.length);
    let cursor = 0;
    async function runner() {
      while (cursor < items.length) {
        const index = cursor++;
        try { results[index] = await worker(items[index], index); }
        catch (_) { results[index] = null; }
      }
    }
    await Promise.all(Array.from({ length: Math.min(limit, items.length) }, runner));
    return results;
  }

  async function fetchDay(serviceId, key) {
    return api(`/slots/?service_id=${encodeURIComponent(serviceId)}&day=${encodeURIComponent(key)}`);
  }

  function mount(form) {
    if (!form || form.dataset.doctolibFlow === '1') return;
    form.dataset.doctolibFlow = '1';

    const state = {
      services: [],
      service: null,
      me: null,
      availability: [],
      fetchedUntil: 0,
      visibleDates: DATE_BATCH,
      openDay: '',
      expandedSlots: new Set(),
      selectedSlot: '',
      loadingAvailability: false,
    };

    form.innerHTML = `
      <div class="a-booking-flow" data-a-booking-flow>
        <div class="a-flow-progress" aria-label="Buchungsschritte">
          <span class="active" data-step-dot="1"><b>1</b><em>Terminart</em></span>
          <i></i>
          <span data-step-dot="2"><b>2</b><em>Termin</em></span>
          <i></i>
          <span data-step-dot="3"><b>3</b><em>Bestätigen</em></span>
        </div>

        <section class="a-flow-step" data-service-step>
          <div class="a-step-heading">
            <div><small>Schritt 1</small><h3>Wählen Sie die Terminart</h3></div>
          </div>
          <label class="a-service-search">
            <span aria-hidden="true">⌕</span>
            <input type="search" data-service-search placeholder="Terminart suchen" autocomplete="off">
          </label>
          <div class="a-service-list" data-service-list>
            <div class="a-flow-loading"><i></i><i></i><i></i><i></i></div>
          </div>
        </section>

        <section class="a-flow-step" data-date-step hidden>
          <button class="a-back-link" type="button" data-back-service>← Terminart ändern</button>
          <div class="a-selected-service" data-selected-service></div>
          <div class="a-step-heading">
            <div><small>Schritt 2</small><h3>Datum & Uhrzeit wählen</h3></div>
            <span class="a-live-pill">Live verfügbar</span>
          </div>
          <div class="a-date-list" data-date-list></div>
          <button class="a-more-dates" type="button" data-more-dates hidden>Weitere Daten anzeigen</button>
        </section>

        <div class="a-booking-message" data-booking-message hidden></div>
      </div>
      <div class="a-confirm-layer" data-confirm-layer hidden></div>
    `;

    const flow = form.querySelector('[data-a-booking-flow]');
    const serviceStep = form.querySelector('[data-service-step]');
    const dateStep = form.querySelector('[data-date-step]');
    const serviceList = form.querySelector('[data-service-list]');
    const serviceSearch = form.querySelector('[data-service-search]');
    const dateList = form.querySelector('[data-date-list]');
    const selectedService = form.querySelector('[data-selected-service]');
    const moreDates = form.querySelector('[data-more-dates]');
    const layer = form.querySelector('[data-confirm-layer]');
    const message = form.querySelector('[data-booking-message]');

    function setStep(step) {
      form.querySelectorAll('[data-step-dot]').forEach(dot => {
        dot.classList.toggle('active', Number(dot.dataset.stepDot) <= step);
        dot.classList.toggle('current', Number(dot.dataset.stepDot) === step);
      });
    }

    function showMessage(text, type = 'info') {
      message.hidden = !text;
      message.className = `a-booking-message ${type}`;
      message.textContent = text || '';
    }

    function renderServices(filter = '') {
      const needle = filter.trim().toLowerCase();
      const items = state.services.filter(service => !needle || `${service.name} ${service.price_label || ''}`.toLowerCase().includes(needle));
      serviceList.innerHTML = items.length ? items.map(service => `
        <button class="a-service-row" type="button" data-service-id="${service.id}">
          <span class="a-service-glyph">${esc(serviceGlyph(service.name))}</span>
          <span class="a-service-copy">
            <b>${esc(service.name)}</b>
            <small>${esc(service.price_label || 'Preis nach Beratung')}${service.duration_minutes ? ` · ca. ${Number(service.duration_minutes)} Min.` : ''}</small>
          </span>
          <span class="a-service-arrow">›</span>
        </button>
      `).join('') : '<div class="a-empty"><b>Keine Terminart gefunden</b><span>Versuchen Sie einen anderen Suchbegriff.</span></div>';
    }

    function renderSelectedService() {
      const service = state.service;
      selectedService.innerHTML = service ? `
        <span class="a-service-glyph">${esc(serviceGlyph(service.name))}</span>
        <span><small>Terminart</small><b>${esc(service.name)}</b><em>${esc(service.price_label || 'Preis nach Beratung')}</em></span>
      ` : '';
    }

    function renderAvailability() {
      if (state.loadingAvailability && !state.availability.length) {
        dateList.innerHTML = '<div class="a-date-skeleton"><i></i><i></i><i></i><i></i></div>';
        moreDates.hidden = true;
        return;
      }
      if (!state.availability.length) {
        dateList.innerHTML = '<div class="a-empty"><b>Aktuell keine Online-Zeit gefunden</b><span>Sie können später erneut prüfen oder A+ Esthetic direkt kontaktieren.</span></div>';
        moreDates.hidden = state.fetchedUntil >= MAX_LOOKAHEAD_DAYS;
        return;
      }

      const visible = state.availability.slice(0, state.visibleDates);
      dateList.innerHTML = visible.map((day, index) => {
        const open = state.openDay ? state.openDay === day.day : index === 0;
        const slots = day.slots || [];
        const expanded = state.expandedSlots.has(day.day);
        const shown = expanded ? slots : slots.slice(0, SLOT_PREVIEW);
        return `
          <article class="a-date-card ${open ? 'open' : ''}" data-date-card="${esc(day.day)}">
            <button class="a-date-head" type="button" data-toggle-day="${esc(day.day)}" aria-expanded="${open ? 'true' : 'false'}">
              <span><b>${esc(fullDate(day.day))}</b><small>${slots.length} freie ${slots.length === 1 ? 'Zeit' : 'Zeiten'}</small></span>
              <span class="a-date-chevron">⌄</span>
            </button>
            <div class="a-date-body" ${open ? '' : 'hidden'}>
              <div class="a-slot-grid">
                ${shown.map(slot => `<button class="a-slot" type="button" data-slot="${esc(slot)}">${esc(shortTime(slot))}</button>`).join('')}
              </div>
              ${!expanded && slots.length > SLOT_PREVIEW ? `<button class="a-more-slots" type="button" data-more-slots="${esc(day.day)}">Mehr Zeiten</button>` : ''}
            </div>
          </article>`;
      }).join('');

      moreDates.hidden = state.visibleDates >= state.availability.length && state.fetchedUntil >= MAX_LOOKAHEAD_DAYS;
      if (state.visibleDates < state.availability.length) {
        moreDates.hidden = false;
        moreDates.textContent = 'Weitere Daten anzeigen';
      } else if (state.fetchedUntil < MAX_LOOKAHEAD_DAYS) {
        moreDates.hidden = false;
        moreDates.textContent = state.loadingAvailability ? 'Weitere Daten werden geladen…' : 'Weitere Daten anzeigen';
      }
    }

    async function loadMoreAvailability({ reset = false } = {}) {
      if (!state.service || state.loadingAvailability) return;
      if (reset) {
        state.availability = [];
        state.fetchedUntil = 0;
        state.visibleDates = DATE_BATCH;
        state.openDay = '';
        state.expandedSlots.clear();
      }
      if (state.fetchedUntil >= MAX_LOOKAHEAD_DAYS) return;

      state.loadingAvailability = true;
      renderAvailability();
      const start = state.fetchedUntil;
      const count = Math.min(WINDOW_DAYS, MAX_LOOKAHEAD_DAYS - start);
      const keys = Array.from({ length: count }, (_, index) => dayKey(dateFromOffset(start + index)));
      const serviceId = state.service.id;
      const results = await parallelMap(keys, 5, async key => {
        const data = await fetchDay(serviceId, key);
        return data.slots?.length ? { day: key, slots: data.slots } : null;
      });
      if (!state.service || state.service.id !== serviceId) return;

      state.fetchedUntil += count;
      state.availability.push(...results.filter(Boolean));
      state.availability.sort((a, b) => a.day.localeCompare(b.day));
      if (!state.openDay && state.availability.length) state.openDay = state.availability[0].day;
      state.loadingAvailability = false;

      if (!state.availability.length && state.fetchedUntil < MAX_LOOKAHEAD_DAYS) {
        await loadMoreAvailability();
        return;
      }
      renderAvailability();
    }

    async function chooseService(id) {
      const service = state.services.find(item => Number(item.id) === Number(id));
      if (!service) return;
      state.service = service;
      state.selectedSlot = '';
      renderSelectedService();
      serviceStep.hidden = true;
      dateStep.hidden = false;
      setStep(2);
      showMessage('');
      await loadMoreAvailability({ reset: true });
      requestAnimationFrame(() => dateStep.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    }

    function closeLayer() {
      layer.hidden = true;
      layer.innerHTML = '';
      document.body.classList.remove('a-confirm-open');
      setStep(2);
    }

    async function savePhoneIfNeeded(phone) {
      const current = String(state.me?.profile?.phone || '').trim();
      const next = String(phone || '').trim();
      if (!next || next === current) return;
      const result = await api('/profile/', {
        method: 'POST',
        body: JSON.stringify({
          phone: next,
          marketing_consent: Boolean(state.me?.profile?.marketing_consent),
        })
      });
      if (state.me?.profile) state.me.profile.phone = result.profile?.phone || next;
    }

    function openConfirmation(slot) {
      state.selectedSlot = slot;
      setStep(3);
      const name = state.me?.member?.name || 'A+ Mitglied';
      const email = state.me?.profile?.email || '';
      const phone = state.me?.profile?.phone || '';
      layer.hidden = false;
      document.body.classList.add('a-confirm-open');
      layer.innerHTML = `
        <button class="a-confirm-backdrop" type="button" data-close-confirm aria-label="Schließen"></button>
        <section class="a-confirm-sheet" role="dialog" aria-modal="true" aria-label="Termin bestätigen">
          <div class="a-sheet-handle"></div>
          <div class="a-confirm-head">
            <div><small>Schritt 3</small><h3>Termin bestätigen</h3></div>
            <button type="button" data-close-confirm aria-label="Schließen">×</button>
          </div>

          <div class="a-confirm-summary">
            <div><small>Terminart</small><b>${esc(state.service.name)}</b></div>
            <div><small>Datum & Uhrzeit</small><b>${esc(fullDateTime(slot))}</b></div>
            <div><small>Praxis</small><b>A+ Esthetic · Stiftstraße 14, Frankfurt</b></div>
          </div>

          <div class="a-confirm-block">
            <div class="a-confirm-title"><span>Ihre Daten</span><small>aus Ihrem Customer-Club-Konto</small></div>
            <div class="a-account-lines">
              <div><span>Name</span><b>${esc(name)}</b></div>
              <div><span>E-Mail</span><b>${esc(email || '–')}</b></div>
            </div>
            ${phone ? `<div class="a-account-lines"><div><span>Telefon</span><b>${esc(phone)}</b></div></div>` : `
              <label class="a-phone-field">Mobilnummer für Terminrückfragen
                <input type="tel" data-confirm-phone placeholder="z. B. +49 172 1234567" autocomplete="tel" required>
              </label>`}
          </div>

          <div class="a-confirm-block a-notices">
            <div class="a-confirm-title"><span>Hinweise vor der Buchung</span><small>bitte kurz prüfen</small></div>
            <p><b>24-Stunden-Regel:</b> Wenn Sie verhindert sind, sagen Sie den Termin bitte möglichst mindestens 24 Stunden vorher ab.</p>
            <p><b>Reservierte Zeit:</b> Bei kurzfristiger Absage oder Nichterscheinen kann nach den geltenden Praxisbedingungen ein Ausfallhonorar anfallen.</p>
            <p><b>Privatpraxis:</b> Privat versicherte und selbstzahlende Patient:innen können regulär buchen. Gesetzlich Versicherte buchen die Leistung als Selbstzahler:innen.</p>
          </div>

          <div class="a-confirm-error" data-confirm-error hidden></div>
          <button class="a-confirm-submit" type="button" data-confirm-book>Hinweise gelesen & Termin anfragen</button>
          <button class="a-confirm-change" type="button" data-close-confirm>Andere Zeit wählen</button>
        </section>`;

      layer.querySelectorAll('[data-close-confirm]').forEach(button => button.addEventListener('click', closeLayer));
      layer.querySelector('[data-confirm-book]')?.addEventListener('click', confirmBooking);
    }

    async function confirmBooking() {
      const button = layer.querySelector('[data-confirm-book]');
      const errorBox = layer.querySelector('[data-confirm-error]');
      const phoneInput = layer.querySelector('[data-confirm-phone]');
      if (phoneInput && !phoneInput.value.trim()) {
        phoneInput.focus();
        errorBox.hidden = false;
        errorBox.textContent = 'Bitte geben Sie eine Telefonnummer für Terminrückfragen ein.';
        return;
      }

      button.disabled = true;
      button.textContent = 'Termin wird gespeichert…';
      errorBox.hidden = true;
      try {
        if (phoneInput) await savePhoneIfNeeded(phoneInput.value);
        const result = await api('/booking/', {
          method: 'POST',
          body: JSON.stringify({
            service_id: Number(state.service.id),
            starts_at: state.selectedSlot,
            consent_acknowledged: true,
          })
        });
        layer.innerHTML = `
          <button class="a-confirm-backdrop" type="button" aria-label="Schließen"></button>
          <section class="a-confirm-sheet a-success-sheet" role="dialog" aria-modal="true">
            <div class="a-success-icon">✓</div>
            <small>Terminanfrage eingegangen</small>
            <h3>${esc(state.service.name)}</h3>
            <p>${esc(fullDateTime(result.starts_at || state.selectedSlot))}</p>
            <span>Falls für die gewählte Leistung eine persönliche Bestätigung erforderlich ist, meldet sich das A+ Esthetic Team separat.</span>
            <button class="a-confirm-submit" type="button" data-done>Fertig</button>
          </section>`;
        layer.querySelector('[data-done]')?.addEventListener('click', () => {
          closeLayer();
          document.querySelector('[data-refresh]')?.click();
        });
      } catch (error) {
        errorBox.hidden = false;
        errorBox.textContent = errorText(error.message);
        button.disabled = false;
        button.textContent = 'Hinweise gelesen & Termin anfragen';
        if (error.message === 'time_not_available') {
          setTimeout(() => {
            closeLayer();
            showMessage('Diese Zeit wurde gerade vergeben. Die Verfügbarkeit wurde aktualisiert.', 'warning');
            loadMoreAvailability({ reset: true });
          }, 1100);
        }
      }
    }

    serviceSearch.addEventListener('input', event => renderServices(event.currentTarget.value));
    serviceList.addEventListener('click', event => {
      const row = event.target.closest('[data-service-id]');
      if (row) chooseService(row.dataset.serviceId);
    });
    form.querySelector('[data-back-service]').addEventListener('click', () => {
      state.service = null;
      state.availability = [];
      state.selectedSlot = '';
      dateStep.hidden = true;
      serviceStep.hidden = false;
      setStep(1);
      serviceSearch.focus();
    });
    dateList.addEventListener('click', event => {
      const toggle = event.target.closest('[data-toggle-day]');
      if (toggle) {
        state.openDay = state.openDay === toggle.dataset.toggleDay ? '' : toggle.dataset.toggleDay;
        renderAvailability();
        return;
      }
      const more = event.target.closest('[data-more-slots]');
      if (more) {
        state.expandedSlots.add(more.dataset.moreSlots);
        state.openDay = more.dataset.moreSlots;
        renderAvailability();
        return;
      }
      const slot = event.target.closest('[data-slot]');
      if (slot) openConfirmation(slot.dataset.slot);
    });
    moreDates.addEventListener('click', async () => {
      if (state.visibleDates < state.availability.length) {
        state.visibleDates += DATE_BATCH;
        renderAvailability();
        return;
      }
      const before = state.availability.length;
      await loadMoreAvailability();
      state.visibleDates = Math.min(state.availability.length, Math.max(state.visibleDates + DATE_BATCH, before + DATE_BATCH));
      renderAvailability();
    });

    Promise.all([api('/booking/'), api('/me/')]).then(([booking, me]) => {
      if (!document.documentElement.contains(form)) return;
      state.services = booking.services || [];
      state.me = me;
      renderServices();
      setStep(1);
    }).catch(() => {
      serviceList.innerHTML = '<div class="a-empty"><b>Terminarten konnten nicht geladen werden</b><span>Bitte laden Sie die Seite erneut.</span></div>';
    });
  }

  function run() {
    const form = document.getElementById('booking-form');
    if (form) mount(form);
  }

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', run);
  setTimeout(run, 0);
})();