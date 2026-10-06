(() => {
  'use strict';

  const API = '/api/mobile/admin/book';
  const state = {
    tab: 'dashboard',
    date: new Date().toISOString().slice(0, 10),
    staff: '',
    bookingQuery: '',
    bookingStatus: '',
    cache: { appointments: new Map(), calendar: null, settings: null }
  };

  const esc = (value = '') => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const list = (...values) => values.find(Array.isArray) || [];
  const obj = (value) => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const token = () => localStorage.getItem('aplus_token') || '';
  const content = () => document.querySelector('.shell .content') || document.querySelector('.content');
  const view = () => document.querySelector('[data-ba-view]');

  function statusLabel(value) {
    return ({ new:'Neu', confirmed:'Bestätigt', cancelled:'Abgesagt', completed:'Abgeschlossen', no_show:'Nicht erschienen' })[value] || value || 'Neu';
  }

  async function api(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 16000);
    const headers = { ...(options.headers || {}), Accept: 'application/json' };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    try {
      const response = await fetch(`${API}${path}`, { ...options, headers, signal: controller.signal, cache:'no-store' });
      let body = {};
      try { body = await response.json(); } catch (_) {}
      if (!response.ok || body.ok === false) {
        const error = new Error(body.message || body.error || `HTTP ${response.status}`);
        error.status = response.status;
        throw error;
      }
      return obj(body);
    } catch (error) {
      if (error?.name === 'AbortError') throw new Error('Book Admin antwortet nicht. Bitte erneut versuchen.');
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  function tabs() {
    const items = [
      ['dashboard','Übersicht'], ['calendar','Kalender'], ['bookings','Buchungen'],
      ['customers','Kunden'], ['services','Behandlungen'], ['settings','Einstellungen']
    ];
    return `<div class="ba-tabs">${items.map(([key,label]) =>
      `<button type="button" class="ba-tab ${state.tab === key ? 'active' : ''}" data-ba-tab="${key}">${label}</button>`
    ).join('')}</div>`;
  }

  function shell() {
    return `<div class="book-admin-v2">
      <header class="ba-head">
        <div><small>A+ ESTHETIC · BOOK</small><h1>Verwaltung</h1><p>Termine, Kalender, Kunden und Verfügbarkeit direkt in der App.</p></div>
        <button type="button" class="ba-back" data-ba-back>← App Admin</button>
      </header>
      ${tabs()}
      <div data-ba-view><div class="ba-loading">Wird geladen…</div></div>
    </div>`;
  }

  function loading() { return '<div class="ba-loading">Wird geladen…</div>'; }
  function failure(error) { return `<div class="ba-error">${esc(error?.message || error || 'Unbekannter Fehler')}</div>`; }

  function remember(items) {
    list(items).forEach(item => { if (item && item.id != null) state.cache.appointments.set(String(item.id), item); });
  }

  function bookingCard(item) {
    const status = item.status || 'new';
    return `<button type="button" class="ba-booking" data-ba-appointment="${esc(item.id)}">
      <div class="ba-booking-top"><strong>${esc(item.date || '')} · ${esc(item.start || '')}<br>${esc(item.customer_name || 'Kunde')}</strong><span class="ba-badge ${esc(status)}">${esc(statusLabel(status))}</span></div>
      <small>${esc(item.service_name || 'Behandlung')} · ${esc(item.staff_name || 'Behandler')}</small>
      ${item.customer_phone || item.customer_email ? `<small>${esc(item.customer_phone || item.customer_email)}</small>` : ''}
    </button>`;
  }

  function appointmentSheet(item) {
    return `<div class="ba-sheet" data-ba-sheet>
      <div class="ba-sheet-card">
        <div class="ba-sheet-head"><button type="button" data-ba-close>‹</button><b>Termin bearbeiten</b><button type="button" data-ba-close>×</button></div>
        <form class="ba-sheet-body" data-ba-appointment-form="${esc(item.id)}">
          <div class="ba-card"><h3>${esc(item.customer_name || 'Kunde')}</h3><div class="ba-muted">${esc(item.service_name || '')} · ${esc(item.staff_name || '')}</div>${item.customer_phone ? `<div class="ba-muted">${esc(item.customer_phone)}</div>` : ''}</div>
          <div class="ba-form-row"><label>Datum</label><input type="date" name="date" required value="${esc(item.date || state.date)}"></div>
          <div class="ba-form-row"><label>Uhrzeit</label><input type="time" step="900" name="time" required value="${esc(item.start || '')}"></div>
          <div class="ba-form-row"><label>Status</label><select name="status">${['new','confirmed','completed','no_show','cancelled'].map(s => `<option value="${s}" ${s === item.status ? 'selected' : ''}>${esc(statusLabel(s))}</option>`).join('')}</select></div>
          ${item.notes_customer ? `<div class="ba-card"><h3>Kundennotiz</h3><div class="ba-muted">${esc(item.notes_customer)}</div></div>` : ''}
          <button class="ba-sheet-save" type="submit">Änderungen speichern</button>
          <button class="ba-btn danger" type="button" data-ba-delete-appointment="${esc(item.id)}">Termin löschen</button>
        </form>
      </div>
    </div>`;
  }

  function openSheet(item) {
    closeSheet();
    document.body.insertAdjacentHTML('beforeend', appointmentSheet(item));
  }
  function closeSheet() { document.querySelector('[data-ba-sheet]')?.remove(); }

  async function renderDashboard(target) {
    target.innerHTML = loading();
    try {
      const data = await api('/overview/');
      const stats = obj(data.stats);
      const upcoming = list(data.upcoming, data.appointments, data.results);
      remember(upcoming);
      target.innerHTML = `<div class="ba-stats">
        <div class="ba-stat"><b>${Number(stats.today || 0)}</b><span>Termine heute</span></div>
        <div class="ba-stat"><b>${Number(stats.new_today || 0)}</b><span>Neue Termine</span></div>
        <div class="ba-stat"><b>${Number(stats.customers || 0)}</b><span>Kunden</span></div>
        <div class="ba-stat"><b>${Number(stats.active_services || 0)}</b><span>Behandlungen</span></div>
      </div>
      <section class="ba-card"><h2>Nächste Termine</h2><div class="ba-list">${upcoming.length ? upcoming.map(bookingCard).join('') : '<div class="ba-empty">Keine kommenden Termine.</div>'}</div></section>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  const mins = (value) => {
    const match = String(value || '').match(/^(\d{1,2}):(\d{2})/);
    return match ? Number(match[1]) * 60 + Number(match[2]) : null;
  };
  const time = (minutes) => `${String(Math.floor(minutes / 60)).padStart(2,'0')}:00`;
  const pct = (minute, start, span) => Math.max(0, Math.min(100, ((minute - start) / span) * 100));

  function calendarTimeline(data) {
    const appointments = list(data.appointments, data.bookings);
    const blocks = list(data.blocks);
    const ranges = list(data.ranges);
    remember(appointments);
    const allTimes = [];
    ranges.forEach(r => { if (mins(r.start) != null) allTimes.push(mins(r.start)); if (mins(r.end) != null) allTimes.push(mins(r.end)); });
    appointments.forEach(a => { if (mins(a.start) != null) allTimes.push(mins(a.start)); if (mins(a.end) != null) allTimes.push(mins(a.end)); });
    blocks.forEach(b => { if (mins(b.start) != null) allTimes.push(mins(b.start)); if (mins(b.end) != null) allTimes.push(mins(b.end)); });
    let start = allTimes.length ? Math.floor((Math.min(...allTimes) - 30) / 60) * 60 : 8 * 60;
    let end = allTimes.length ? Math.ceil((Math.max(...allTimes) + 30) / 60) * 60 : 20 * 60;
    start = Math.max(6 * 60, start); end = Math.min(23 * 60, Math.max(start + 8 * 60, end));
    const span = end - start;
    const labels = [];
    for (let m = start; m <= end; m += 60) labels.push(`<span class="ba-axis-label" style="top:${pct(m,start,span)}%">${time(m)}</span>`);
    const working = ranges.map(r => {
      const s = mins(r.start), e = mins(r.end); if (s == null || e == null) return '';
      return `<div class="ba-working" style="top:${pct(s,start,span)}%;height:${Math.max(1,pct(e,start,span)-pct(s,start,span))}%"></div>`;
    }).join('');
    const blockHtml = blocks.map(b => {
      const s = mins(b.start), e = mins(b.end); if (s == null || e == null) return '';
      return `<div class="ba-block" style="top:${pct(s,start,span)}%;height:${Math.max(2.2,pct(e,start,span)-pct(s,start,span))}%">${esc(b.start)}–${esc(b.end)} ${esc(b.note ? 'Notiz' : 'Gesperrt')}</div>`;
    }).join('');
    const events = appointments.map(a => {
      const s = mins(a.start), e = mins(a.end); if (s == null) return '';
      const durationEnd = e != null && e > s ? e : s + 30;
      return `<button type="button" class="ba-event" data-ba-appointment="${esc(a.id)}" style="top:${pct(s,start,span)}%;height:${Math.max(4.8,pct(durationEnd,start,span)-pct(s,start,span))}%"><strong>${esc(a.start)} · ${esc(a.customer_name)}</strong><span>${esc(a.service_name)}</span><small>${esc(statusLabel(a.status))}</small></button>`;
    }).join('');
    return `<div class="ba-calendar"><div class="ba-axis">${labels.join('')}</div><div class="ba-track">${working}${blockHtml}${events}</div></div>`;
  }

  function datePretty(value) {
    try { return new Intl.DateTimeFormat('de-DE',{weekday:'long',day:'2-digit',month:'long'}).format(new Date(`${value}T12:00:00`)); } catch (_) { return value; }
  }
  function shiftDate(days) {
    const d = new Date(`${state.date}T12:00:00`); d.setDate(d.getDate() + days); state.date = d.toISOString().slice(0,10);
  }

  async function renderCalendar(target) {
    target.innerHTML = loading();
    try {
      const query = new URLSearchParams({ date: state.date });
      if (state.staff) query.set('staff', state.staff);
      const data = await api(`/calendar/?${query}`);
      const staff = list(data.staff);
      const appointments = list(data.appointments, data.bookings);
      const blocks = list(data.blocks);
      const ranges = list(data.ranges);
      state.staff = String(data.selected_staff || state.staff || staff[0]?.id || '');
      state.date = data.date || state.date;
      state.cache.calendar = { ...data, staff, appointments, blocks, ranges };
      remember(appointments);
      target.innerHTML = `<section class="ba-card">
        <div class="ba-date-nav"><button type="button" data-ba-day="-1">‹</button><div class="ba-date-center"><b>${esc(datePretty(state.date))}</b><small>${esc(state.date)}</small></div><button type="button" data-ba-day="1">›</button></div>
        ${staff.length ? `<div class="ba-provider" style="margin-top:9px">${staff.map(s => `<button type="button" class="${String(s.id) === state.staff ? 'active' : ''}" data-ba-staff="${esc(s.id)}">${esc(s.name)}</button>`).join('')}</div>` : ''}
      </section>
      ${staff.length ? calendarTimeline(state.cache.calendar) : '<div class="ba-empty">Kein aktiver Behandler vorhanden.</div>'}
      <section class="ba-card"><h3>Sperrzeit / Notiz</h3><form data-ba-block>
        <div class="ba-toolbar"><label class="ba-field">Von<input required type="time" step="900" name="start"></label><label class="ba-field">Bis<input required type="time" step="900" name="end"></label></div>
        <div class="ba-toolbar" style="margin-top:8px"><label class="ba-field">Typ<select name="kind"><option value="block">Zeitraum blockieren</option><option value="note">Notiz</option></select></label><label class="ba-field">Text<input name="text" maxlength="120" placeholder="Optional"></label></div>
        <button class="ba-btn primary" style="margin-top:9px" type="submit">Speichern</button>
      </form>${blocks.length ? `<div class="ba-list" style="margin-top:10px">${blocks.map(b => `<div class="ba-booking"><div class="ba-booking-top"><strong>${esc(b.start)}–${esc(b.end)} · ${b.note ? 'Notiz' : 'Gesperrt'}</strong><button type="button" class="ba-btn danger" data-ba-delete-block="${esc(b.id)}">Löschen</button></div><small>${esc(b.reason || '')}</small></div>`).join('')}</div>` : ''}</section>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderBookings(target) {
    target.innerHTML = loading();
    try {
      const query = new URLSearchParams();
      if (state.bookingQuery) query.set('q', state.bookingQuery);
      if (state.bookingStatus) query.set('status', state.bookingStatus);
      const data = await api(`/bookings/?${query.toString()}`);
      const bookings = list(data.bookings, data.appointments, data.results);
      remember(bookings);
      const statuses = [['','Alle'],['new','Neu'],['confirmed','Bestätigt'],['completed','Abgeschlossen'],['no_show','No-show'],['cancelled','Abgesagt']];
      target.innerHTML = `<section class="ba-card"><form class="ba-search" data-ba-booking-search><input name="q" value="${esc(state.bookingQuery)}" placeholder="Name, E-Mail oder Behandlung"><button class="ba-btn" type="submit">Suchen</button></form><div class="ba-status-chips">${statuses.map(([key,label]) => `<button type="button" class="${state.bookingStatus === key ? 'active' : ''}" data-ba-status="${key}">${label}</button>`).join('')}</div></section>
        <div class="ba-list">${bookings.length ? bookings.map(bookingCard).join('') : '<div class="ba-empty">Keine Buchungen gefunden.</div>'}</div>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  function initials(name) { return String(name || 'K').split(/\s+/).filter(Boolean).slice(0,2).map(v => v[0]?.toUpperCase() || '').join('') || 'K'; }

  async function renderCustomers(target, q = '') {
    target.innerHTML = loading();
    try {
      const data = await api(`/customers/${q ? `?q=${encodeURIComponent(q)}` : ''}`);
      const customers = list(data.customers, data.results);
      target.innerHTML = `<section class="ba-card"><form class="ba-search" data-ba-customer-search><input name="q" value="${esc(q)}" placeholder="Name, E-Mail oder Telefon"><button class="ba-btn" type="submit">Suchen</button></form></section><div class="ba-list">${customers.length ? customers.map(c => `<button type="button" class="ba-customer" data-ba-customer="${esc(c.id)}"><span class="ba-avatar">${esc(initials(c.name))}</span><span><strong>${esc(c.name || 'Kunde')}</strong><small>${esc(c.email || c.phone || '')}</small><small>${Number(c.appointments || 0)} Termine · ${Number(c.patient_records || 0)} Akteneinträge</small></span><b>›</b></button>`).join('') : '<div class="ba-empty">Keine Kunden gefunden.</div>'}</div>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderCustomerDetail(target, id) {
    target.innerHTML = loading();
    try {
      const data = await api(`/customers/${id}/`);
      const c = obj(data.customer);
      const records = list(c.records);
      const appointments = list(data.appointments, c.appointments_list);
      remember(appointments);
      target.innerHTML = `<button class="ba-btn" type="button" data-ba-back-customers>← Kunden</button>
        <section class="ba-card" style="margin-top:9px"><div style="display:flex;gap:11px;align-items:center"><span class="ba-avatar">${esc(initials(c.name))}</span><div><h2 style="margin:0">${esc(c.name || 'Kunde')}</h2><div class="ba-muted">${esc(c.email || '')}${c.phone ? ` · ${esc(c.phone)}` : ''}</div></div></div></section>
        <section class="ba-card"><h3>Patientenakte</h3>${records.length ? records.map(r => `<div class="ba-record"><b>${esc(r.title || 'Eintrag')}</b><small>${esc(r.kind || '')} · ${esc(r.source || '')} · ${r.shared_with_customer ? 'geteilt' : 'intern'}</small>${r.note ? `<small>${esc(r.note)}</small>` : ''}</div>`).join('') : '<div class="ba-empty">Keine Akteneinträge.</div>'}</section>
        <section class="ba-card"><h3>Terminverlauf</h3><div class="ba-list">${appointments.length ? appointments.map(bookingCard).join('') : '<div class="ba-empty">Keine Termine.</div>'}</div></section>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderServices(target) {
    target.innerHTML = loading();
    try {
      const data = await api('/services/');
      const services = list(data.services, data.results);
      target.innerHTML = `<div class="ba-list">${services.length ? services.map(s => `<details class="ba-card"><summary style="cursor:pointer;list-style:none"><div class="ba-booking-top"><strong>${esc(s.name)}</strong><span class="ba-badge">${s.active && s.bookable ? 'Buchbar' : s.active ? 'Aktiv' : 'Inaktiv'}</span></div><div class="ba-muted" style="margin-top:4px">${esc(s.price_label || 'Kein Preis')} · ${Number(s.duration_minutes || 0)} Min.</div></summary><form data-ba-service="${esc(s.id)}" style="margin-top:12px;display:grid;gap:8px"><label class="ba-field">Name<input name="name" value="${esc(s.name)}"></label><label class="ba-field">Preis<input name="price_label" value="${esc(s.price_label || '')}"></label><div class="ba-toolbar"><label class="ba-field">Dauer<input type="number" min="0" name="duration_minutes" value="${Number(s.duration_minutes || 0)}"></label><label class="ba-field">Puffer<input type="number" min="0" name="buffer_minutes" value="${Number(s.buffer_minutes || 0)}"></label></div><label class="ba-field"><span><input type="checkbox" name="active" ${s.active ? 'checked' : ''}> Aktiv</span></label><label class="ba-field"><span><input type="checkbox" name="bookable" ${s.bookable ? 'checked' : ''}> Online buchbar</span></label><label class="ba-field"><span><input type="checkbox" name="requires_confirmation" ${s.requires_confirmation ? 'checked' : ''}> Manuelle Bestätigung</span></label><button class="ba-btn primary" type="submit">Speichern</button></form></details>`).join('') : '<div class="ba-empty">Keine Behandlungen.</div>'}</div>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderSettings(target) {
    target.innerHTML = loading();
    try {
      const data = await api('/settings/');
      const staff = list(data.staff);
      const overrides = list(data.upcoming_overrides, data.overrides);
      state.cache.settings = { ...data, staff, upcoming_overrides: overrides };
      target.innerHTML = `<section class="ba-card"><h3>Team & Arbeitszeiten</h3><div class="ba-list">${staff.length ? staff.map(s => `<div class="ba-booking"><strong>${esc(s.name)}</strong><small>${esc(s.role || '')}</small><small>${list(s.services).map(x => esc(x.name)).join(', ')}</small><div class="ba-status-chips">${list(s.working_hours).map(h => `<span class="ba-badge">${esc(h.weekday_label)} ${esc(h.start)}–${esc(h.end)}</span>`).join('')}</div></div>`).join('') : '<div class="ba-empty">Kein Team.</div>'}</div></section>
        <section class="ba-card"><h3>Tages-Verfügbarkeit</h3><form data-ba-override style="display:grid;gap:8px"><div class="ba-toolbar"><label class="ba-field">Behandler<select name="staff_id">${staff.filter(s => s.active !== false).map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('')}</select></label><label class="ba-field">Datum<input required type="date" name="date" value="${esc(state.date)}"></label></div><label class="ba-field"><span><input type="checkbox" name="closed"> Ganztägig nicht verfügbar</span></label><div class="ba-toolbar"><label class="ba-field">Von<input type="time" step="900" name="start" value="09:00"></label><label class="ba-field">Bis<input type="time" step="900" name="end" value="18:00"></label></div><div class="ba-actions"><button class="ba-btn primary" type="submit">Ausnahme speichern</button><button class="ba-btn" type="button" data-ba-reset-override>Zurücksetzen</button></div></form></section>
        <section class="ba-card"><h3>Kommende Ausnahmen</h3><div class="ba-list">${overrides.length ? overrides.map(o => `<div class="ba-booking"><strong>${esc(o.date)} · ${esc(o.staff_name)}</strong><small>${o.closed ? 'Geschlossen' : list(o.ranges).map(r => `${esc(r.start)}–${esc(r.end)}`).join(' / ')}</small></div>`).join('') : '<div class="ba-empty">Keine Ausnahmen.</div>'}</div></section>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderTab() {
    const target = view(); if (!target) return;
    document.querySelectorAll('[data-ba-tab]').forEach(button => button.classList.toggle('active', button.dataset.baTab === state.tab));
    if (state.tab === 'dashboard') return renderDashboard(target);
    if (state.tab === 'calendar') return renderCalendar(target);
    if (state.tab === 'bookings') return renderBookings(target);
    if (state.tab === 'customers') return renderCustomers(target);
    if (state.tab === 'services') return renderServices(target);
    if (state.tab === 'settings') return renderSettings(target);
  }

  async function openBookAdmin() {
    const target = content(); if (!target) return;
    closeSheet(); target.innerHTML = shell(); await renderTab();
  }

  async function saveAppointment(form) {
    const id = form.dataset.baAppointmentForm;
    const fd = new FormData(form);
    await api(`/appointments/${id}/`, { method:'POST', body:JSON.stringify({ date:fd.get('date'), time:fd.get('time'), status:fd.get('status') }) });
    closeSheet(); await renderTab();
  }

  document.addEventListener('click', async event => {
    const legacyBook = event.target.closest('a[href*="book.a-esthetic.de/verwaltung"], [data-book-admin-open]');
    if (legacyBook) { event.preventDefault(); event.stopPropagation(); await openBookAdmin(); return; }
    const tab = event.target.closest('[data-ba-tab]');
    if (tab) { state.tab = tab.dataset.baTab; await renderTab(); return; }
    if (event.target.closest('[data-ba-back]')) {
      document.querySelector('.nav [data-route="more"]')?.click();
      setTimeout(() => document.querySelector('[data-ops-admin]')?.click(), 70);
      return;
    }
    if (event.target.closest('[data-ba-close]') || (event.target.matches('[data-ba-sheet]'))) { closeSheet(); return; }
    const appointment = event.target.closest('[data-ba-appointment]');
    if (appointment) { const item = state.cache.appointments.get(String(appointment.dataset.baAppointment)); if (item) openSheet(item); return; }
    const day = event.target.closest('[data-ba-day]');
    if (day) { shiftDate(Number(day.dataset.baDay || 0)); await renderCalendar(view()); return; }
    const staff = event.target.closest('[data-ba-staff]');
    if (staff) { state.staff = String(staff.dataset.baStaff || ''); await renderCalendar(view()); return; }
    const status = event.target.closest('[data-ba-status]');
    if (status) { state.bookingStatus = status.dataset.baStatus || ''; await renderBookings(view()); return; }
    const customer = event.target.closest('[data-ba-customer]');
    if (customer) { await renderCustomerDetail(view(), customer.dataset.baCustomer); return; }
    if (event.target.closest('[data-ba-back-customers]')) { await renderCustomers(view()); return; }
    const delAppt = event.target.closest('[data-ba-delete-appointment]');
    if (delAppt) { if (!confirm('Termin wirklich löschen?')) return; await api(`/appointments/${delAppt.dataset.baDeleteAppointment}/`, { method:'POST', body:JSON.stringify({action:'delete'}) }); closeSheet(); await renderTab(); return; }
    const delBlock = event.target.closest('[data-ba-delete-block]');
    if (delBlock) { await api('/blocks/', {method:'POST',body:JSON.stringify({action:'delete',id:Number(delBlock.dataset.baDeleteBlock)})}); await renderCalendar(view()); return; }
    if (event.target.closest('[data-ba-reset-override]')) {
      const form = event.target.closest('form'); if (!form) return; const fd = new FormData(form);
      await api('/day-override/', {method:'POST',body:JSON.stringify({action:'reset',staff_id:Number(fd.get('staff_id')),date:fd.get('date')})}); await renderSettings(view());
    }
  });

  document.addEventListener('submit', async event => {
    const appointment = event.target.closest('[data-ba-appointment-form]');
    if (appointment) { event.preventDefault(); try { await saveAppointment(appointment); } catch (e) { alert(e.message); } return; }
    if (event.target.matches('[data-ba-booking-search]')) { event.preventDefault(); state.bookingQuery = new FormData(event.target).get('q') || ''; await renderBookings(view()); return; }
    if (event.target.matches('[data-ba-customer-search]')) { event.preventDefault(); const q = new FormData(event.target).get('q') || ''; await renderCustomers(view(), q); return; }
    if (event.target.matches('[data-ba-block]')) {
      event.preventDefault(); const fd = new FormData(event.target);
      try { await api('/blocks/', {method:'POST',body:JSON.stringify({staff_id:Number(state.staff),date:state.date,start:fd.get('start'),end:fd.get('end'),kind:fd.get('kind'),text:fd.get('text')})}); await renderCalendar(view()); } catch(e) { alert(e.message); }
      return;
    }
    const service = event.target.closest('[data-ba-service]');
    if (service) {
      event.preventDefault(); const fd = new FormData(service);
      try { await api(`/services/${service.dataset.baService}/`, {method:'POST',body:JSON.stringify({name:fd.get('name'),price_label:fd.get('price_label'),duration_minutes:Number(fd.get('duration_minutes')),buffer_minutes:Number(fd.get('buffer_minutes')),active:fd.get('active')==='on',bookable:fd.get('bookable')==='on',requires_confirmation:fd.get('requires_confirmation')==='on'})}); await renderServices(view()); } catch(e) { alert(e.message); }
      return;
    }
    if (event.target.matches('[data-ba-override]')) {
      event.preventDefault(); const fd = new FormData(event.target); const closed = fd.get('closed') === 'on'; const ranges = closed ? [] : [{start:fd.get('start'),end:fd.get('end')}];
      try { await api('/day-override/', {method:'POST',body:JSON.stringify({staff_id:Number(fd.get('staff_id')),date:fd.get('date'),closed,ranges})}); await renderSettings(view()); } catch(e) { alert(e.message); }
    }
  });

  window.APlusBookAdmin = { open: openBookAdmin };
})();
