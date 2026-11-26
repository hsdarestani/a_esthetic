const clinicZone = 'Europe/Berlin';
const isoFormat = new Intl.DateTimeFormat('sv-SE', {timeZone: clinicZone, year:'numeric', month:'2-digit', day:'2-digit'});
const clockFormat = new Intl.DateTimeFormat('de-DE', {timeZone: clinicZone, hour:'2-digit', minute:'2-digit'});
export const today = () => isoFormat.format(new Date());
const utcDate = value => new Date(value + 'T12:00:00Z');
export function shiftDay(date, delta) {
  const value = utcDate(date);
  value.setUTCDate(value.getUTCDate() + delta);
  return value.toISOString().slice(0, 10);
}
export const startWeek = date => shiftDay(date, -((utcDate(date).getUTCDay() + 6) % 7));
export const dateLabel = (date, options) => utcDate(date).toLocaleDateString('de-DE', {...options, timeZone: 'UTC'});
export const minutes = value => {
  const [hours, min] = value.split(':').map(Number);
  return hours * 60 + min;
};
const listDays = (start, length) => Array.from({length}, (_, index) => shiftDay(start, index));

function dailySpan(item, day) {
  const start = new Date(item.start_at);
  const end = new Date(item.end_at);
  const startDate = isoFormat.format(start);
  const endDate = isoFormat.format(end);
  if (day < startDate || day > endDate) return null;
  const lower = day === startDate ? minutes(clockFormat.format(start)) : 0;
  const upper = day === endDate ? minutes(clockFormat.format(end)) : 1440;
  return upper > lower ? {...item, lower, upper} : null;
}

export function packEvents(items) {
  const ordered = [...items].sort((a, b) => a.lower - b.lower || b.upper - a.upper);
  const groups = [];
  let group = [];
  let laneEnds = [];
  const flush = () => {
    groups.push(...group.map(entry => ({...entry, lanes: laneEnds.length})));
    group = [];
    laneEnds = [];
  };
  for (const item of ordered) {
    if (group.length && laneEnds.every(end => end <= item.lower)) flush();
    const lane = laneEnds.findIndex(end => end <= item.lower);
    const index = lane === -1 ? laneEnds.length : lane;
    laneEnds[index] = item.upper;
    group.push({...item, lane: index});
  }
  flush();
  return groups;
}

