(() => {
  'use strict';

  const API = '/api/mobile/admin/book';
  const state = { tab: 'dashboard', date: new Date().toISOString().slice(0, 10), staff: '', cache: {} };
  const esc = (v = '') => String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const token = () => localStorage.getItem('aplus_token') || '';
  const content = () => document.querySelector('.shell .content');

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}), Accept: 'application/json' };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(`${API}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) {
      const err = new Error(body.message || body.error || `http_${response.status}`);
      err.status = response.status;
      throw err;
    }
    return body;
  }

  function tabs() {
    const items = [
      ['dashboard','Übersicht'],['calendar','Kalender'],['bookings','Buchungen'],
      ['customers','Kunden'],['services','Behandlungen'],['settings','Einstellungen']
    ];
    return `<div class="book-admin-tabs">${items.map(([key,label]) => `<button class="book-admin-tab ${state.tab===key?'active':''}" type="button" data-book-tab="${key}">${label}</button>`).join('')}</div>`;
  }

  function shell(inner) {
    return `<div class="book-admin">
      <div class="book-admin-head"><div><div class="book-admin-sub">A+ ESTHETIC · BOOK</div><h1 class="book-admin-title">Verwaltung</h1><p class="book-admin-sub">Kalender, Termine, Kunden und Einstellungen direkt in der App.</p></div><button class="book-admin-btn" type="button" data-book-back>← App Admin</button></div>
      ${tabs()}<div data-book-view>${inner}</div>
    </div>`;
  }

  function statusLabel(value) {
    return ({new:'Neu',confirmed:'Bestätigt',cancelled:'Abgesagt',completed:'Abgeschlossen',no_show:'Nicht erschienen'})[value] || value;
  }

  function appointmentRow(item, editable = false) {
    const base = `<b>${esc(item.start)} · ${esc(item.customer_name)}</b><small>${esc(item.service_name)} · ${esc(item.staff_name)}</small><span class="book-admin-badge">${esc(statusLabel(item.status))}</span>`;
    if (!editable) return `<div class="book-admin-row">${base}</div>`;
    return `<details class="book-admin-row"><summary>${base}</summary>
      <form class="book-admin-form" data-book-appointment="${item.id}" style="margin-top:10px">
        <div class="book-admin-grid"><label>Datum<input type="date" name="date" value="${esc(item.date)}"></label><label>Uhrzeit<input type="time" step="900" name="time" value="${esc(item.start)}"></label></div>
        <label>Status<select name="status">${['new','confirmed','completed','no_show','cancelled'].map(s=>`<option value="${s}" ${s===item.status?'selected':''}>${statusLabel(s)}</option>`).join('')}</select></label>
        <div class="book-admin-actions"><button class="book-admin-btn primary" type="submit">Speichern</button><button class="book-admin-btn danger" type="button" data-book-delete-appointment="${item.id}">Löschen</button></div>
      </form>
    </details>`;
  }

  function loading() { return '<div class="book-admin-loading">Wird geladen…</div>'; }
  function failure(error) { return `<div class="book-admin-error">${esc(error.message || error)}</div>`; }

  async function renderDashboard(target) {
    target.innerHTML = loading();
    try {
      const data = await api('/overview/');
      target.innerHTML = `<div class="book-admin-stats">
        <div class="book-admin-stat"><b>${data.stats.today}</b><small>Termine heute</small></div>
        <div class="book-admin-stat"><b>${data.stats.new_today}</b><small>Neu heute</small></div>
        <div class="book-admin-stat"><b>${data.stats.customers}</b><small>Kunden</small></div>
        <div class="book-admin-stat"><b>${data.stats.active_services}</b><small>Behandlungen</small></div>
      </div><section class="book-admin-card"><h3>Nächste Termine</h3><div class="book-admin-list">${data.upcoming.length ? data.upcoming.map(x=>appointmentRow(x)).join('') : '<div class="book-admin-empty">Keine kommenden Termine.</div>'}</div></section>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderCalendar(target) {
    target.innerHTML = loading();
    try {
      const query = new URLSearchParams({ date: state.date });
      if (state.staff) query.set('staff', state.staff);
      const data = await api(`/calendar/?${query}`);
      state.staff = String(data.selected_staff || '');
      state.cache.calendar = data;
      target.innerHTML = `<section class="book-admin-card">
        <div class="book-admin-toolbar"><label>Datum<input type="date" data-book-date value="${esc(data.date)}"></label><label>Behandler<select data-book-staff>${data.staff.map(s=>`<option value="${s.id}" ${String(s.id)===state.staff?'selected':''}>${esc(s.name)}</option>`).join('')}</select></label></div>
        <div class="book-admin-hours" style="margin-top:9px">${data.closed ? '<span>Geschlossen</span>' : data.ranges.map(r=>`<span>${esc(r.start)}–${esc(r.end)}</span>`).join('')}</div>
      </section>
      <section class="book-admin-card"><h3>Termine</h3><div class="book-admin-list">${data.appointments.length ? data.appointments.map(x=>appointmentRow(x,true)).join('') : '<div class="book-admin-empty">Keine Termine.</div>'}</div></section>
      <section class="book-admin-card"><h3>Sperrzeit / Notiz</h3>
        <form class="book-admin-form" data-book-block>
          <div class="book-admin-grid"><label>Von<input required type="time" step="900" name="start"></label><label>Bis<input required type="time" step="900" name="end"></label></div>
          <label>Typ<select name="kind"><option value="block">Zeitraum blockieren</option><option value="note">Notiz</option></select></label><label>Text<input name="text" maxlength="120" placeholder="Optional"></label>
          <button class="book-admin-btn primary" type="submit">Speichern</button>
        </form>
        <div class="book-admin-list" style="margin-top:10px">${data.blocks.map(b=>`<div class="book-admin-row"><b>${esc(b.start)}–${esc(b.end)} · ${b.note?'Notiz':'Gesperrt'}</b><small>${esc(b.reason)}</small><button class="book-admin-btn danger" type="button" data-book-delete-block="${b.id}">Löschen</button></div>`).join('')}</div>
      </section>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderBookings(target, q = '', status = '') {
    target.innerHTML = loading();
    try {
      const query = new URLSearchParams(); if (q) query.set('q', q); if (status) query.set('status', status);
      const data = await api(`/bookings/?${query}`);
      target.innerHTML = `<section class="book-admin-card"><form class="book-admin-form" data-book-search-bookings><div class="book-admin-grid"><label>Suche<input name="q" value="${esc(q)}" placeholder="Name, E-Mail, Behandlung"></label><label>Status<select name="status"><option value="">Alle</option>${['new','confirmed','completed','no_show','cancelled'].map(s=>`<option value="${s}" ${s===status?'selected':''}>${statusLabel(s)}</option>`).join('')}</select></label></div><button class="book-admin-btn" type="submit">Filtern</button></form></section>
        <div class="book-admin-list">${data.bookings.length ? data.bookings.map(x=>appointmentRow(x,true)).join('') : '<div class="book-admin-empty">Keine Buchungen gefunden.</div>'}</div>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderCustomerDetail(target, id) {
    target.innerHTML = loading();
    try {
      const data = await api(`/customers/${id}/`);
      const c = data.customer;
      target.innerHTML = `<button class="book-admin-btn" type="button" data-book-back-customers>← Kunden</button><section class="book-admin-card" style="margin-top:10px"><h3>${esc(c.name)}</h3><small>${esc(c.email)} · ${esc(c.phone || 'kein Telefon')}</small><div class="book-admin-stats" style="margin-top:10px"><div class="book-admin-stat"><b>${c.appointments}</b><small>Termine</small></div><div class="book-admin-stat"><b>${c.patient_records}</b><small>Akteneinträge</small></div></div></section>
        <section class="book-admin-card"><h3>Patientenakte</h3>${c.records.length ? c.records.map(r=>`<div class="book-admin-record"><b>${esc(r.title)}</b><small>${esc(r.kind)} · ${esc(r.source)} · ${r.shared_with_customer?'geteilt':'intern'}</small>${r.note?`<small>${esc(r.note)}</small>`:''}</div>`).join('') : '<div class="book-admin-empty">Keine Akteneinträge.</div>'}</section>
        <section class="book-admin-card"><h3>Terminverlauf</h3><div class="book-admin-list">${data.appointments.map(x=>appointmentRow(x)).join('')}</div></section>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderCustomers(target, q = '') {
    target.innerHTML = loading();
    try {
      const query = q ? `?q=${encodeURIComponent(q)}` : '';
      const data = await api(`/customers/${query}`);
      target.innerHTML = `<section class="book-admin-card"><form class="book-admin-form" data-book-search-customers><label>Suche<input name="q" value="${esc(q)}" placeholder="Name, E-Mail oder Telefon"></label><button class="book-admin-btn" type="submit">Suchen</button></form></section><div class="book-admin-list">${data.customers.length ? data.customers.map(c=>`<button class="book-admin-row" type="button" data-book-customer="${c.id}" style="text-align:left;width:100%"><b>${esc(c.name)}</b><small>${esc(c.email)} · ${esc(c.phone || 'kein Telefon')}</small><small>${c.appointments} Termine · ${c.patient_records} Akteneinträge</small></button>`).join('') : '<div class="book-admin-empty">Keine Kunden gefunden.</div>'}</div>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderServices(target) {
    target.innerHTML = loading();
    try {
      const data = await api('/services/');
      target.innerHTML = `<div class="book-admin-list">${data.services.map(s=>`<details class="book-admin-row"><summary><b>${esc(s.name)}</b><small>${esc(s.price_label || 'kein Preis')} · ${s.duration_minutes} Min. + ${s.buffer_minutes} Min. Puffer</small><span class="book-admin-badge">${s.active && s.bookable ? 'Buchbar' : (s.active?'Intern aktiv':'Inaktiv')}</span></summary><form class="book-admin-form" data-book-service="${s.id}" style="margin-top:10px"><label>Name<input name="name" value="${esc(s.name)}"></label><label>Preis<input name="price_label" value="${esc(s.price_label || '')}"></label><div class="book-admin-grid"><label>Dauer<input type="number" min="0" name="duration_minutes" value="${s.duration_minutes}"></label><label>Puffer<input type="number" min="0" name="buffer_minutes" value="${s.buffer_minutes}"></label></div><label><input type="checkbox" name="active" ${s.active?'checked':''}> Aktiv</label><label><input type="checkbox" name="bookable" ${s.bookable?'checked':''}> Online buchbar</label><label><input type="checkbox" name="requires_confirmation" ${s.requires_confirmation?'checked':''}> Manuelle Bestätigung</label><button class="book-admin-btn primary" type="submit">Speichern</button></form></details>`).join('')}</div>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderSettings(target) {
    target.innerHTML = loading();
    try {
      const data = await api('/settings/');
      state.cache.settings = data;
      target.innerHTML = `<section class="book-admin-card"><h3>Team & Arbeitszeiten</h3><div class="book-admin-list">${data.staff.map(s=>`<div class="book-admin-row"><b>${esc(s.name)}</b><small>${esc(s.role)} · ${s.services.map(x=>esc(x.name)).join(', ')}</small><div class="book-admin-hours">${s.working_hours.map(h=>`<span>${esc(h.weekday_label)} ${esc(h.start)}–${esc(h.end)}</span>`).join('')}</div></div>`).join('')}</div></section>
        <section class="book-admin-card"><h3>Tages-Verfügbarkeit</h3><form class="book-admin-form" data-book-override><div class="book-admin-grid"><label>Behandler<select name="staff_id">${data.staff.filter(s=>s.active).map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></label><label>Datum<input required type="date" name="date" value="${state.date}"></label></div><label><input type="checkbox" name="closed"> Ganztägig nicht verfügbar</label><div class="book-admin-grid"><label>Von<input type="time" step="900" name="start" value="09:00"></label><label>Bis<input type="time" step="900" name="end" value="18:00"></label></div><div class="book-admin-actions"><button class="book-admin-btn primary" type="submit">Ausnahme speichern</button><button class="book-admin-btn" type="button" data-book-reset-override>Zurücksetzen</button></div></form></section>
        <section class="book-admin-card"><h3>Kommende Ausnahmen</h3><div class="book-admin-list">${data.upcoming_overrides.length ? data.upcoming_overrides.map(o=>`<div class="book-admin-row"><b>${esc(o.date)} · ${esc(o.staff_name)}</b><small>${o.closed?'Geschlossen':o.ranges.map(r=>`${esc(r.start)}–${esc(r.end)}`).join(' / ')}</small></div>`).join('') : '<div class="book-admin-empty">Keine Ausnahmen.</div>'}</div></section>`;
    } catch (error) { target.innerHTML = failure(error); }
  }

  async function renderTab() {
    const target = document.querySelector('[data-book-view]'); if (!target) return;
    document.querySelectorAll('[data-book-tab]').forEach(b=>b.classList.toggle('active', b.dataset.bookTab===state.tab));
    if (state.tab === 'dashboard') return renderDashboard(target);
    if (state.tab === 'calendar') return renderCalendar(target);
    if (state.tab === 'bookings') return renderBookings(target);
    if (state.tab === 'customers') return renderCustomers(target);
    if (state.tab === 'services') return renderServices(target);
    if (state.tab === 'settings') return renderSettings(target);
  }

  async function openBookAdmin() {
    const target = content(); if (!target) return;
    target.innerHTML = shell(loading());
    await renderTab();
  }

  async function saveAppointment(form) {
    const id = form.dataset.bookAppointment;
    const data = new FormData(form);
    await api(`/appointments/${id}/`, { method:'POST', body:JSON.stringify({ date:data.get('date'), time:data.get('time'), status:data.get('status') }) });
    await renderTab();
  }

  document.addEventListener('click', async event => {
    const bookLink = event.target.closest('a[href*="book.a-esthetic.de/verwaltung"]');
    if (bookLink) { event.preventDefault(); event.stopPropagation(); await openBookAdmin(); return; }
    const tab = event.target.closest('[data-book-tab]'); if (tab) { state.tab = tab.dataset.bookTab; await renderTab(); return; }
    if (event.target.closest('[data-book-back]')) {
      document.querySelector('.nav [data-route="more"]')?.click();
      setTimeout(()=>document.querySelector('[data-ops-admin]')?.click(), 80);
      return;
    }
    const customer = event.target.closest('[data-book-customer]'); if (customer) { await renderCustomerDetail(document.querySelector('[data-book-view]'), customer.dataset.bookCustomer); return; }
    if (event.target.closest('[data-book-back-customers]')) return renderCustomers(document.querySelector('[data-book-view]'));
    const delAppt = event.target.closest('[data-book-delete-appointment]'); if (delAppt) {
      if (!confirm('Termin wirklich löschen?')) return;
      await api(`/appointments/${delAppt.dataset.bookDeleteAppointment}/`, { method:'POST', body:JSON.stringify({action:'delete'}) }); await renderTab(); return;
    }
    const delBlock = event.target.closest('[data-book-delete-block]'); if (delBlock) {
      await api('/blocks/', { method:'POST', body:JSON.stringify({action:'delete', id:Number(delBlock.dataset.bookDeleteBlock)}) }); await renderCalendar(document.querySelector('[data-book-view]')); return;
    }
    if (event.target.closest('[data-book-reset-override]')) {
      const form = event.target.closest('form'); const fd = new FormData(form);
      await api('/day-override/', { method:'POST', body:JSON.stringify({action:'reset',staff_id:Number(fd.get('staff_id')),date:fd.get('date')}) }); await renderSettings(document.querySelector('[data-book-view]')); return;
    }
  });

  document.addEventListener('change', async event => {
    if (event.target.matches('[data-book-date]')) { state.date = event.target.value; await renderCalendar(document.querySelector('[data-book-view]')); }
    if (event.target.matches('[data-book-staff]')) { state.staff = event.target.value; await renderCalendar(document.querySelector('[data-book-view]')); }
  });

  document.addEventListener('submit', async event => {
    const appointment = event.target.closest('[data-book-appointment]'); if (appointment) { event.preventDefault(); try { await saveAppointment(appointment); } catch(e){ alert(e.message); } return; }
    if (event.target.matches('[data-book-search-bookings]')) { event.preventDefault(); const fd=new FormData(event.target); await renderBookings(document.querySelector('[data-book-view]'), fd.get('q')||'', fd.get('status')||''); return; }
    if (event.target.matches('[data-book-search-customers]')) { event.preventDefault(); const fd=new FormData(event.target); await renderCustomers(document.querySelector('[data-book-view]'), fd.get('q')||''); return; }
    if (event.target.matches('[data-book-block]')) { event.preventDefault(); const fd=new FormData(event.target); try { await api('/blocks/', {method:'POST',body:JSON.stringify({staff_id:Number(state.staff),date:state.date,start:fd.get('start'),end:fd.get('end'),kind:fd.get('kind'),text:fd.get('text')})}); await renderCalendar(document.querySelector('[data-book-view]')); } catch(e){alert(e.message);} return; }
    const service = event.target.closest('[data-book-service]'); if (service) { event.preventDefault(); const fd=new FormData(service); try { await api(`/services/${service.dataset.bookService}/`, {method:'POST',body:JSON.stringify({name:fd.get('name'),price_label:fd.get('price_label'),duration_minutes:Number(fd.get('duration_minutes')),buffer_minutes:Number(fd.get('buffer_minutes')),active:fd.get('active')==='on',bookable:fd.get('bookable')==='on',requires_confirmation:fd.get('requires_confirmation')==='on'})}); await renderServices(document.querySelector('[data-book-view]')); } catch(e){alert(e.message);} return; }
    if (event.target.matches('[data-book-override]')) { event.preventDefault(); const fd=new FormData(event.target); const closed=fd.get('closed')==='on'; const ranges=closed?[]:[{start:fd.get('start'),end:fd.get('end')}]; try { await api('/day-override/', {method:'POST',body:JSON.stringify({staff_id:Number(fd.get('staff_id')),date:fd.get('date'),closed,ranges})}); await renderSettings(document.querySelector('[data-book-view]')); } catch(e){alert(e.message);} }
  });
})();
