import {createCalendar, dateLabel, today} from './calendar.mjs';

const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch =>
  ({'&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;'}[ch]));
const labels = {new:'Offen', confirmed:'Bestätigt', cancelled:'Abgesagt', completed:'Abgeschlossen', no_show:'Nicht erschienen'};
const tabs = [
  ['overview','Übersicht','dashboard'], ['calendar','Kalender','appointments'],
  ['appointments','Termine','records'], ['patients','Patienten','friends'], ['settings','Mehr','settings'],
];
const icons = window.AEstheticIconSet;
const itemButton = (action, id, title, secondary = '', end = '') =>
  `<button type="button" class="mw-row" data-mw-action="${action}" data-id="${id}">
    <span><strong>${esc(title)}</strong><small>${esc(secondary)}</small></span>
    <span class="mw-row-end">${end ? `<small>${esc(end)}</small>` : ''}<span aria-hidden="true">›</span></span></button>`;
const empty = message => `<p class="mw-empty">${esc(message)}</p>`;
const connectionMessage = failure => {
  const status = Number(failure?.status || 0);
  if (status === 404) return 'Die Buchungs-API ist nicht verfügbar (HTTP 404).';
  if (status === 502 || status === 503 || status === 504)
    return `Der Buchungsdienst ist vorübergehend nicht erreichbar (HTTP ${status}).`;
  if (status === 429) return 'Zu viele Anfragen. Bitte versuchen Sie es erneut (HTTP 429).';
  if (status) return `Die Anfrage ist fehlgeschlagen (HTTP ${status}).`;
  return 'Die Verbindung konnte nicht hergestellt werden. Bitte prüfen Sie das Netzwerk.';
};
const input = (label, name, attrs) => `<label class="mw-field">${label}<input name="${name}" ${attrs}></label>`;
const options = (items, value) => items.map(item =>
  `<option value="${esc(item.id)}" ${String(item.id) === String(value) ? 'selected' : ''}>${esc(item.name)}</option>`).join('');
const select = (label, name, items, value) =>
  `<label class="mw-field">${label}<select name="${name}" aria-label="${label}" required>${options(items,value)}</select></label>`;
const check = (label, name, selected) =>
  `<label class="mw-check"><input type="checkbox" name="${name}" ${selected?'checked':''}>${label}</label>`;
const formWrap = inner => `<form class="mw-form" data-own-submit>${inner}
  <p class="mw-form-error" role="alert" hidden></p><button class="mw-primary" type="submit">Speichern</button></form>`;
const appointmentRow = item => itemButton('appointment', item.id, item.customer_name,
  item.service_name + ' · ' + item.staff_name,
  (item.date === today() ? '' : dateLabel(item.date,{day:'numeric',month:'numeric'})+' · ') +
  item.start + ' · ' + (labels[item.status] || item.status));
const displayDay = date => dateLabel(date,{weekday:'long', day:'numeric', month:'long'});