export function createCalendar(container, {api, catalog, escape, select, add, error}) {
  const state = {date: today(), view: 'day', filter: 'all', panelWidth: 0, generation: 0};
  const cache = new Map();
  const inflight = new Map();
  const disposal = new AbortController();
  const listen = {signal: disposal.signal};
  let fetchScope = new AbortController();
  const PX = 1.24;
  const firstHour = 0;
  const lastHour = 24;
  let pointer;
  let suppressClickUntil = 0;

  container.innerHTML = `
    <div class="mw-calendar">
      <div class="mw-cal-top">
        <div class="mw-cal-month"><div><h1>Kalender</h1><p data-cal-month></p></div>
          <button type="button" data-cal-today>Heute</button>
          <label class="mw-date-button" aria-label="Datum auswählen">
            <span aria-hidden="true">▦</span><input type="date" aria-label="Datum auswählen" data-cal-date>
          </label>
        </div>
        <div class="mw-week-picker">
          <button type="button" data-cal-shift="-7" aria-label="Vorherige Woche">‹</button>
          <div class="mw-week-days" data-cal-week></div>
          <button type="button" data-cal-shift="7" aria-label="Nächste Woche">›</button>
        </div>
        <div class="mw-cal-filters">
          <select data-cal-mode aria-label="Kalenderansicht">
            <option value="day">Tag</option><option value="week">Woche</option>
            <option value="provider">Behandler</option><option value="service">Behandlung</option>
          </select>
          <select data-cal-filter aria-label="Kalender filtern"></select>
          <button type="button" data-cal-shift="-1" aria-label="Vorheriger Tag">‹</button>
          <button type="button" data-cal-shift="1" aria-label="Nächster Tag">›</button>
        </div>
      </div>
      <div class="mw-cal-state" role="status" data-cal-status hidden></div>
      <div class="mw-cal-grid-header"><span></span><div data-cal-columns></div></div>
      <div class="mw-cal-scroll" data-cal-scroll tabindex="0" aria-label="Zeitraster">
        <div class="mw-cal-ruler" aria-hidden="true">${Array.from({length: lastHour-firstHour}, (_, index) =>
          `<span style="top:${index * PX * 60}px">${String(firstHour + index).padStart(2,'0')}:00</span>`).join('')}</div>
        <div class="mw-cal-track" data-cal-track></div>
      </div>
      <button class="mw-fab" type="button" data-cal-add aria-label="Kalendereintrag hinzufügen">+</button>
    </div>`;
  const get = name => container.querySelector(`[data-cal-${name}]`);
  const scroll = get('scroll');
  const track = get('track');
  const status = get('status');
  scroll.scrollTop = 9 * 60 * PX;
  const resize = new ResizeObserver(() => {
    const width = scroll.clientWidth;
    const previous = state.panelWidth >= 700;
    state.panelWidth = width;
    if (previous !== (width >= 700) && state.view === 'week') void refresh();
  });
  resize.observe(scroll);

  async function load(week) {
    const found = cache.get(week);
    if (found && performance.now() - found.at < 45000) return found.value;
    if (inflight.has(week)) return inflight.get(week);
    const batch = api(`calendar/?start=${week}&days=7`, {signal: fetchScope.signal}).then(data => {
      cache.set(week, {at:performance.now(), value:data});
      if (cache.size > 8) cache.delete(cache.keys().next().value);
      return data;
    }).finally(() => {
      if (inflight.get(week) === batch) inflight.delete(week);
    });
    inflight.set(week, batch);
    return batch;
  }

  function columns() {
    const providers = catalog.providers;
    const services = catalog.services.filter(service => service.active);
    if (state.view === 'week') {
      const days = state.panelWidth >= 700 ? listDays(startWeek(state.date), 7) : listDays(state.date, 3);
      return days.map(date => ({date, id: state.filter, title: dateLabel(date,{weekday:'short', day:'numeric', month:'numeric'})}));
    }
    if (state.view === 'provider') {
      const shown = providers.filter(row => state.filter === 'all' || String(row.id) === state.filter);
      return shown.map(row => ({date:state.date, id:String(row.id), title:row.name}));
    }
    if (state.view === 'service') {
      const shown = services.filter(row => state.filter === 'all' || String(row.id) === state.filter);
      return shown.map(row => ({date:state.date, id:String(row.id), title:row.name}));
    }
    const name = catalog.providers.find(row => String(row.id) === state.filter)?.name;
    return [{date:state.date, id:state.filter, title:name || dateLabel(state.date,{weekday:'long', day:'numeric', month:'long'})}];
  }

  function renderHeader() {
    get('month').textContent = dateLabel(state.date, {month:'long', year:'numeric'});
    get('date').value = state.date;
    get('week').innerHTML = listDays(startWeek(state.date), 7).map(date =>
      `<button type="button" data-cal-day="${date}" aria-pressed="${date === state.date}" aria-label="${dateLabel(date,{dateStyle:'full'})}">
        <span>${dateLabel(date,{weekday:'short'}).replace('.', '')}</span><b>${Number(date.slice(-2))}</b></button>`).join('');
    const services = state.view === 'service';
    const filter = get('filter');
    filter.setAttribute('aria-label', services ? 'Behandlung filtern' : 'Behandler filtern');
    if (filter.dataset.mode !== state.view) {
      filter.dataset.mode = state.view;
      filter.innerHTML = `<option value="all">${services ? 'Alle Behandlungen' : 'Alle Behandler'}</option>` +
        (services ? catalog.services.filter(service => service.active) : catalog.providers).map(row =>
          `<option value="${row.id}">${escape(row.name)}</option>`).join('');
    }
    filter.value = state.filter;
  }

  function renderTimeline(layout, result) {
    const dataByWeek = result || new Map();
    const wide = ['provider','service'].includes(state.view) && layout.length > 2;
    const style = `--mw-cols:${Math.max(1,layout.length)};--mw-col-min:${wide?120:0}px;--mw-hour:${PX*60}px;--mw-timeline:${(lastHour-firstHour)*60*PX}px`;
    const header = get('columns');
    header.style.cssText = style;
    track.style.cssText = style;
    header.innerHTML = layout.map(col => `<span>${escape(col.title)}</span>`).join('');
    track.innerHTML = layout.map(col => {
      const data = dataByWeek.get(startWeek(col.date));
      const serviceMode = state.view === 'service';
      const asService = serviceMode ? catalog.providers.filter(p => p.services.includes(Number(col.id))).map(p => p.id) : [];
      const matchesStaff = item => serviceMode ? asService.includes(item.staff_id) : col.id === 'all' || String(item.staff_id) === col.id;
      const matchingBlocks = item => matchesStaff(item) && (item.scope !== 'service' || !serviceMode || item.service_id === col.id);
      const appointments = (data?.appointments || []).filter(item => serviceMode
        ? String(item.service_id) === col.id : matchesStaff(item));
      const blocks = (data?.blocks || []).filter(matchingBlocks);
      const schedule = (data?.availability || []).filter(item => item.date === col.date && matchesStaff(item));
      const periods = schedule.flatMap(row => row.ranges).map(range =>
        `<div class="mw-working" style="top:${minutes(range.start)*PX}px;height:${(minutes(range.end)-minutes(range.start))*PX}px"></div>`).join('');
      const events = packEvents([
        ...appointments.map(item => dailySpan({...item, type:'appointment'},col.date)),
        ...blocks.map(item => dailySpan({...item, type:item.kind},col.date)),
      ].filter(Boolean));
      return `<div class="mw-cal-column">${periods}${events.map(item => {
        const title = item.type === 'appointment' ? item.customer_name : item.text;
        const label = item.type === 'appointment' ? item.service_name : item.kind === 'note' ? 'Notiz' : 'Gesperrt';
        const geometry = `top:${item.lower*PX}px;height:${Math.max(19,(item.upper-item.lower)*PX)}px;left:${100*item.lane/item.lanes}%;width:${100/item.lanes}%`;
        return `<button type="button" class="mw-cal-event mw-cal-${item.type}" data-cal-item="${item.type}:${item.id}" style="${geometry}"
          aria-label="${escape(`${item.start} · ${title} · ${label}`)}"><small>${escape(item.start)} · ${escape(label)}</small><strong>${escape(title)}</strong></button>`;
      }).join('')}</div>`;
    }).join('');
    track.dataset.items = '';
    container._calendarItems = new Map([...dataByWeek.values()].flatMap(data => [
      ...data.appointments.map(item => [`appointment:${item.id}`, {...item, type:'appointment'}]),
      ...data.blocks.map(item => [`${item.kind}:${item.id}`, {...item, type:item.kind}]),
    ]));
    header.scrollLeft = scroll.scrollLeft;
  }

  const showStatus = (message, retry = false) => {
    status.replaceChildren(document.createTextNode(message));
    status.hidden = !message;
    if (retry) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Erneut versuchen';
      button.onclick = () => void refresh();
      status.append(button);
    }
  };

  async function refresh() {
    const generation = ++state.generation;
    const started = performance.now();
    renderHeader();
    const layout = columns();
    const weeks = [...new Set(layout.map(col => startWeek(col.date)))];
    const saved = new Map(weeks.map(week => [week, cache.get(week)?.value]).filter(([,value]) => value));
    renderTimeline(layout, saved);
    showStatus(saved.size === weeks.length ? '' : 'Kalender wird geladen …');
    if (!weeks.length) {
      showStatus('Für diese Ansicht sind keine Einträge verfügbar.');
      return;
    }
    try {
      const rows = await Promise.all(weeks.map(load));
      if (generation !== state.generation || disposal.signal.aborted) return;
      if (saved.size !== weeks.length || rows.some((value,index) => saved.get(weeks[index]) !== value)) {
        renderTimeline(layout, new Map(weeks.map((week,index) => [week,rows[index]])));
      }
      showStatus('');
      container.dispatchEvent(new CustomEvent('aplus:calendar-ready', {bubbles:true, detail:{
        date:state.date, view:state.view, milliseconds:performance.now()-started, cached:saved.size === weeks.length,
      }}));
      if (navigator.onLine) {
        const first = weeks[0];
        const last = weeks.at(-1);
        void load(shiftDay(first,-7)).catch(() => {});
        void load(shiftDay(last,7)).catch(() => {});
      }
    } catch (failure) {
      if (generation !== state.generation || disposal.signal.aborted) return;
      if (failure.status === 401 || failure.status === 403) error(failure);
      showStatus(saved.size ? 'Verbindung unterbrochen. Zwischengespeicherte Ansicht.' : 'Kalender konnte nicht geladen werden.', true);
    }
  }

  function activate(date) {
    if (date === state.date) return;
    state.date = date;
    void refresh();
  }

  container.addEventListener('click', event => {
    if (performance.now() < suppressClickUntil && event.target.closest('[data-cal-item]')) return;
    const button = event.target.closest('button');
    if (!button) return;
    if (button.hasAttribute('data-cal-today')) activate(today());
    if (button.dataset.calDay) activate(button.dataset.calDay);
    if (button.dataset.calShift) activate(shiftDay(state.date, Number(button.dataset.calShift)));
    if (button.hasAttribute('data-cal-add')) add(state.date, state.view === 'service' ? 'all' : state.filter);
    if (button.dataset.calItem) {
      const item = container._calendarItems?.get(button.dataset.calItem);
      if (item) select(item);
    }
  }, listen);
  get('mode').onchange = event => {
    state.view = event.target.value;
    state.filter = 'all';
    scroll.scrollLeft = 0;
    void refresh();
  };
  get('filter').onchange = event => { state.filter = event.target.value; scroll.scrollLeft = 0; void refresh(); };
  get('date').onchange = event => { if (event.target.value) activate(event.target.value); };
  scroll.addEventListener('scroll', () => { get('columns').scrollLeft = scroll.scrollLeft; }, {passive:true, ...listen});
  scroll.addEventListener('pointerdown', event => {
    if (!['day','week'].includes(state.view) || !event.isPrimary || event.button !== 0) return;
    pointer = {id:event.pointerId, x:event.clientX, y:event.clientY, dx:0, locked:false};
  }, listen);
  scroll.addEventListener('pointermove', event => {
    if (pointer?.id !== event.pointerId) return;
    const dx = event.clientX - pointer.x;
    const dy = event.clientY - pointer.y;
    if (!pointer.locked && Math.abs(dy) > 12 && Math.abs(dy) >= Math.abs(dx)) { pointer = null; return; }
    if (!pointer.locked && Math.abs(dx) > 12 && Math.abs(dx) > 1.25 * Math.abs(dy)) {
      pointer.locked = true;
      scroll.setPointerCapture(event.pointerId);
    }
    if (!pointer.locked) return;
    pointer.dx = dx;
    track.style.translate = `${Math.max(-110, Math.min(110,dx*.48))}px 0`;
  }, listen);
  function release(event) {
    if (pointer?.id !== event.pointerId) return;
    const {dx, locked} = pointer;
    pointer = null;
    track.style.translate = '';
    if (locked) suppressClickUntil = performance.now() + 180;
    if (event.type === 'pointerup' && locked && Math.abs(dx) >= 40) activate(shiftDay(state.date, dx < 0 ? 1 : -1));
  }
  scroll.addEventListener('pointerup', release, listen);
  scroll.addEventListener('pointercancel', release, listen);
  window.addEventListener('online', refresh, listen);
  void refresh();

  return {
    invalidate() {
      fetchScope.abort();
      fetchScope = new AbortController();
      inflight.clear();
      cache.clear();
      void refresh();
    },
    destroy() {
      disposal.abort();
      fetchScope.abort();
      resize.disconnect();
      cache.clear();
      delete container._calendarItems;
    },
  };
}