export function mountWorkspace({root, token, identity, origin, logout}) {
  const doctor = identity.role === 'doctor';
  const lifetime = new AbortController();
  const requests = new AbortController();
  let view = doctor ? 'calendar' : 'overview';
  let subsection = '';
  let calendar;
  let catalog;
  let generation = 0;
  let currentItems = new Map();
  let sheet;
  let identityFailure = false;

  root.innerHTML = `<div class="mw">
    <header class="mw-header">
      <div class="mw-brand"><img src="./assets/logo.svg" alt=""><span>A+ ESTHETIC</span></div>
      <span class="mw-role">${doctor?'Arztzugang':'Verwaltung'}</span>
    </header>
    <main class="mw-main" data-mw-main></main>
    <nav class="mw-nav" aria-label="Praxisnavigation">${tabs.map(([id,label,icon]) =>
      `<button type="button" data-mw-tab="${id}">${icons[icon] || ''}<span>${label}</span></button>`).join('')}</nav>
    <div role="status" class="mw-toast" hidden></div>
  </div>`;
  const surface = root.firstElementChild;
  const main = surface.querySelector('main');
  const live = surface.querySelector('.mw-toast');
  let toastTimer;

  async function request(path, {json, signal, blob = false} = {}) {
    const response = await fetch(origin + '/api/mobile/' + path, {
      method:json === undefined ? 'GET' : 'POST',
      cache:'no-store', credentials:'omit', aplusSilent:true,
      headers:{Authorization:'Bearer ' + token, ...(json === undefined ? {} : {'Content-Type':'application/json'})},
      body:json === undefined ? undefined : JSON.stringify(json),
      signal: AbortSignal.any([requests.signal, signal || requests.signal, AbortSignal.timeout(14000)]),
    });
    if (blob && response.ok) return response.blob();
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.ok === false) {
      const error = new Error(result.message || 'Der Server konnte die Anfrage nicht abschließen.');
      error.status = response.status;
      error.code = result.error || '';
      throw error;
    }
    return result;
  }
  const api = (path, opts) => request('staff/book/' + path, opts);

  function toast(message) {
    live.textContent = message;
    live.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { live.hidden = true; }, 3400);
  }

  const showError = failure => {
    if (lifetime.signal.aborted) return true;
    if (failure.status === 401) { logout(); return true; }
    if (failure.status === 403) {
      identityFailure = true;
      calendar?.destroy();
      closeSheet();
      main.innerHTML = `<div class="mw-page"><h1>Zugang eingeschränkt</h1>
        <p>Die Praxisdaten sind mit diesem Zugang nicht verfügbar.</p>
        <button type="button" class="mw-primary" data-mw-action="logout">Abmelden</button></div>`;
      return true;
    }
    return false;
  };

  async function navigate(next, sub = '') {
    if (identityFailure) return;
    view = next;
    subsection = sub;
    const run = ++generation;
    calendar?.destroy();
    calendar = null;
    closeSheet();
    currentItems = new Map();
    surface.querySelectorAll('[data-mw-tab]').forEach(button => {
      button.setAttribute('aria-current', button.dataset.mwTab === view ? 'page' : 'false');
    });
    main.innerHTML = '<p class="mw-loading" role="status">Wird geladen …</p>';
    const current = () => !lifetime.signal.aborted && run === generation;
    try {
      if (next === 'calendar') {
        catalog ||= await api('catalog/');
        if (current()) calendar = createCalendar(main, {api, catalog, escape:esc,
          select:showCalendarItem, add:newCalendarItem, error:showError});
      } else if (next === 'overview') {
        const data = await api('overview/');
        if (!current()) return;
        currentItems = new Map(data.upcoming.map(row => [row.id, row]));
        const first = identity.name?.trim().split(' ')[0];
        main.innerHTML = `<section class="mw-page">
          <p class="mw-meta">${esc(displayDay(today()))}</p>
          <h1>${first ? 'Hallo, '+esc(first) : 'Praxisübersicht'}</h1>
          <button type="button" class="mw-feature" data-mw-tab="calendar">
            <span><small>Termine heute</small><strong>${Number(data.today)}</strong></span>
            <span>Zum Kalender <b aria-hidden="true">↗︎</b></span>
          </button>
          <h2>Als Nächstes</h2>
          <div class="mw-list">${data.upcoming.map(appointmentRow).join('') || empty('Keine bevorstehenden Termine.')}</div>
        </section>`;
      } else if (next === 'appointments' || next === 'patients') {
        const patient = next === 'patients';
        main.innerHTML = `<section class="mw-page">
          <h1>${patient?'Patienten':'Termine'}</h1>
          <form class="mw-search" data-own-submit role="search">
            <input name="q" aria-label="${patient?'Patienten suchen':'Termine suchen'}" type="search" placeholder="${patient?'Name, E-Mail oder Telefon':'Name oder Behandlung'}">
            <button type="submit">Suchen</button>
          </form><div class="mw-list" data-mw-results></div>
        </section>`;
        const form = main.querySelector('form');
        const results = main.querySelector('[data-mw-results]');
        let searchVersion = 0;
        let page = 1;
        async function search(replace = true) {
          const searchId = ++searchVersion;
          if (replace) { page = 1; results.innerHTML = '<p class="mw-loading" role="status">Wird geladen …</p>'; }
          results.querySelector('[data-mw-more]')?.remove();
          try {
            const data = await api(`${next}/?q=${encodeURIComponent(form.elements.q.value)}&page=${page}`);
            if (!current() || searchId !== searchVersion) return;
            if (!patient) for (const row of data.items) currentItems.set(row.id,row);
            const rows = data.items.map(row => patient
              ? itemButton('patient',row.id,row.name,row.email || row.phone)
              : appointmentRow(row)).join('');
            if (replace) results.innerHTML = rows || empty('Keine Treffer.');
            else results.insertAdjacentHTML('beforeend', rows);
            if (data.has_more) {
              const more = document.createElement('button');
              more.type = 'button';
              more.dataset.mwMore = '';
              more.className = 'mw-secondary';
              more.textContent = 'Weitere laden';
              more.onclick = () => { page++; void search(false); };
              results.append(more);
            }
          } catch (failure) {
            if (current() && searchId === searchVersion && !showError(failure)) {
              results.innerHTML = `${empty(connectionMessage(failure))}
                <button class="mw-secondary" type="button" data-mw-search-retry>Erneut versuchen</button>`;
              results.querySelector('[data-mw-search-retry]').onclick = () => void search();
            }
          }
        }
        form.onsubmit = event => { event.preventDefault(); void search(); };
        void search();
      } else if (next === 'settings') {
        await settings(sub, current);
      }
    } catch (failure) {
      if (!current() || showError(failure)) return;
      main.innerHTML = `<div class="mw-page"><h1>Verbindung unterbrochen</h1>
        <p role="alert">${esc(connectionMessage(failure))}</p>
        <button class="mw-primary" type="button" data-mw-action="retry">Erneut versuchen</button></div>`;
    }
  }

  async function settings(sub, current) {
    if (!sub) {
      main.innerHTML = `<section class="mw-page"><h1>Mehr</h1><p class="mw-meta">${esc(identity.name || '')}</p>
        <div class="mw-list">
        ${itemButton('settings','providers','Behandler und Arbeitszeiten')}
        ${doctor ? '' : itemButton('settings','services','Behandlungen') +
          itemButton('settings','packages','Pakete') + itemButton('settings','points','A+ Punkte') +
          itemButton('settings','notifications','Benachrichtigungen')}
        ${itemButton('settings','account','Konto und Einstellungen')}</div></section>`;
      return;
    }
    let heading;
    let content;
    if (sub === 'providers' || sub === 'services') {
      catalog ||= await api('catalog/');
      heading = sub === 'providers' ? 'Behandler' : 'Behandlungen';
      content = sub === 'providers' ? catalog.providers.map(person => itemButton('hours',person.id,person.name,'Arbeitszeiten und Ausnahmen')).join('')
        : catalog.services.map(service => itemButton('service',service.id,service.name,service.duration_minutes+' Min.',service.active?'Aktiv':'Inaktiv')).join('');
    } else if (sub === 'packages' && !doctor) {
      heading = 'Pakete';
      const data = await request('admin/packages/');
      content = data.packages.map(item => `<article class="mw-static-row"><strong>${esc(item.name)}</strong>
        <small>${esc(item.customer)} · ${Number(item.remaining_sessions)} Einheiten</small></article>`).join('');
    } else if (sub === 'points' && !doctor) {
      heading = 'A+ Punkte';
      content = `<form class="mw-search" role="search" data-own-submit>
        <input name="q" placeholder="Name oder E-Mail" aria-label="Mitglied suchen" required><button type="submit">Suchen</button></form>
        <div data-mw-points></div>`;
    } else if (sub === 'notifications' && !doctor) {
      heading = 'Benachrichtigungen';
      const data = await request('admin/notifications/history/');
      content = data.notifications.map(item => `<article class="mw-static-row"><strong>${esc(item.title)}</strong>
        <small>${esc(item.customer)} · ${item.read?'Gelesen':'Ungelesen'}</small><p>${esc(item.body)}</p></article>`).join('');
    } else {
      heading = 'Konto und Einstellungen';
      content = `<p>${esc(identity.name || '')} · ${doctor?'Arztzugang':'Verwaltung'}</p>
        ${doctor || origin.startsWith('http://127.0.0.1') ? '' : '<button type="button" class="mw-secondary" data-mw-action="desktop">Desktop-Verwaltung öffnen</button>'}
        <button type="button" class="mw-danger" data-mw-action="logout">Abmelden</button>`;
    }
    if (!current()) return;
    main.innerHTML = `<section class="mw-page"><button class="mw-secondary" type="button" data-mw-tab="settings">‹ Mehr</button>
      <h1>${esc(heading)}</h1><div class="mw-list">${content || empty('Keine Einträge.')}</div></section>`;
    if (sub !== 'points') return;
    const form = main.querySelector('form');
    const result = main.querySelector('[data-mw-points]');
    let searchVersion = 0;
    form.onsubmit = async event => {
      event.preventDefault();
      const id = ++searchVersion;
      result.innerHTML = '<p class="mw-loading">Wird geladen …</p>';
      try {
        const data = await request('admin/customers/?q=' + encodeURIComponent(form.elements.q.value));
        if (id !== searchVersion || !current()) return;
        result.innerHTML = data.customers.map(row => itemButton('points-account',row.id,row.name,row.email,row.coins+' Punkte')).join('') || empty('Keine Treffer.');
      } catch (failure) {
        if (id === searchVersion && current() && !showError(failure)) result.textContent = 'Suche fehlgeschlagen.';
      }
    };
  }

  function closeSheet() { sheet?.close(); sheet = null; }

  function openSheet(title, content) {
    closeSheet();
    const dialog = document.createElement('dialog');
    dialog.className = 'mw-sheet';
    dialog.setAttribute('aria-labelledby', 'mw-sheet-title');
    dialog.innerHTML = `<div class="mw-sheet-inner"><header><h2 id="mw-sheet-title">${esc(title)}</h2>
      <button type="button" data-close-sheet aria-label="Schließen">×</button></header><div data-sheet-body>${content}</div></div>`;
    surface.append(dialog);
    sheet = dialog;
    dialog.addEventListener('close', () => {
      if (sheet === dialog) sheet = null;
      dialog.remove();
    });
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    dialog.querySelector('[data-close-sheet]').onclick = () => dialog.close();
    dialog.showModal();
    return dialog;
  }

  function sheetError(dialog, failure) {
    if (!dialog.open || showError(failure)) return;
    const info = dialog.querySelector('.mw-form-error, [data-sheet-error]');
    if (!info) return;
    info.hidden = false;
    info.textContent = failure.status
      ? failure.message : 'Verbindung unterbrochen. Sie können den gleichen Auftrag erneut senden.';
  }

  function bindCommand(dialog, endpoint, values, after, send = api) {
    const form = dialog.querySelector('form.mw-form');
    let fingerprint;
    let key;
    form.onsubmit = async event => {
      event.preventDefault();
      const submit = form.querySelector('[type=submit]');
      if (submit.disabled) return;
      const error = form.querySelector('.mw-form-error');
      error.hidden = true;
      const body = values(form);
      if (!body) return;
      if (fingerprint !== JSON.stringify(body)) {
        fingerprint = JSON.stringify(body);
        key = crypto.randomUUID();
      }
      const title = submit.textContent;
      submit.disabled = true;
      submit.textContent = 'Wird gespeichert …';
      try {
        await send(endpoint, {json:{...body,key}});
        if (lifetime.signal.aborted) return;
        if (dialog.open) closeSheet();
        toast(endpoint === 'appointment/' && body.operation === 'cancel'
          ? 'Termin abgesagt. Paketguthaben wird geprüft.' : 'Gespeichert.');
        after?.();
        if (calendar) calendar.invalidate();
      } catch (failure) {
        sheetError(dialog, failure);
      } finally {
        submit.disabled = false;
        submit.textContent = title;
      }
    };
  }

  async function openPatient(id, page = 1) {
    const dialog = openSheet('Patientenakte','<p role="status">Wird geladen …</p>');
    try {
      const data = await api(`patient/${id}/?page=${page}`);
      if (!dialog.open) return;
      dialog.querySelector('[data-sheet-body]').innerHTML = `<h3>${esc(data.patient.name)}</h3>
        <p>${esc([data.patient.email,data.patient.phone].filter(Boolean).join(' · '))}</p>
        <h3>Dokumente und Notizen</h3>
        <button class="mw-secondary" type="button" data-record-note>Aktennotiz hinzufügen</button>${data.records.map(record => `<article class="mw-static-row">
          <strong>${esc(record.title)}</strong><p>${esc(record.note)}</p>
          ${record.has_file ? `<button class="mw-secondary" type="button" data-record="${esc(record.id)}" data-filename="${esc(record.filename)}">Datei laden</button>` : ''}</article>`).join('') || empty('Keine freigegebenen Einträge.')}
        <p data-sheet-error class="mw-form-error" role="alert" hidden></p>
        ${page > 1 ? '<button class="mw-secondary" type="button" data-page="previous">Vorherige</button>' : ''}
        ${data.has_more ? '<button class="mw-secondary" type="button" data-page="next">Weitere Einträge</button>' : ''}
        <h3>Letzte Termine</h3>${data.appointments.map(row => `<article class="mw-static-row"><strong>${esc(row.service_name)}</strong>
          <small>${esc(row.date)} · ${esc(row.start)} · ${esc(labels[row.status] || row.status)}</small></article>`).join('') || empty('Keine Termine.')}`;
      dialog.querySelector('[data-record-note]').onclick = () => {
        const note = openSheet('Aktennotiz hinzufügen', formWrap(
          input('Titel','title','required maxlength="180"') +
          '<label class="mw-field">Interne Notiz<textarea name="note" rows="5" required maxlength="6000"></textarea></label>',
        ));
        bindCommand(note,'record-note/',form => ({...Object.fromEntries(new FormData(form)),customer_id:id}),
          () => void openPatient(id));
      };
      dialog.querySelectorAll('[data-page]').forEach(button => {
        button.onclick = () => void openPatient(id,page+(button.dataset.page === 'next'?1:-1));
      });
      dialog.querySelectorAll('[data-record]').forEach(button => {
        button.onclick = async () => {
          button.disabled = true;
          try {
            const file = await api(`patient/${id}/records/${button.dataset.record}/`, {blob:true});
            if (!dialog.open) return;
            const url = URL.createObjectURL(file);
            const link = document.createElement('a');
            link.href = url;
            link.download = button.dataset.filename || 'APlus-Dokument';
            dialog.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 5000);
          } catch (failure) { sheetError(dialog, failure); }
          finally { button.disabled = false; }
        };
      });
    } catch (failure) {
      if (dialog.open && !showError(failure)) dialog.querySelector('[data-sheet-body]').textContent = 'Die Patientenakte konnte nicht geladen werden.';
    }
  }

  function showCalendarItem(item) {
    if (item.type !== 'appointment') {
      const editable = item.editable;
      const dialog = openSheet(item.type === 'note'?'Kalendernotiz':'Gesperrte Zeit',
        `<p><strong>${esc(item.text)}</strong></p><p>${esc(displayDay(item.date))} · ${esc(item.start)}–${esc(item.end)}</p>
        ${editable ? '<button class="mw-secondary" type="button" data-edit-block>Bearbeiten</button>' : ''}`);
      dialog.querySelector('[data-edit-block]')?.addEventListener('click', () => blockForm(item.date,item.staff_id,item.type,item));
      return;
    }
    const dialog = openSheet('Termindetails', `<div class="mw-detail">
      <h3>${esc(item.customer_name)}</h3><p>${esc(item.service_name)}</p>
      <p>${esc(displayDay(item.date))} · ${esc(item.start)}–${esc(item.end)}<br>${esc(item.staff_name)}</p>
      <p class="mw-tag">${esc(labels[item.status] || item.status)}</p>
      ${item.credit_pending?'<p>Die Paketgutschrift wird geprüft.</p>':''}
      ${item.source_managed?'<p>Änderungen sind im angebundenen Buchungssystem möglich.</p>':''}
      <button class="mw-secondary" type="button" data-detail-patient>Patientenakte öffnen</button>
      ${!item.source_managed && item.status !== 'cancelled' ? '<button class="mw-secondary" type="button" data-detail-edit>Termin bearbeiten</button><button class="mw-danger" type="button" data-detail-cancel>Termin absagen</button>' : ''}
      </div>`);
    dialog.querySelector('[data-detail-patient]').onclick = () => void openPatient(item.customer_id);
    dialog.querySelector('[data-detail-edit]')?.addEventListener('click', () => void appointmentForm(item.date,item.staff_id,item));
    dialog.querySelector('[data-detail-cancel]')?.addEventListener('click', () => {
      const confirmation = openSheet('Termin absagen', formWrap(`<p>Termin für <strong>${esc(item.customer_name)}</strong> am ${esc(displayDay(item.date))} um ${esc(item.start)} absagen?</p>`));
      confirmation.querySelector('[type=submit]').textContent = 'Absage bestätigen';
      bindCommand(confirmation,'appointment/',() => ({operation:'cancel',id:item.id,revision:item.revision}),
        () => { if (view !== 'calendar') void navigate(view,subsection); });
    });
  }

  function newCalendarItem(date, provider) {
    const dialog = openSheet('Zum Kalender hinzufügen', `<div class="mw-list">
      ${itemButton('new','appointment','Neuer Termin')}${itemButton('new','block','Zeit sperren')}
      ${itemButton('new','note','Notiz hinzufügen')}${itemButton('new','hours','Verfügbarkeit ändern')}</div>`);
    dialog.addEventListener('click', event => {
      const button = event.target.closest('[data-mw-action=new]');
      if (!button) return;
      const choice = button.dataset.id;
      if (choice === 'appointment') void appointmentForm(date,provider);
      else if (choice === 'hours') void hoursForm(date,provider).catch(failure => {
        if (!showError(failure)) toast('Arbeitszeiten konnten nicht geladen werden.');
      });
      else blockForm(date,provider,choice);
    });
  }

  async function appointmentForm(date, provider, item = null) {
    try {
      catalog ||= await api('catalog/');
    } catch (failure) {
      if (!showError(failure)) toast('Behandlungen konnten nicht geladen werden.');
      return;
    }
    if (lifetime.signal.aborted) return;
    const statusItems = Object.entries(labels).filter(([id]) => id !== 'cancelled').map(([id,name]) => ({id,name}));
    const providers = item ? catalog.providers.filter(row => row.services.includes(item.service_id)) : catalog.providers;
    const dialog = openSheet(item?'Termin bearbeiten':'Neuer Termin', `
      ${item ? '' : `<form class="mw-search" data-own-submit role="search">
        <input type="search" aria-label="Patient suchen" placeholder="Patient suchen" name="q" required>
        <button type="submit">Suchen</button></form><p data-sheet-error role="alert" class="mw-form-error" hidden></p>`}
      ${formWrap(`
        ${item ? `<p><strong>${esc(item.customer_name)}</strong><br>${esc(item.service_name)}</p>` : select('Patient','customer_id',[{id:'',name:'Über die Suche auswählen'}])}
        ${select('Behandler','staff_id',providers,provider)}
        ${item?'':select('Behandlung','service_id',[])}
        <div class="mw-pair">${input('Datum','date',`type="date" required value="${esc(date)}"`)}
          ${input('Beginn','start',`type="time" step="900" required value="${esc(item?.start || '10:00')}"`)}</div>
        ${item ? select('Status','status',statusItems,item.status) : ''}
      `)}`);
    const form = dialog.querySelector('.mw-form');
    if (!item) {
      const search = dialog.querySelector('.mw-search');
      search.onsubmit = async event => {
        event.preventDefault();
        const query = search.elements.q.value.trim();
        if (!query) return;
        const submit = search.querySelector('button');
        submit.disabled = true;
        try {
          const data = await api('patients/?q=' + encodeURIComponent(query));
          if (!dialog.open) return;
          form.elements.customer_id.innerHTML = options(data.items.length ? data.items.map(row =>
            ({id:row.id,name:row.name+(row.email ? ' · '+row.email : '')})) : [{id:'',name:'Keine Treffer'}]);
        } catch (failure) { sheetError(dialog,failure); }
        finally { submit.disabled = false; }
      };
      const updateServices = () => {
        const allowed = catalog.providers.find(row => String(row.id) === form.elements.staff_id.value)?.services || [];
        form.elements.service_id.innerHTML = options(catalog.services.filter(row =>
          row.active && row.bookable && allowed.includes(row.id)));
      };
      form.elements.staff_id.onchange = updateServices;
      updateServices();
    }
    bindCommand(dialog,'appointment/', form => {
      const values = Object.fromEntries(new FormData(form));
      return item ? {...values, operation:'update', id:item.id, revision:item.revision,
        customer_id:item.customer_id, service_id:item.service_id} : {...values,operation:'create'};
    }, () => { if (view !== 'calendar') void navigate(view,subsection); });
  }

  function blockForm(date, provider, kind, item = null) {
    const dialog = openSheet(kind === 'note' ? 'Kalendernotiz' : 'Zeit sperren', formWrap(
      select('Behandler','staff_id',item ? catalog.providers.filter(row => row.id === item.staff_id) : catalog.providers, provider) +
      input('Datum','date',`type="date" value="${esc(date)}" required`) +
      `<div class="mw-pair">${input('Beginn','start',`type="time" step="900" required value="${esc(item?.start || '10:00')}"`)}
      ${input('Ende','end',`type="time" step="900" required value="${esc(item?.end || '11:00')}"`)}</div>` +
      input(kind === 'note'?'Notiz':'Grund','text',`maxlength="120" value="${esc(item?.text || '')}" ${kind === 'note'?'required':''}`) +
      (item ? '<button class="mw-danger" type="button" data-block-delete>Eintrag löschen</button>' : ''),
    ));
    bindCommand(dialog, 'block/', form => ({
      ...Object.fromEntries(new FormData(form)), operation:item?'update':'create', kind, ...(item?{id:item.id}:{}),
    }));
    dialog.querySelector('[data-block-delete]')?.addEventListener('click', () => {
      const confirm = openSheet('Eintrag löschen', formWrap('<p>Diesen Kalendereintrag entfernen?</p>'));
      confirm.querySelector('[type=submit]').textContent = 'Löschen bestätigen';
      bindCommand(confirm,'block/',() => ({operation:'delete',staff_id:item.staff_id,id:item.id}));
    });
  }

  async function hoursForm(date, provider) {
    catalog ||= await api('catalog/');
    if (lifetime.signal.aborted) return;
    const dialog = openSheet('Verfügbarkeit', formWrap(
      select('Behandler','staff_id',catalog.providers,provider) + input('Datum','date',`type="date" value="${esc(date)}" required`) +
      select('Gültigkeit','operation',[{id:'daily',name:'Nur dieses Datum'},{id:'weekly',name:'Wöchentlich an diesem Wochentag'},
        {id:'reset',name:'Tagesausnahme entfernen'}],'daily') +
      check('Geschlossen','closed',false) +
      '<div class="mw-pair">'+input('Von','start_1','type="time" step="900"')+input('Bis','end_1','type="time" step="900"')+'</div>'+
      '<div class="mw-pair">'+input('Zweiter Zeitraum von','start_2','type="time" step="900"')+input('Bis','end_2','type="time" step="900"')+'</div>'));
    const form = dialog.querySelector('form');
    let version = 0;
    const fill = async () => {
      const run = ++version;
      const {date,staff_id,operation,closed} = form.elements;
      const info = form.querySelector('.mw-form-error');
      info.hidden = true;
      if (!date.value || !staff_id.value) return;
      let ranges = [];
      try {
        if (operation.value === 'daily') {
          const data = await api(`calendar/?start=${date.value}&days=1`);
          ranges = data.availability.find(row=>row.staff_id === Number(staff_id.value))?.ranges || [];
        } else if (operation.value === 'weekly') {
          const weekday = (new Date(date.value+'T12:00:00Z').getUTCDay()+6)%7;
          ranges = catalog.providers.find(row=>row.id===Number(staff_id.value))?.working_hours
            .filter(row=>row.weekday===weekday) || [];
        }
        if (run !== version || !dialog.open) return;
        closed.checked = !ranges.length;
        for (const index of [1,2]) {
          form.elements['start_'+index].value = ranges[index-1]?.start || '';
          form.elements['end_'+index].value = ranges[index-1]?.end || '';
        }
      } catch (failure) { sheetError(dialog,failure); }
    };
    for (const name of ['date','staff_id','operation']) form.elements[name].onchange = () => void fill();
    void fill();
    bindCommand(dialog,'availability/', form => ({...Object.fromEntries(new FormData(form)),closed:form.elements.closed.checked}),
      () => { if (!calendar) { catalog=null; void navigate(view,subsection); } });
  }

  function serviceForm(id) {
    const item = catalog.services.find(row => row.id === id);
    if (!item) return;
    const dialog = openSheet('Behandlung bearbeiten', formWrap(
      input('Name','name',`value="${esc(item.name)}" maxlength="140" required`) +
      input('Preisangabe','price_label',`value="${esc(item.price_label)}" maxlength="80"`) +
      '<div class="mw-pair">'+input('Dauer (Min.)','duration_minutes',`type="number" min="1" required value="${Number(item.duration_minutes)}"`)+
      input('Puffer (Min.)','buffer_minutes',`type="number" min="0" required value="${Number(item.buffer_minutes)}"`)+'</div>'+
      check('Aktiv','active',item.active)+check('Online buchbar','bookable',item.bookable)+
      check('Bestätigung erforderlich','requires_confirmation',item.requires_confirmation)));
    bindCommand(dialog,'service/',form => ({
      ...Object.fromEntries(new FormData(form)),id,
      ...Object.fromEntries(['active','bookable','requires_confirmation'].map(name => [name,form.elements[name].checked])),
    }),() => { catalog=null; void navigate(view,subsection); });
  }

  async function pointsAccount(id) {
    const dialog = openSheet('Mitgliedskonto', '<p role="status">Wird geladen …</p>');
    try {
      const data = await request('admin/customers/'+id+'/');
      if (!dialog.open) return;
      dialog.querySelector('[data-sheet-body]').innerHTML = `<h3>${esc(data.customer.name)}</h3>
        <p>${Number(data.customer.coins)} Punkte · ${esc(data.customer.member_number)}</p>
        <button class="mw-secondary" type="button" data-adjust-points>Punkte korrigieren</button>
        <h3>Pakete</h3>${data.packages.map(item=>`<article class="mw-static-row"><strong>${esc(item.name)}</strong>
          <small>${Number(item.remaining_sessions)} Einheiten</small></article>`).join('')||empty('Keine Pakete.')}`;
      dialog.querySelector('[data-adjust-points]').onclick = () => {
        const adjustment = openSheet('Punktestand korrigieren', formWrap(
          '<p>Positive Werte schreiben Punkte gut, negative ziehen Punkte ab.</p>' +
          input('Differenz','coin_delta','type="number" min="-100000" max="100000" required'),
        ));
        bindCommand(adjustment, 'staff/points/'+id+'/', form => ({coin_delta:Number(form.elements.coin_delta.value)}),
          () => void pointsAccount(id), request);
      };
    } catch (failure) {
      if (dialog.open && !showError(failure)) dialog.querySelector('[data-sheet-body]').textContent = 'Das Mitgliedskonto konnte nicht geladen werden.';
    }
  }

  surface.addEventListener('click', event => {
    const button = event.target.closest('[data-mw-tab],[data-mw-action]');
    if (!button) return;
    if (button.dataset.mwTab) { void navigate(button.dataset.mwTab); return; }
    const id = Number(button.dataset.id);
    switch (button.dataset.mwAction) {
      case 'retry':
        button.disabled = true;
        button.textContent = 'Wird erneut verbunden …';
        void navigate(view,subsection);
        break;
      case 'logout': logout(); break;
      case 'desktop': {
        const url = 'https://book.a-esthetic.de/verwaltung/login/';
        const browser = window.Capacitor?.Plugins?.Browser;
        if (browser) void browser.open({url}).catch(() => toast('Der Browser konnte nicht geöffnet werden.'));
        else window.open(url,'_blank','noopener,noreferrer');
        break;
      }
      case 'settings': void navigate('settings',button.dataset.id); break;
      case 'appointment': if (currentItems.has(id)) showCalendarItem({...currentItems.get(id),type:'appointment'}); break;
      case 'patient': void openPatient(id); break;
      case 'hours': void hoursForm(today(),id).catch(failure => { if (!showError(failure)) toast('Arbeitszeiten konnten nicht geladen werden.'); }); break;
      case 'service': serviceForm(id); break;
      case 'points-account': void pointsAccount(id); break;
    }
  }, {signal:lifetime.signal});

  void navigate(view);
  return {
    openPatient,
    openCalendar: () => void navigate('calendar'),
    back() {
      if (sheet?.open) { closeSheet(); return true; }
      if (subsection) { void navigate('settings'); return true; }
      if (view !== (doctor?'calendar':'overview')) { void navigate(doctor?'calendar':'overview'); return true; }
      return false;
    },
    destroy() {
      lifetime.abort();
      requests.abort();
      calendar?.destroy();
      closeSheet();
      clearTimeout(toastTimer);
      currentItems.clear();
      surface.remove();
    },
  };
}
