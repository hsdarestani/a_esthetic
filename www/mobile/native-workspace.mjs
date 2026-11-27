// One screen/state controller; all controls are rendered by UIKit/SwiftUI or
// Android Views. No staff HTML, browser navigation or web forms are mounted.
import { today, startWeek, shiftDay } from './calendar.mjs';
import { buildNativeCalendarTimeline } from './native-calendar-layout.mjs';

// Keep form input semantics identical in SwiftUI and Android native controls.
const inputKind = id => {
  if (/^(note|notes|description|goae_description|goae_justification|date_correction_reason|text)$/.test(id)) return 'multiline';
  if (/^(quantity|treatment_quantity|duration_minutes|buffer_minutes|goae_points|next_sequence)$/.test(id)) return 'integer';
  if (/^(goae_factor|goae_base_eur|desired_total_eur)$/.test(id)) return 'decimal';
  if (id === 'email') return 'email';
  if (id === 'phone') return 'phone';
  return 'text';
};
const dateFields = new Set(['date','from','to','service_date','date_of_birth']);
export const germanDate = value => String(value ?? '').replace(/\b(\d{4})-(\d{2})-(\d{2})(?=\b|T)/g,'$3.$2.$1');
// Display copy only. Keep canonical values, email addresses, phone numbers,
// file names, links, and patient identifiers untouched.
export const displayCopy = value => String(value??'').replace(/\s+[\-–—]\s+/g,' · ').replace(/[\u00ad\-‐‑–—]/g,' ').replace(/ {2,}/g,' ').trim();
export function canonicalDate(value) {
  const raw=String(value??'').trim();
  if(!raw)return '';
  const match=raw.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  const iso=match?`${match[3]}-${match[2].padStart(2,'0')}-${match[1].padStart(2,'0')}`:raw;
  if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))return null;
  const parsed=new Date(iso+'T12:00:00Z');
  return !Number.isNaN(parsed.getTime())&&parsed.toISOString().slice(0,10)===iso?iso:null;
}
const value = (id, label, initial = '', options) => ({
  id,label:displayCopy(dateFields.has(id)&&!options?label.replace(/\s*\((?:JJJJ[ -]MM[ -]TT|YYYY[ -]MM[ -]DD)\)/,'')+' · TT.MM.JJJJ':label),value:dateFields.has(id)&&!options?germanDate(initial):String(initial ?? ''),kind:options?'select':inputKind(id),
  ...(options ? {options} : {}),
});
const displayData = value => germanDate(value).replace(/\s+[\-–—]\s+/g,' · ').replace(/^\s*[–—-]\s*$/,'');
const row = (id,label,detail='') => ({id,label:displayData(label),detail:displayData(detail)});
const option = (value,label) => ({value:String(value),label:germanDate(label)});
const dateLabel = (date, locale, options) => new Date(date+'T12:00:00Z').toLocaleDateString('de-DE',{...options,timeZone:'UTC'});
const optionFor = (list) => list.map(x=>option(x.id,x.name));
const serviceOptions = list => list.map(x=>option(x.id,displayCopy(x.name)));
const sourceOfBlock = block => block?.source_managed || /\u2063[\u200b\u200c]+\u2063/.test(block?.text||'')
  ? 'SimplyBook' : 'Book';
const isSyncedProvider = p => Boolean(p?.source_managed || String(p?.name||'').startsWith('A+ Esthetic (SimplyBook #'));
const isSyncedService = s => Boolean(s?.source_managed || String(s?.slug||'').startsWith('simplybook-event-'));
const uuid = () => globalThis.crypto.randomUUID();

export function internationalPhone(input) {
  const raw=String(input??'').trim();
  if(!/^\+?\(?[0-9][0-9 ().\s/–-]*$/.test(raw))return '';
  // An explicit trunk prefix in parentheses is for domestic use. Italy,
  // San Marino, and Vatican numbers can have a significant leading zero.
  const trunk=raw.match(/^(?:\+|00)\s*(\d{1,3})[ .–-]*\(0\)/);
  const formatted=trunk&&!['39','378','379'].includes(trunk[1])?raw.replace('(0)',''):raw;
  let phone=formatted.replace(/[ ().\s/–-]/g,'');
  if(phone.startsWith('00'))phone='+'+phone.slice(2);
  else if(phone.startsWith('0'))phone='+49'+phone.slice(1);
  if(phone.startsWith('+490'))phone='+49'+phone.slice(4);
  return /^\+[1-9]\d{6,14}$/.test(phone)&&!phone.startsWith('+490')?phone:'';
}
const validContactEmail = input => typeof input==='string' && input.length<=254 &&
  /^[^\s@<>,;?&#%]+@[^\s@<>,;?&#%]+\.[^\s@<>,;?&#%]+$/.test(input) &&
  !/@invalid\.local$/i.test(input);
const contactEmail = input => /@invalid\.local$/i.test(input||'')?'':String(input??'').trim();


export async function mountNativeWorkspace({token, identity, origin, logout, initialPatient, initialCalendar, navigation, signal}) {
  const plugin = globalThis.APlusNativeStaff || globalThis.Capacitor?.Plugins?.NativeStaff;
  if (!plugin) throw new Error('Native staff renderer unavailable');
  const admin = identity.role === 'admin';
  let language = localStorage.getItem('aplus_language') === 'en' ? 'en' : 'de';
  const tr = (de,en) => displayCopy(language === 'en' ? en : de);
  let locale = language === 'en' ? 'en-GB' : 'de-DE';
  const history = [];
  const requests = new AbortController();
  let transition, location, routeTarget, calendarScreen, queuedRoute, closing;
  const appointmentsById = new Map();
  const rememberAppointments = items => { for(const a of items||[]) appointmentsById.set(a.id,a); };
  let date = today(), search = '', calendarMode='day', providerFilter=admin?null:'all', serviceFilter='all', active = true, busy = true, listener, patient, catalog, appointment;
  let activeTab = 'home';
  let patientPage=1, recordPage=1, patientSection='overview', intakeSearch='', intakeStatus='', intakePage=1, intakeFrom='', intakeTo='', submission, canonicalForms=true;
  let current = {title:'A+ Esthetic',busy:true,tabs:[]};
  const blockById = new Map();
  const calendarCache = new Map();
  const calendarInFlight = new Map();
  let prefetchBusy = false, calendarEpoch = 0;
  function invalidateCalendar() {
    calendarEpoch++;
    calendarCache.clear();
    calendarInFlight.clear();
  }
  function getCalendarWeek(day) {
    const key=startWeek(day);
    const cached=calendarCache.get(key);
    if(cached && Date.now()-cached.at<45000)return Promise.resolve(cached.data);
    if(calendarInFlight.has(key))return calendarInFlight.get(key);
    const epoch=calendarEpoch;
    const pending=book('calendar/?start='+key+'&days=7').then(data=>{
      if(epoch!==calendarEpoch)return data;
      calendarCache.set(key,{at:Date.now(),data});
      if(calendarCache.size>6)calendarCache.delete(calendarCache.keys().next().value);
      return data;
    }).finally(()=>{if(calendarInFlight.get(key)===pending)calendarInFlight.delete(key);});
    calendarInFlight.set(key,pending);
    return pending;
  }
  function prefetchCalendarNeighbors(day) {
    if(prefetchBusy)return;
    prefetchBusy=true;
    // Sequential and deduplicated: at most one background calendar relay
    // runs beside the active request. Avoid app->Book->app worker starvation.
    void (async()=>{
      try {
        await getCalendarWeek(shiftDay(startWeek(day),-7));
        await getCalendarWeek(shiftDay(startWeek(day),7));
      } catch(_) { /* Prefetch is optional; visible range reports its own errors. */ }
      finally { prefetchBusy=false; }
    })();
  }
  const tabs = () => [
    {...row('home',tr('Übersicht','Home')), icon:'square.grid.2x2'},
    {...row('calendar',tr('Kalender','Calendar')),icon:'calendar'},
    {...row('patients',tr('Patienten','Patients')),icon:'person.2'},
    {...row('settings',tr('Einstellungen','Settings')),icon:'gearshape'},
  ];
  async function request(path, data, prefix='/api/mobile/staff/') {
    requests.signal.throwIfAborted();
    const response = await fetch(origin+prefix+path,{
      method:data ? 'POST':'GET', headers:{Authorization:'Bearer '+token,Accept:'application/json','Content-Type':'application/json'},
      cache:'no-store', signal:requests.signal, ...(data?{body:JSON.stringify(data)}:{}),
    });
    if(!response.ok){const err=new Error(tr('Vorgang konnte nicht abgeschlossen werden.','Unable to complete request.')+' (HTTP '+response.status+')');err.status=response.status;throw err;}
    return response.json();
  }
  const pendingCommands = new Map();
  async function command(path, payload, keyName='key') {
    const fingerprint=JSON.stringify([path,payload]);
    const key=pendingCommands.get(fingerprint)||uuid();
    pendingCommands.set(fingerprint,key);
    const reply=await request(path,{...payload,[keyName]:key});
    pendingCommands.delete(fingerprint);
    return reply;
  }
  const book = (path,data) => request('book/'+path,data);
  const office = (path,data) => request('office/'+path,data);
  const localizedStatus = status => language==='de'?({confirmed:'Bestätigt',pending:'Ausstehend',cancelled:'Abgesagt',canceled:'Abgesagt',completed:'Abgeschlossen',no_show:'Nicht erschienen',linked:'Zugeordnet',review:'Zu prüfen',draft:'Entwurf',issued:'Ausgestellt',paid:'Bezahlt',active:'Aktiv',expired:'Abgelaufen',note:'Notiz',block:'Sperrzeit'}[status]||status):status;
  const view = (title, content={}) => ({title:germanDate(title),language,
    ...(activeTab==='calendar'&&!content.timeline?{presentation:'calendar-sheet'}:{}),
    tabs:tabs().map(tab=>({...tab,selected:tab.id===activeTab})), ...content,
    ...(content.subtitle?{subtitle:displayData(content.subtitle)}:{}),
    ...Object.fromEntries(['rows','secondaryRows'].filter(key=>content[key]).map(key=>[key,content[key].map(item=>({...item,...(item.badge?{badge:localizedStatus(item.badge)}:{})}))]))});
  const datePattern=/^\d{4}-\d{2}-\d{2}$/;
  const subviews=/^(appointment:\d+|record-detail:[\w-]+|block(?:-info)?:\d+|service:\d+|patient-(?:link-account|adjust-points|invoices|edit-contact)|note|record-edit|new-patient-appointment|new-appointment|slot:\d{4}-\d{2}-\d{2}:\d{2}:\d{2}(?::\w+)?|edit-appointment|new-block|availability|language|services|identity-review)$/;
  const updates=/^(date:|cal-(?:today|mode:|provider:|service:)|(?:day|week)-(?:next|prev)|search$|patient-section:|(?:patient|record)-page-|apply-calendar-filter$|calendar-client-search$|load-availability$|patient-link-search$)/;
  function routeState(action){
    return {action,activeTab,date,search,calendarMode,providerFilter,serviceFilter,patientPage,recordPage,patientSection,
      patientId:activeTab==='patients'?patient?.patient.id:undefined,
      appointmentId:appointment?.id,blockId:currentBlock?.id,recordId:selectedRecord?.id};
  }
  function applyRoute(saved){
    ({activeTab,date,search,calendarMode,providerFilter,serviceFilter,patientPage,recordPage,patientSection}=saved);
  }
  function snapshot(event={}){
    const values=event.values||{};
    const screen={...current,scroll:event.scroll??current.scroll,scrollX:event.scrollX??current.scrollX,
      ...(current.fields?{fields:current.fields.map(f=>({...f,value:values[f.id]??f.value}))}:{})};
    return {screen,location,models:{patient,appointment,currentBlock,currentService,selectedRecord,currentPatientAccount},calendarScreen};
  }
  const checkpoint=()=>{
    if(active && location)return navigation?.save('staff',{...location,screenKey:current.screenKey,
      scroll:current.scroll,scrollX:current.scrollX,values:Object.fromEntries((current.fields||[]).map(f=>[f.id,f.value])),
      history:history.map(({location,screen})=>screen?{...location,scroll:screen.scroll,scrollX:screen.scrollX,
        values:Object.fromEntries((screen.fields||[]).map(f=>[f.id,f.value]))}:location)});
  };
  function destination(screen,action){
    if(screen.timeline)return 'calendar';
    if(screen.segments && patient)return 'patient:'+patient.patient.id;
    const tab=screen.tabs?.find(tab=>tab.selected)?.id;
    if(['home','patients','settings'].includes(action) && action===tab)return action;
    if(subviews.test(action))return action;
    if(updates.test(action))return location?.action||tab;
    return action;
  }
  async function render(screen,{replace=false,keepKey=false}={}) {
    if(!active)return;
    const previous=transition?.from;
    const action=routeTarget||destination(screen,transition?.action||location?.action||activeTab);
    const next={...screen,screenKey:keepKey?current.screenKey:uuid()};
    await plugin.render({screen:next});
    if(!active)return;
    if(!replace && previous?.location && previous.location.action!==action){
      if(history.at(-1)?.location.action===action)history.pop();
      else if(!updates.test(transition.action)){
        history.push(previous);
        if(history.length>20)history.shift();
      }
    }
    current=next;
    if(next.timeline)calendarScreen=next;
    location=routeState(action);
  }
  async function screen(name) {
    const previous=routeTarget;
    routeTarget=name;
    try{return await renderRoute(name);}
    finally{routeTarget=previous;}
  }
  async function renderRoute(name) {
    if(['home','calendar','patients','settings'].includes(name))activeTab=name;
    if(name==='home'){
      const r=await book('overview/');
      rememberAppointments(r.upcoming);
      const upcoming=r.upcoming||[];
      return render(view(tr('Willkommen','Welcome'),{hero:tr('Praxisübersicht','Practice overview'),subtitle:identity.name+' · '+dateLabel(today(),locale,{weekday:'long',day:'numeric',month:'long'}),
        metrics:[row('calendar',tr('Termine heute','Appointments today'),String(r.today)),
          row('calendar',r.upcoming_count==null?tr('Nächste Termine (Auszug)','Next appointments (shown)'):tr('Bevorstehend','Upcoming'),String(r.upcoming_count??upcoming.length)),
          ...(r.patient_count==null?[]:[row('patients',tr('Kontaktprofile','Contact profiles'),String(r.patient_count))]),
          ...(r.provider_count==null?[]:[row('calendar',tr('Behandler','Providers'),String(r.provider_count))])],
        shortcuts:[row('calendar',tr('Kalender','Calendar')),row('patients',tr('Patientenakten','Patient records'))],
        sectionTitle:tr('NÄCHSTE TERMINE','NEXT APPOINTMENTS'),
        rows:upcoming.map(a=>({...row('appointment:'+a.id,a.customer_name,[a.date,a.start,a.service_name&&displayCopy(a.service_name),a.staff_name].filter(Boolean).join(' · ')),badge:a.status||''})),
        secondaryTitle:tr('HEUTIGER PRAXISPLAN','TODAY’S PRACTICE SCHEDULE'),
        secondaryRows:(r.provider_today||[]).map(p=>row('cal-provider:'+p.id,p.name,String(p.count)+' '+tr('Termine heute','appointments today'))),
        empty:tr('Keine kommenden Termine.','No upcoming appointments.')} ));
    }
    if(name==='calendar'){
      const weekStart=startWeek(date);
      const data=await getCalendarWeek(date);
      const days=Array.from({length:7},(_,i)=>{
        const d=shiftDay(weekStart,i);
        return {id:'date:'+d,label:dateLabel(d,locale,{weekday:'short',day:'numeric'}),selected:d===date};
      });
      catalog = catalog || await book('catalog/');
      // Resolve the default from the authorized provider catalog, never from a
      // hard-coded database ID. Explicit All / provider choices stay intact.
      if(providerFilter==null || (providerFilter!=='all'&&!catalog.providers.some(p=>String(p.id)===providerFilter))){
        const ariane=admin?catalog.providers.filter(p=>/(^|[^\p{L}])ariane([^\p{L}]|$)/iu.test(String(p.name||''))&&!isSyncedProvider(p)):[];
        providerFilter=ariane.length===1?String(ariane[0].id):'all';
      }
      rememberAppointments(data.appointments);
      for(const item of data.blocks||[])blockById.set(item.id,item);
      const match = a => (providerFilter==='all'||String(a.staff_id)===providerFilter) &&
        (serviceFilter==='all'||String(a.service_id)===serviceFilter);
      const found=(data.appointments||[]).filter(a=>(calendarMode==='week'||a.date===date)&&match(a));
      const blocked=(data.blocks||[]).filter(a=>(calendarMode==='week'||a.date===date)&&(providerFilter==='all'||String(a.staff_id)===providerFilter));
      found.sort((a,b)=>(a.date+a.start).localeCompare(b.date+b.start));
      const timeline=buildNativeCalendarTimeline({date,mode:calendarMode,
        providers:catalog.providers,services:catalog.services,provider:providerFilter,
        service:serviceFilter,calendar:data});
      timeline.language=language;
      // Nonblocking adjacent-week prefetch; never hold the SwiftUI timeline for it.
      prefetchCalendarNeighbors(weekStart);
      return render(view(tr('Kalender','Calendar'),{subtitle:dateLabel(date,locale,{weekday:'long',day:'numeric',month:'long'}),
        timeline,
        week:days,message:date===shiftDay(weekStart,6)?tr('Sonntag · Online-Buchung geschlossen','Sunday · Online booking closed'):'',
        fields:[
          value('calendar_mode',tr('Ansicht','View'),calendarMode,[option('day',tr('Tag','Day')),option('week',tr('Woche','Week')),option('provider',tr('Behandler','Provider')),option('service',tr('Behandlung','Service'))]),
          value('provider_filter',tr('Behandler','Provider'),providerFilter,[option('all',tr('Alle','All')),...optionFor(catalog.providers)]),
          value('service_filter',tr('Behandlung','Service'),serviceFilter,[option('all',tr('Alle','All')),...serviceOptions(catalog.services.filter(x=>x.active))]),
        ],
        rows:[...found.map(a=>row('appointment:'+a.id,(calendarMode==='week'?a.date+' · ':'')+a.start+' · '+a.customer_name,displayCopy(a.service_name)+' · '+a.staff_name)),
          ...blocked.map(b=>row((b.editable?'block:':'block-info:')+b.id,b.start+' · '+(b.text||tr('Gesperrt','Blocked')).split('\u2063')[0],b.end||''))],
        actions:[row('apply-calendar-filter',tr('Ansicht aktualisieren','Apply filters')),
          row('new-appointment',tr('Termin hinzufügen','Add appointment')),row('new-block',tr('Sperrzeit / Notiz','Block / note')),
          row('availability',tr('Arbeitszeit','Working hours'))]}));
    }
    if(name==='patients'){
      const r=await book('patients/?q='+encodeURIComponent(search)+'&page='+patientPage);
      return render(view(tr('Patienten','Patients'),{subtitle:tr('Patientenverwaltung und digitale Akten','Patient management and digital records'),
        fields:[value('query',tr('Name, E-Mail oder Telefon','Name, email or phone'),search)],
        shortcuts:[row('search',tr('Suchen','Search')),...(admin?[row('identity-review',tr('Identität prüfen','Review identities'))]:[])],
        sectionTitle:tr('KONTAKTPROFILE','CONTACT PROFILES')+' · '+tr('Seite','Page')+' '+patientPage,
        empty:tr('Keine passenden Patienten gefunden.','No matching patients found.'),
        actions:[...(r.has_more?[row('patient-page-next',tr('Nächste Seite','Next page'))]:[]),...(patientPage>1?[row('patient-page-prev',tr('Vorherige Seite','Previous page'))]:[])],
        rows:r.items.map(x=>row('patient:'+x.id,x.name,[x.email,x.phone].filter(Boolean).join(' · ')))}));
    }
    if(name==='settings'){
      return render(view(tr('Einstellungen','Settings'),{rows:[
        row('availability',tr('Arbeitszeit und Verfügbarkeit','Hours and availability')),
        ...(admin?[row('services',tr('Behandlungskatalog','Treatment catalog')),row('booking-notifications',tr('Terminbenachrichtigungen','Booking notifications'))]:[]),
        row('language',tr('Sprache','Language')),
      ],actions:[row('logout',tr('Abmelden','Sign out'))]}));
    }
    if(name==='booking-notifications'&&admin){
      let permission='unknown';
      try {permission=(await globalThis.Capacitor?.Plugins?.PushNotifications?.checkPermissions?.())?.receive||'unknown';} catch (_) {}
      const permissionLabel=permission==='granted'?tr('Erlaubt','Allowed'):permission==='denied'?tr('In den Systemeinstellungen deaktiviert','Disabled in system settings'):tr('Nicht bestätigt','Not confirmed');
      return render(view(tr('Terminbenachrichtigungen','Booking notifications'),{
        message:tr('Alle Terminaktionen lösen administrative Push und E-Mail Benachrichtigungen aus. Push Zustellung setzt ein registriertes Gerät und die Systemfreigabe voraus.','All booking actions trigger administrative push and email alerts. Push delivery requires a registered device and system permission.'),
        rows:[row('',tr('Push Berechtigung dieses Geräts','Push permission on this device'),permissionLabel),
          row('',tr('Neue Buchung und Änderungen','New booking and changes'),tr('Push und E-Mail','Push and email')),
          row('',tr('Absage, Löschung und Statuswechsel','Cancellation, deletion and status changes'),tr('Push und E-Mail','Push and email')),
          row('',tr('Erinnerung vor dem Termin','Appointment reminder'),tr('Push und E-Mail','Push and email')),
          row('',tr('E-Mail Zustellung','Email delivery'),tr('An die konfigurierte Praxisadresse','To the configured clinic address'))],
        actions:[row('register-booking-push',tr('Push Registrierung aktualisieren','Refresh push registration'))],
      }));
    }
    if(name==='services'&&admin){
      catalog=await book('catalog/');
      return render(view(tr('Behandlungen','Treatments'),{rows:catalog.services.map(s=>row('service:'+s.id,s.name,
        String(s.duration_minutes)+' min · '+String(s.buffer_minutes)+' min '+tr('Puffer','buffer')+
        (isSyncedService(s)?' · SimplyBook':'')))}));
    }
    if(name==='intakes'&&admin){
      activeTab='office';
      const params='?q='+encodeURIComponent(intakeSearch)+'&status='+encodeURIComponent(intakeStatus)+'&page='+intakePage;
      let r;
      try {r=await book('forms/'+params+'&from='+encodeURIComponent(intakeFrom)+'&to='+encodeURIComponent(intakeTo));canonicalForms=true;}
      catch(err) {if(err.status!==404&&err.status!==405)throw err;canonicalForms=false;r=await office('submissions/'+params);}
      return render(view(tr('Eingereichte Formulare','Submitted forms'),{subtitle:tr('Digitale Aufnahmebögen','Digital intake forms'),
        fields:[value('query',tr('Patient suchen','Find patient'),intakeSearch),
          value('status',tr('Status','Status'),intakeStatus,[option('',tr('Alle','All')),option('linked',tr('Zugeordnet','Linked')),option('review',tr('Zu prüfen','Review'))]),
          ...(canonicalForms?[value('from',tr('Von (JJJJ-MM-TT)','From (YYYY-MM-DD)'),intakeFrom),value('to',tr('Bis (JJJJ-MM-TT)','To (YYYY-MM-DD)'),intakeTo)]:[])],
        shortcuts:[row('filter-intakes',tr('Filtern','Filter')),row('intake-reviews',tr('Identität prüfen','Review identity'))],
        sectionTitle:tr('FORMULARE','FORMS')+' · '+tr('Seite','Page')+' '+intakePage,
        rows:r.items.map(x=>({...row('submission:'+x.id,x.name,[x.email,x.created_at.slice(0,10)].filter(Boolean).join(' · ')),badge:x.status})),
        actions:[...(r.has_more?[row('intake-next',tr('Nächste Seite','Next page'))]:[]),...(intakePage>1?[row('intake-prev',tr('Vorherige Seite','Previous page'))]:[])],
        empty:tr('Keine Formulare für diese Filter.','No forms match these filters.')}));
    }
    if(name==='intake-reviews'&&admin){
      const r=await office('intake-reviews/');
      return render(view(tr('Identität prüfen','Review identity'),{rows:r.items.map(x=>row('intake:'+x.id,
        x.submission.first_name+' '+x.submission.last_name,x.created_at.slice(0,10))),empty:tr('Keine offenen Prüfungen.','No pending reviews.'),
        actions:[row('identity-review',tr('Doppelte Patientenprofile prüfen','Review duplicate patient profiles'))]}));
    }
    if(name==='identity-review'&&admin){
      const r=await book('identity-review/');
      return render(view(tr('Identität prüfen','Review identity'),{rows:r.items.map(x=>row(
        'review:'+x.left.id+':'+x.right.id,x.left.name+' / '+x.right.name,x.reason))}));
    }
    if(name==='billing-search'&&admin){
      activeTab='office';
      const r=search.length>=2?await office('customers/?q='+encodeURIComponent(search)):{items:[]};
      return render(view(tr('GOÄ Rechnung','GOÄ invoice'),{fields:[value('query',tr('Patient suchen','Find patient'),search)],
        theme:'billing',shortcuts:[row('billing-query',tr('Suchen','Search')),row('billing-settings',tr('Rechnungsdaten','Invoice settings'))],
        empty:tr('Patientennamen eingeben.','Enter a patient name.'),rows:r.items.map(x=>row('billing:'+x.id,x.name,x.email))}));
    }
    if(name==='billing-settings'&&admin){
      const response=await office('invoice-settings/');
      officeSettingsRevision=response.revision;
      const data=response.settings, fields=[
        value('company_name',tr('Rechnungsaussteller','Invoice issuer'),data.company_name),
        value('street',tr('Straße','Street'),data.street),value('postal_code',tr('PLZ','Postal code'),data.postal_code),
        value('city',tr('Ort','City'),data.city),value('email','E-Mail',data.email),value('phone',tr('Telefon','Phone'),data.phone),
        value('tax_number',tr('Steuernummer','Tax number'),data.tax_number),value('vat_id','USt-IdNr.',data.vat_id),
        value('bank_name',tr('Bank','Bank'),data.bank_name),value('iban','IBAN',data.iban),value('bic','BIC',data.bic),
        value('invoice_prefix',tr('Rechnungspräfix','Invoice prefix'),data.invoice_prefix),
        value('next_sequence',tr('Nächste Rechnungsnummer','Next invoice sequence'),data.next_sequence),
      ];
      return render(view(tr('Rechnungseinstellungen','Invoice settings'),{
        message:tr('Änderungen an Rechnungsdaten werden protokolliert. GOÄ-Rechnungen dürfen erst nach medizinischer und steuerlicher Freigabe ausgestellt werden.',
          'Invoice changes are audited. GOÄ issuance requires medical and accounting approval.'),
        fields, actions:[row('save-billing-settings',tr('Rechnungsdaten sicher speichern','Save invoice settings securely'))],
      }));
    }
  }

  async function showPatient(id,{reset=true,scroll}={}) {
    const loaded=await book('patient/'+id+'/?page='+(reset?1:recordPage));
    activeTab='patients';
    if(reset){patientSection='overview';recordPage=1;currentPatientAccount=null;selectedRecord=null;}
    patient=loaded;
    rememberAppointments(patient.appointments);
    return renderPatient(scroll);
  }
  async function renderPatient(scroll,message=''){
    const p=patient.patient;
    const sections=[['overview',tr('Übersicht','Overview')],['appointments',tr('Termine','Appointments')],['records',tr('Patientenakte','Records')],['contact',tr('Kontakt','Contact')],
      ...(admin?[['account',tr('Patientenkonto','Patient account')]]:[])];
    const appointments=patient.appointments||[], records=patient.records||[];
    const timeline=appointments.map(a=>({...row('appointment:'+a.id,a.date+' · '+a.start,[a.service_name&&displayCopy(a.service_name),a.staff_name].filter(Boolean).join(' · ')),badge:a.status}));
    const recordRows=records.map(r=>({...row('record-detail:'+r.id,r.title,[r.date?.slice(0,10),r.note,r.filename].filter(Boolean).join(' · ')),badge:r.kind||''}));
    let accountContent={};
    if(patientSection==='account'&&admin){
      currentPatientAccount=null;
      try {
      let linked;
       try{ linked=await office('patient-account/'+p.id+'/'); }
       catch(err){if(err.status!==404)throw err;linked=null;}
       // Recover only an explicit verified Book ID, never an email/name-only match.
       if(!linked?.customer_id){
         const verified=new Map();
         let successfulSearch=false;
         for(const q of [...new Set([p.email,p.name].filter(v=>String(v||'').trim().length>=2))]){
           try{
             const result=await office('customers/?q='+encodeURIComponent(q));
             successfulSearch=true;
             for(const x of result.items||[])if(Number(x.book_customer_id)===Number(p.id)&&Number(x.id)>0)verified.set(Number(x.id),x);
           }catch(err){if(err.status===401)throw err;}
         }
         if(verified.size===1)linked={customer_id:[...verified.keys()][0]};
         else if(successfulSearch||linked)linked={customer_id:null};
       }
       if(!linked){accountContent={message:tr('Das Patientenkonto konnte nicht geprüft werden. Bitte erneut laden.','The patient account could not be verified. Please reload.'),actions:[row('patient-section:account',tr('Erneut laden','Reload')),row('patient-link-account',tr('Konto suchen','Find account'))]};}
      else if(!linked.customer_id){
        currentPatientAccount=null;
        accountContent={message:tr('Das A+ Patientenkonto ist noch nicht eindeutig mit der Patientenakte verknüpft.','The A+ patient account is not yet linked to this patient record.'),
          actions:[row('patient-link-account',tr('Konto suchen und Identität prüfen','Find account and verify identity'))]};
      }else{
        let detail;
        try{detail=await request('customers/'+linked.customer_id+'/',undefined,'/api/mobile/admin/');}catch(err){if(err.status!==404)throw err;accountContent={message:tr('Das verknüpfte Patientenkonto ist nicht mehr verfügbar. Bitte Identität prüfen.','The linked patient account is no longer available. Please verify identity.'),actions:[row('patient-link-account',tr('Konto prüfen','Verify account'))]};}
        if(detail?.customer){currentPatientAccount=detail.customer;
        accountContent={
          metrics:[row('',tr('A+ Punkte','A+ points'),String(detail.customer.coins)),row('',tr('Guthaben','Credit'),(detail.customer.credit_cents/100).toFixed(2)+' EUR')],
          shortcuts:[row('patient-adjust-points',tr('Punkte korrigieren','Adjust points')),row('patient-wallet-history',tr('Wallet-Verlauf','Wallet history')),row('patient-invoices',tr('GOÄ Rechnungen','GOÄ invoices'))],
          sectionTitle:tr('PAKETE','PACKAGES'),
          rows:(detail.packages||[]).map(x=>({...row('',x.name,String(x.remaining_sessions)+' '+tr('Sitzungen · bis','sessions · until')+' '+x.expires_at),badge:x.status})),
          empty:tr('Keine Pakete.','No packages.'),
        };}
      }
      }catch(err){if(err.status===401)throw err;accountContent={message:tr('Das Patientenkonto ist momentan nicht erreichbar. Bitte erneut laden.','The patient account is temporarily unavailable. Please reload.'),actions:[row('patient-section:account',tr('Erneut laden','Reload'))]};}
    }
    const email=contactEmail(p.email), phone=String(p.phone??'').trim();
    const dialable=Boolean(internationalPhone(phone)), mailable=validContactEmail(email);
    const missing=tr('Nicht angegeben','Not provided');
    const contactRows=[
      row('',tr('Name','Name'),p.name),
      {...row(mailable?'patient-contact-email':'',tr('E-Mail','Email')),label:language==='en'?'Email':'E-Mail',detail:email||missing},
      {...row(dialable?'patient-contact-call':'',tr('Telefon','Phone')),detail:phone||missing},
      ...(p.date_of_birth?[row('',tr('Geburtsdatum','Date of birth'),p.date_of_birth)]:[]),
    ];
    const contactActions=[
      ...(dialable?[row('patient-contact-call',tr('Anrufen','Call')),row('patient-contact-whatsapp','WhatsApp')]:[]),
      ...(mailable?[{...row('patient-contact-email','Email'),label:language==='en'?'Email':'E-Mail'}]:[]),
      ...(phone?[row('patient-copy-phone',tr('Telefonnummer kopieren','Copy phone number'))]:[]),
      ...(email?[{...row('patient-copy-email','Copy email'),label:language==='en'?'Copy email':'E-Mail-Adresse kopieren'}]:[]),
      ...(admin?[row('patient-edit-contact',tr('Kontaktdaten bearbeiten','Edit contact details'))]:[]),
    ];
    const contactMessage=message||[
      ...(phone&&!dialable?[tr('Die Telefonnummer hat kein gültiges Format.','The phone number has an invalid format.')]:[]),
      ...(email&&!mailable?[tr('Die E-Mail-Adresse hat kein gültiges Format.','The email address has an invalid format.')]:[]),
    ].join(' ');
    return render(view(p.name,{hero:p.name,heroLabel:tr('PATIENTENAKTE','PATIENT RECORD'),subtitle:[email,phone].filter(Boolean).join(' · '),
      scroll,segments:sections.map(([id,label])=>({...row('patient-section:'+id,label),selected:patientSection===id})),
      ...(patientSection==='overview'?{metrics:[row('patient-section:appointments',tr('Termine (Auszug)','Appointments (shown)'),String(appointments.length)),row('patient-section:records',tr('Akteneinträge (Auszug)','Records (shown)'),String(records.length))],
        shortcuts:[row('new-patient-appointment',tr('Termin hinzufügen','Book appointment')),row('note',tr('Notiz hinzufügen','Add note')),row('upload-pdf',tr('PDF hinzufügen','Add PDF'))],
        sectionTitle:tr('LETZTE TERMINE','RECENT APPOINTMENTS'),rows:timeline.slice(0,3),empty:tr('Keine Termine.','No appointments.')}:
      patientSection==='appointments'?{rows:timeline,empty:tr('Keine Termine.','No appointments.'),actions:[row('new-patient-appointment',tr('Termin hinzufügen','Book appointment'))]}:
      patientSection==='records'?{sectionTitle:tr('DIGITALE AKTE','DIGITAL RECORD')+' · '+tr('Seite','Page')+' '+recordPage,rows:recordRows,empty:tr('Noch keine Akteneinträge.','No records yet.'),
        shortcuts:[row('note',tr('Notiz hinzufügen','Add note')),row('upload-pdf',tr('PDF hinzufügen','Add PDF')),
          row('take-photo',tr('Kamera','Camera')),row('upload-photo',tr('Foto auswählen','Choose photo'))],
        actions:[...(patient.has_more?[row('record-page-next',tr('Nächste Seite','Next page'))]:[]),...(recordPage>1?[row('record-page-prev',tr('Vorherige Seite','Previous page'))]:[])]}:
      patientSection==='account'?accountContent:
      {rows:contactRows,actions:contactActions,message:contactMessage})}));
  }
  async function contactForm() {
    const {patient:p}=await book('patient/'+patient.patient.id+'/contact/');
    patient={...patient,patient:{...patient.patient,...p}};
    return render(view(tr('Kontaktdaten bearbeiten','Edit contact details'),{
      subtitle:p.name,
      fields:[value('phone',tr('Telefon','Phone'),p.phone),{...value('email','Email',contactEmail(p.email)),label:language==='en'?'Email':'E-Mail'}],
      actions:[row('patient-save-contact',tr('Speichern','Save')),row('back',tr('Abbrechen','Cancel'))],
    }));
  }
  async function openNativeContact(channel, contact, event, message) {
    const phone=internationalPhone(contact.phone), email=contactEmail(contact.email);
    if(channel==='email'?!validContactEmail(email):!phone)throw new Error(channel==='email'
      ?tr('Keine gültige E-Mail-Adresse.','No valid email address.')
      :tr('Keine gültige internationale Telefonnummer.','No valid international phone number.'));
    current={...current,scroll:event.scroll??current.scroll};
    await checkpoint();
    try {
      await plugin.openContact(channel==='email'?{channel,email}:{channel,phone,...(message?{message}:{direct:true})});
    } catch {
      throw new Error({
        phone:tr('Die Telefon-App ist nicht verfügbar.','The phone app is unavailable.'),
        whatsapp:tr('WhatsApp ist auf diesem Gerät nicht verfügbar.','WhatsApp is unavailable on this device.'),
        email:tr('Keine E-Mail-App verfügbar.','No email app is available.'),
      }[channel]);
    }
  }
  async function getAppointment(id) {
    const known=appointmentsById.get(id);
    if(known?.date){
      const fresh=await book('calendar/?start='+startWeek(known.date)+'&days=7');
      rememberAppointments(fresh.appointments);
      const match=fresh.appointments.find(item=>item.id===id);
      if(match)return {...match,calendar_editability_contract:fresh.calendar_editability_contract,calendar_actor_role:fresh.calendar_actor_role};
    }
    const result=await book('appointments/?page=1');
    let item=result.items.find(x=>x.id===id);

    const r=await book('calendar/?start='+startWeek(item?.date||date)+'&days=7');
    const match=r.appointments.find(x=>x.id===id);
    if(match)item={...match,calendar_editability_contract:r.calendar_editability_contract,calendar_actor_role:r.calendar_actor_role};
    if(!item)throw new Error(tr('Termin nicht verfügbar.','Appointment unavailable.'));
    return item;
  }
  function editabilityRows(item,kind){
    const flag = name => typeof item[name] === 'boolean' ? String(item[name]) : 'missing';
    const code = name => typeof item[name] === 'string' && /^[a-z0-9_-]{1,80}$/i.test(item[name]) ? item[name] : 'missing';
    return [row('', 'API contract', code('calendar_editability_contract')),
      row('', 'API role', code('calendar_actor_role')),
      row('', 'source_managed', flag('source_managed')),
      row('', 'source_editable', flag('source_editable')),
      ...(kind==='block'?[row('', 'editable',flag('editable')),row('', 'source_revision_available',flag('source_revision_available'))]:
        [row('', 'source_identity_available',flag('source_identity_available')),row('', 'source_time_supported',flag('source_time_supported')),row('', 'sync_state',item.sync_state===''?'empty':code('sync_state'))]),
      row('', 'Eligibility reason', code('source_editability_reason')),
      ...(item.source_readback_diagnostic?[row('', 'Source readback',code('source_readback_diagnostic'))]:[])];
  }
  async function showEditabilityDiagnostic(kind){
    const item=kind==='appointment'?appointment:currentBlock;
    const id=kind==='appointment'?item?.id:(item?.record_id??item?.id);
    const managed=kind==='block'?sourceOfBlock(item)==='SimplyBook':item?.source_managed===true;
    if(!admin||!managed||!Number.isSafeInteger(Number(id))||Number(id)<=0)return;
    let fresh=item;
    try {
      const response=await book('calendar/?start='+startWeek(item.date)+'&days=7&diagnose='+encodeURIComponent(kind+':'+id));
      const found=(kind==='appointment'?response.appointments:response.blocks).find(x=>String(kind==='appointment'?x.id:(x.record_id??x.id))===String(id));
      if(found)fresh={...found,calendar_editability_contract:response.calendar_editability_contract,calendar_actor_role:response.calendar_actor_role};
    } catch (_) { fresh={...item,source_readback_diagnostic:'relay_readback_unavailable'}; }
    return render(view(tr('Freigabediagnose','Editability diagnostic'),{
      message:tr('Nur Freigabefelder der authentifizierten API. Keine Zugangsdaten oder Patientendetails.','Only authenticated API eligibility fields. No credentials or patient details.'),
      rows:editabilityRows(fresh,kind),actions:[row('calendar',tr('Zurück zum Kalender','Back to calendar'))],
    }));
  }
  function appointmentSourceMessage(item) {
    if(!item.source_managed)return '';
    if(['queued','sending'].includes(item.sync_state))return tr('Bestätigung durch SimplyBook steht aus.','Awaiting SimplyBook confirmation.');
    if(['review','blocked'].includes(item.sync_state))return tr('SimplyBook konnte die Buchung nicht bestätigen. Bitte den Buchungsstatus prüfen.','SimplyBook could not confirm the booking. Check its status.');
    if(admin&&item.source_editable)return tr('Terminzeit und Absage werden zuerst in SimplyBook bestätigt.','Rescheduling and cancellation are confirmed in SimplyBook first.');
    if(!admin)return tr('Änderungen an SimplyBook-Terminen benötigen Administratorrechte.','Changes to SimplyBook appointments require administrator access.');
    if(item.source_time_supported===false)return tr('Nur bestätigte zukünftige Termine des verbundenen Behandlers können hier geändert werden.','Only confirmed future appointments for the connected provider can be changed here.');
    if(item.source_identity_available===false)return tr('Die SimplyBook-Buchungsnummer muss zuerst geprüft werden.','The SimplyBook booking ID must be verified first.');
    return tr('Die Änderung in SimplyBook ist derzeit nicht freigegeben.','Changes in SimplyBook are currently unavailable.');
  }
  async function showAppointment(id,scroll) {
    activeTab='calendar';
    appointment=await getAppointment(id);
    let contact={};
    if(appointment.customer_id){try { const detail=await book('patient/'+appointment.customer_id+'/'); contact=detail.patient||{}; } catch(err) { if(err.status!==404) throw err; }}
    const treatmentEnd=String(appointment.treatment_end_at||'').match(/T(\d{2}:\d{2})/)?.[1]||appointment.end;
    return render(view(appointment.customer_name,{
      subtitle:displayCopy(appointment.service_name), scroll,
      message:appointmentSourceMessage(appointment),
      rows:[
        row('',appointment.date+' · '+appointment.start+' – '+treatmentEnd, appointment.staff_name),
        ...(treatmentEnd!==appointment.end?[row('',tr('Reserviert bis','Reserved until'),appointment.end)]:[]),
        row('',tr('Status','Status'),appointment.status),row('',tr('Notiz','Note'),appointment.notes||''),
        row('',tr('Patient','Patient'),appointment.customer_name),row('',tr('Telefon','Phone'),contact.phone||tr('Nicht angegeben','Not provided')),row('','E Mail',contact.email||tr('Nicht angegeben','Not provided')),
      ],actions:[...(['new','confirmed'].includes(appointment.status)&&appointment.date>=today()?[row('appointment-reminder',tr('App Erinnerung senden','Send app reminder'))]:[]),...(contact.phone?[row('appointment-call',tr('Patient anrufen','Call patient')),row('appointment-whatsapp',tr('WhatsApp Erinnerung vorbereiten','Prepare WhatsApp reminder'))]:[]),...(appointment.customer_id?[row('patient:'+appointment.customer_id,tr('Patientenakte öffnen','Open patient record'))]:[]),...(appointment.source_managed && !(admin&&appointment.source_editable)
        ? [...(admin?[row('appointment-editability-diagnostic',tr('Freigabediagnose','Editability diagnostic'))]:[]),row('calendar',tr('Zurück zum Kalender','Back to calendar'))]
        : [row('edit-appointment',tr('Bearbeiten','Edit')),row('cancel-appointment',tr('Absagen','Cancel'))])],
    }));
  }
  async function appendForm(edit=false, chosenPatient=null, slot={}) {
    catalog=await book('catalog/');
    const r=await book('patients/?q='+encodeURIComponent(search));
    const options=r.items.map(x=>({...option(x.id,x.name),detail:[x.email,x.phone].filter(Boolean).join(' / ')}));
    if(chosenPatient&&!options.some(x=>x.value===String(chosenPatient.id)))options.unshift(option(chosenPatient.id,chosenPatient.name));
    // The current booking's patient may be outside the paginated search results.
    if(edit && appointment?.customer_id && !options.some(x=>x.value===String(appointment.customer_id))) options.unshift(option(appointment.customer_id,appointment.customer_name));
    const syncedEdit=Boolean(edit&&appointment?.source_managed&&appointment?.source_editable&&admin);
    const providersForBooking=syncedEdit
      ? catalog.providers.filter(p=>Number(p.id)===Number(appointment.staff_id))
      : catalog.providers.filter(p=>!isSyncedProvider(p));
    const servicesForBooking=syncedEdit
      ? catalog.services.filter(s=>Number(s.id)===Number(appointment.service_id))
      : catalog.services.filter(s=>s.active&&!isSyncedService(s));
    // A SimplyBook source booking supports *time only* here. Never show
    // patient/provider/treatment/notes as editable fields when the API would
    // discard or reject those values. Source IDs travel unchanged in payload.
    const fields=syncedEdit ? [
      value('date',tr('Datum (JJJJ-MM-TT)','Date (YYYY-MM-DD)'),appointment.date),
      value('start',tr('Beginn (HH:MM)','Start (HH:MM)'),appointment.start),
    ] : [
      value('customer_id',tr('Patient','Patient'),edit?appointment.customer_id:chosenPatient?.id||'',options),
      value('staff_id',tr('Behandler','Provider'),edit?appointment.staff_id:(slot.staff_id && providersForBooking.some(p=>String(p.id)===String(slot.staff_id)) ? slot.staff_id : providersForBooking[0]?.id),optionFor(providersForBooking)),
      value('service_id',tr('Dienstleistung','Service'),edit?appointment.service_id:'',serviceOptions(servicesForBooking)),
      value('date',tr('Datum (JJJJ-MM-TT)','Date (YYYY-MM-DD)'),edit?appointment.date:(slot.date||date)),
      value('start',tr('Beginn (HH:MM)','Start (HH:MM)'),edit?appointment.start:(slot.start||'10:00')),
      value('notes',tr('Notiz','Notes'),edit?appointment.notes:''),
      ...(edit?[value('status',tr('Status','Status'),appointment.status,[
        option('new',tr('Ausstehend','Pending')),option('confirmed',tr('Bestätigt','Confirmed')),
        option('completed',tr('Abgeschlossen','Completed')),option('no_show',tr('Nicht erschienen','No show')),
      ])]:[]),
    ];
    return render(view(edit?tr('Termin bearbeiten','Edit appointment'):tr('Neuen Termin buchen','Book new appointment'),
      {layout:'simplybook-form',formType:'booking',fields:syncedEdit?fields:[fields[2],fields[1],fields[0],...fields.slice(3)],actions:[row(edit?'save-edit':'save-new',tr('Speichern','Save'))]}));
  }
  let currentBlock, currentService, selectedRecord;
  async function patientLinkForm(query){
    const p=patient.patient;
    const result=query.trim().length>=2?await office('customers/?q='+encodeURIComponent(query.trim())):{items:[]};
    const candidates=(result.items||[]).filter(x=>!x.book_customer_id||Number(x.book_customer_id)===Number(p.id));
    return render(view(tr('Patientenkonto verknüpfen','Link patient account'),{subtitle:p.name,message:tr('Nur nach persönlicher Prüfung der Identität verknüpfen.','Link only after personally verifying the identity.'),fields:[value('query',tr('Name oder E Mail','Name or email'),query),value('customer_id',tr('Patientenkonto','Patient account'),'',[option('',tr('Auswählen','Select')),...candidates.map(x=>option(x.id,[x.name,x.email].filter(Boolean).join(' · ')))]),value('confirm',tr('Identität persönlich geprüft?','Identity verified in person?'),'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))])],actions:[row('patient-link-search',tr('Suchen','Search')),row('patient-link-confirm',tr('Verknüpfen','Link')),row('patient-section:account',tr('Abbrechen','Cancel'))]}));
  }
  async function blockForm(edit){
    catalog=catalog||await book('catalog/');
    const localProviders=catalog.providers.filter(p=>!isSyncedProvider(p));
    if(!localProviders.length)throw new Error(tr('Keine lokal verwalteten Behandler verfügbar.','No locally managed providers available.'));
    return render(view(edit?tr('Kalendereintrag bearbeiten','Edit calendar entry'):tr('Notiz oder Sperrzeit','Note or blocked time'),{layout:'simplybook-form',formType:'block',fields:[
      value('staff_id',tr('Behandler','Provider'),edit?currentBlock.staff_id:(localProviders.find(p=>String(p.id)===String(providerFilter))||localProviders[0]).id,optionFor(edit?localProviders.filter(p=>Number(p.id)===Number(currentBlock.staff_id)):localProviders)),
      value('date',tr('Datum','Date'),edit?currentBlock.date:date),
      value('kind',tr('Zeitraum ist geblockt','Time is blocked'),edit?currentBlock.kind:'note',[option('block',tr('Sperrzeit','Blocked time')),option('note',tr('Notiz','Note'))]),
      value('start',tr('Startzeit','Start time'),edit?currentBlock.start:'10:00'),
      value('end',tr('Endzeit','End time'),edit?currentBlock.end:'10:15'),
      value('text',tr('Text der Notiz','Note text'),edit?currentBlock.text:''),
    ],actions:[row(edit?'save-block-edit':'save-block-new',tr('Speichern','Save')),...(edit?[row('remove-block',tr('Eintrag löschen','Delete entry'))]:[])]}));
  }
  let availabilityTarget=null;
  async function availabilityForm(id, loaded=false){
    catalog=await book('catalog/');
    const provider=catalog.providers.find(p=>String(p.id)===String(id??providerFilter))||catalog.providers.find(p=>!isSyncedProvider(p))||catalog.providers[0];
    if(!provider)throw new Error(tr('Kein Behandler','No provider'));
    availabilityTarget=null;
    if(!loaded)return render(view(tr('Arbeitszeiten','Working hours'),{layout:'simplybook-form',formType:'availability',fields:[value('staff_id',tr('Behandler','Provider'),provider.id,optionFor(catalog.providers)),value('date',tr('Datum','Date'),date)],actions:[row('load-availability',tr('Weiter','Continue'))]}));
    const data=await book('calendar/?start='+date+'&days=1');
    const current=data.availability.find(r=>r.staff_id===provider.id&&r.date===date);
    const ranges=current?.ranges||[];
    if(provider.working_hours_source_managed||isSyncedProvider(provider)){
      return render(view(tr('Arbeitszeit – SimplyBook','Working hours – SimplyBook'),{layout:'simplybook-form',formType:'availability',
        subtitle:provider.name+' · '+date,
        message:tr('Diese Arbeitszeiten werden aus SimplyBook synchronisiert. Bitte direkt in der SimplyBook-Verwaltung ändern. Die Änderungen werden anschließend übernommen.',
                   'These working hours are synced from SimplyBook. Change them in SimplyBook administration; they will sync here.'),
        fields:[value('staff_id',tr('Behandler','Provider'),provider.id,optionFor(catalog.providers)),
          value('date',tr('Datum','Date'),date)],
        rows:ranges.map(r=>row('',r.start+' – '+r.end)),
        actions:[row('load-availability',tr('Behandler / Datum laden','Load provider / date')),
          row('calendar',tr('Zurück zum Kalender','Back to calendar'))],
      }));
    }
    availabilityTarget={staff_id:String(provider.id),date};
    return render(view(tr('Arbeitszeit','Working hours'),{layout:'simplybook-form',formType:'availability',subtitle:provider.name+' · '+date,message:provider.name+' · '+germanDate(date),fields:[
      value('operation',tr('Gültigkeit','Scope'),'daily',[option('daily',tr('Diesen Tag','This day')),option('weekly',tr('Wöchentlich','Weekly')),option('reset',tr('Tagesausnahme zurücksetzen','Reset override'))]),
      value('closed',tr('Geschlossen','Closed'),ranges.length?'no':'yes',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))]),
      value('start_1',tr('Beginn','Start'),ranges[0]?.start||'09:00'),value('end_1',tr('Ende','End'),ranges[0]?.end||'18:00'),
      value('start_2',tr('Zweiter Beginn (optional)','Second start (optional)'),ranges[1]?.start||''),
      value('end_2',tr('Zweites Ende (optional)','Second end (optional)'),ranges[1]?.end||''),
    ],actions:[row('save-availability',tr('Speichern','Save')),row('availability',tr('Behandler oder Datum ändern','Change provider or date'))]}));
  }
  let billingUser, billingVisits, reviewPair, intakeRecord, invoiceLines=[], invoiceMeta={}, editingInvoice=null, selectedInvoice=null, tariffCatalog=null, officeSettingsRevision=null, currentPatientAccount;
  async function showBilling(id) {
    const r=await office('customers/?q='+encodeURIComponent(search));
    billingUser=r.items.find(u=>u.id===id);
    if(!billingUser)throw new Error(tr('Patient nicht verfügbar','Patient unavailable'));
    const list=await office('invoices/'+id+'/');
    return render(view(billingUser.name,{theme:'billing',subtitle:billingUser.email,
      rows:list.items.map(i=>row('invoice-detail:'+i.id,(i.number?i.number+' · ':'')+i.service_date+' · '+(i.total_cents/100).toFixed(2)+' EUR',i.status)),
      actions:[row(billingUser.book_customer_id?'invoice-form':'link-search',billingUser.book_customer_id?tr('GOÄ Entwurf','GOÄ draft'):tr('Book Identität verifizieren','Verify Book identity'))]}));
  }
  async function invoiceForm(initial=true){
    if(initial){
      editingInvoice=null;
      const r=await book('patient/'+billingUser.book_customer_id+'/');
      billingVisits=r.appointments.filter(a=>a.status==='completed');
      if(!billingVisits.length)throw new Error(tr('Kein abgeschlossener Besuch.','No completed visit.'));
      const addr=billingUser.address;
      tariffCatalog=tariffCatalog||await office('tariff-catalog/');
      invoiceLines=[];
      invoiceMeta={visit_id:billingVisits[0].public_id,street:addr.street,postal_code:addr.postal_code,city:addr.city,
        service_date:'',date_correction_reason:'',treatment:'',treatment_quantity:'1',desired_total_eur:''};
    }
    const fields=[
      {...value('treatment',tr('1 · Was wurde behandelt?','1 · What was treated?'),invoiceMeta.treatment||'',[option('',tr('Ohne Auswahl','No selection')),option('botox','Botox'),option('hyaluron','Hyaluron / Filler'),option('prp','PRP'),option('lipolysis',tr('Lipolyse','Lipolysis'))]),kind:'choice-grid'},
      value('treatment_quantity',tr('2 · Anzahl der Behandlungseinheiten (nur Hinweis)','2 · Treatment units (reference only)'),invoiceMeta.treatment_quantity||'1'),
      value('desired_total_eur',tr('3 · Gewünschter Gesamtbetrag (optional, EUR)','3 · Desired total (optional, EUR)'),invoiceMeta.desired_total_eur||''),
      value('visit_id',tr('Besuch','Visit'),invoiceMeta.visit_id,billingVisits.map(a=>option(a.public_id,a.date+' · '+a.service_name))),
      value('service_date',tr('Abweichendes Leistungsdatum (optional)','Corrected visit date (optional)'),invoiceMeta.service_date),
      value('date_correction_reason',tr('Begründung der Datumskorrektur','Reason for date correction'),invoiceMeta.date_correction_reason),
      value('street',tr('Straße','Street'),invoiceMeta.street),value('postal_code',tr('PLZ','Postal code'),invoiceMeta.postal_code),value('city',tr('Ort','City'),invoiceMeta.city),
    ];
    return render(view(tr('GOÄ Entwurf erstellen','Create GOÄ draft'),{theme:'billing',subtitle:billingUser.name,
      message:tr('Gebührennummer, Einfachsatz und Steuerstatus ärztlich prüfen.','Clinician must verify tariff code, base fee and tax classification.'),
      fields, sectionTitle:tr('GOÄ-LEISTUNGSZIFFERN','GOÄ FEE CODES'),
      rows:invoiceLines.map((line,i)=>row('invoice-line:'+i,(line.kind==='material'?tr('Auslage','Expense'):line.goae_number)+' · '+line.goae_description,
        tr('Anzahl','Quantity')+' '+line.quantity+(line.kind==='material'?'':' · '+line.goae_factor+'×'))),
      empty:tr('Noch keine Leistungspositionen.','No service lines yet.'),
      actions:[row('add-invoice-line',tr('Amtliche GOÄ Leistung hinzufügen','Add official GOÄ service')),row('add-manual-line',tr('Manuelle Ziffer (ungeprüft)','Manual code (unverified)')),row('add-material-line',tr('Auslage hinzufügen','Add expense')),
        ...(tariffCatalog?.synthetic_reference_available?[row('reference-case',tr('Synthetische Referenz prüfen','Review synthetic reference'))]:[]),
        ...(invoiceLines.length?[row('invoice-quote',tr('Beträge prüfen','Review totals'))]:[])],
    }));
  }
  async function invoiceDetail(id){
    selectedInvoice=await office('detail/'+id+'/');
    const i=selectedInvoice.invoice;
    return render(view(i.number||tr('GOÄ Entwurf','GOÄ draft'),{theme:'billing',subtitle:i.service_date,
      rows:[row('',tr('Status','Status'),i.status),row('',tr('Gesamt','Total'),(i.total_cents/100).toFixed(2)+' EUR')],
      actions:[row('invoice-pdf:'+id,tr('PDF anzeigen','View PDF')),...(i.status==='draft'?[row('invoice-edit',tr('Entwurf bearbeiten','Edit draft'))]:[]),
        ...(i.status==='draft'&&selectedInvoice.can_simulate?[row('invoice-simulate',tr('Testrechnung nummerieren','Number test invoice'))]:[])]}));
  }
  async function lineForm(index,material=false,manual=false){
    const line=invoiceLines[index]||{};
    if(material||line.kind==='material')return render(view(tr('Auslage erfassen','Record expense'),{theme:'billing',message:tr('Nur tatsächlich entstandene, nach § 10 berechnungsfähige Auslagen erfassen.','Only actual eligible expenses under § 10.'),fields:[
      value('goae_description',tr('Art der Auslage','Expense description'),line.goae_description),value('goae_base_eur',tr('Tatsächlicher Einzelpreis EUR','Actual unit cost EUR'),line.goae_base_eur),
      value('quantity',tr('Anzahl','Quantity'),line.quantity||'1'),value('goae_vat_rate',tr('Umsatzsteuer','VAT'),line.goae_vat_rate||'',[option('',tr('Bitte auswählen','Select')),option('0','0%'),option('7','7%'),option('19','19%')]),
      value('material_receipt_reference',tr('Belegreferenz','Receipt reference'),line.material_receipt_reference),value('material_eligible',tr('Berechnungsfähigkeit geprüft?','Eligibility verified?'),line.material_eligible?'yes':'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))]),
    ],actions:[row('save-material:'+index,tr('Auslage speichern','Save expense')),...(invoiceLines[index]?[row('delete-line:'+index,tr('Position entfernen','Remove line'))]:[])]}));
    if(!manual && (!invoiceLines[index] || line.tariff_source==='official_catalog')){
      tariffCatalog=tariffCatalog||await office('tariff-catalog/');
      const hints=tariffCatalog.treatments[invoiceMeta.treatment]||[];
      const ordered=[...tariffCatalog.items].sort((a,b)=>Number(hints.includes(b.number))-Number(hints.includes(a.number)));
      const choices=ordered.map(i=>option(i.number,(hints.includes(i.number)?tr('Prüfhinweis: ','Review prompt: '):'')+i.number+' · '+(language==='en'?i.en:i.de)+' · '+i.points+' '+tr('Punkte','points')));
      return render(view(tr('Amtliche GOÄ Ziffer','Official GOÄ code'),{theme:'billing',
        message:tr('Nur tatsächlich erbrachte Leistungen eingeben. Ziffer, Menge, Faktor und Steuer ärztlich prüfen; keine Ableitung aus dem Endpreis.','Enter only services actually performed. Code, quantity, factor and tax require physician review; no reverse pricing.'),
        fields:[
          value('goae_number',tr('Gebührenziffer','Fee code'),line.goae_number||'',[option('',tr('Bitte auswählen','Select')),...choices]),
          value('quantity',tr('Tatsächliche Anzahl','Actual quantity'),line.quantity||'1'),
          value('goae_factor',tr('Dokumentierter Faktor','Documented factor'),line.goae_factor||'1.00'),
          value('goae_justification',tr('Individuelle Begründung','Individual justification'),line.goae_justification),
          value('goae_vat_rate',tr('Umsatzsteuer','VAT'),line.goae_vat_rate||'',[option('',tr('Bitte auswählen','Select')),option('0','0%'),option('7','7%'),option('19','19%')]),
          value('clinical_confirmed',tr('Leistung und Anzahl geprüft?','Service and quantity confirmed?'),line.clinical_confirmed?'yes':'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))]),
          value('analog',tr('Analoge Leistung (§ 6)?','Analogous service (§ 6)?'),line.analog?'yes':'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))]),
          value('goae_description',tr('Beschreibung der Analogleistung (falls zutreffend)','Analogous service description (if applicable)'),line.goae_description||''),
          value('analog_confirmed',tr('Äquivalenz ärztlich geprüft?','Equivalence physician-reviewed?'),line.analog_confirmed?'yes':'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))]),
        ],actions:[row('save-verified-line:'+index,tr('Position prüfen','Validate line')),
        ...(invoiceLines[index]?[row('delete-line:'+index,tr('Position entfernen','Remove line'))]:[])]}));
    }
    return render(view(tr('Manuelle GOÄ Position · ungeprüft','Manual GOÄ line · unverified'),{theme:'billing',message:tr('Diese manuelle Ziffer ist nicht durch den hinterlegten Tarif geprüft. Nur Entwurf.','This manual code has not been verified against the included tariff. Draft only.'),fields:[
      value('goae_number','GOÄ Nr.',line.goae_number),value('goae_description',tr('Leistung','Service'),line.goae_description),
      value('goae_base_eur',tr('Einfachsatz EUR','Base fee EUR'),line.goae_base_eur),
      value('goae_points',tr('Punkte (alternativ)','Points (alternative)'),line.goae_points),
      value('goae_category',tr('Gebührenkategorie','Fee category'),line.goae_category||'general',[
        option('general',tr('Allgemein','General')),option('technical',tr('Technisch','Technical')),option('laboratory',tr('Labor','Laboratory'))]),
      value('goae_factor',tr('Faktor','Factor'),line.goae_factor||'1.00'),
      value('quantity',tr('Anzahl','Quantity'),line.quantity||'1'),
      value('goae_vat_rate',tr('Umsatzsteuer','VAT'),line.goae_vat_rate||'',[option('',tr('Bitte auswählen','Select')),option('0','0%'),option('7','7%'),option('19','19%')]),
      value('goae_justification',tr('Begründung','Justification'),line.goae_justification),
    ],actions:[row('save-line:'+index,tr('Position speichern','Save line')),...(invoiceLines[index]?[row('delete-line:'+index,tr('Position entfernen','Remove line'))]:[])]}));
  }
  async function quote(){
    const r=await office('quote/',{lines:invoiceLines,desired_total_eur:invoiceMeta.desired_total_eur||''});
    const money=cents=>(cents/100).toFixed(2)+' EUR';
    return render(view(tr('Entwurf prüfen','Review draft'),{theme:'billing',
      metrics:[row('',tr('Gesamtbetrag','Total amount'),money(r.total_cents)),row('',tr('Netto','Net'),money(r.subtotal_cents)),row('',tr('Steuer','Tax'),money(r.tax_cents))],
      sectionTitle:tr('RECHNUNGSVORSCHAU · ENTWURF','INVOICE PREVIEW · DRAFT'),
      rows:r.items.map(i=>({...row('',(i.goae_number||tr('Auslage','Expense'))+' · '+i.description,[tr('Anz.','Qty')+' '+i.quantity,i.factor&&i.factor!=='None'?tr('Faktor','Factor')+' '+i.factor:'',i.unit_gross_cents!=null?tr('Einzelbetrag','Unit amount')+' '+money(i.unit_gross_cents):'',money(i.gross_cents)].filter(Boolean).join(' · '))})),
      message:r.target_matches===false
        ?tr('Wunschbetrag und geprüfte Positionen stimmen nicht überein: ','Desired amount and verified items do not match: ')+money(r.total_cents)+' ≠ '+money(r.target_cents)
        :tr('Entwurf – nicht zur Zahlung verwenden.','Draft – not for payment.'),
      actions:[...(r.target_matches===false?[]:[row('save-invoice',tr('Entwurf speichern','Save draft'))]),row('invoice-return',tr('Weiter bearbeiten','Continue editing'))]}));
  }

  async function showPDF(path,title,allowImage=false){
    const response=await fetch(origin+'/api/mobile/staff/'+path,{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:requests.signal});
    if(!response.ok)throw Object.assign(new Error(tr('Datei nicht verfügbar','File unavailable')),{status:response.status});
    const blob=await response.blob();
    if(blob.size>8000000)throw new Error(tr('Datei zu groß','File too large'));
    const bytes=new Uint8Array(await blob.arrayBuffer());
    let chunk='';for(let i=0;i<bytes.length;i+=16384)chunk+=String.fromCharCode(...bytes.subarray(i,i+16384));
    if(String.fromCharCode(...bytes.slice(0,5))!=='%PDF-'){
      if(allowImage&&((bytes[0]===0xff&&bytes[1]===0xd8)||(bytes[0]===0x89&&String.fromCharCode(...bytes.slice(1,4))==='PNG'))){
        return render(view(title,{image:btoa(chunk),actions:[row('back',tr('Zurück','Back'))]}));
      }
      throw new Error(tr('Dieses Dateiformat wird noch nicht unterstützt','This file type is not supported'));
    }
    if(active)await plugin.previewPDF({title,base64:btoa(chunk)});
  }
  async function restoreRoute(saved){
    if(!saved || !['home','calendar','patients','settings'].includes(saved.activeTab) || !datePattern.test(saved.date))return false;
    applyRoute(saved);
    await screen(saved.activeTab);
    if(saved.activeTab==='patients' && Number(saved.patientId)>0)await showPatient(saved.patientId,{reset:false});
    if(subviews.test(saved.action)){
      if(saved.action==='edit-appointment' && Number(saved.appointmentId)>0)await showAppointment(saved.appointmentId);
      if(saved.action==='record-edit' && saved.recordId)await handle({id:'record-detail:'+saved.recordId},{restoring:true});
      await handle({id:saved.action,values:saved.values},{restoring:true});
    }
    // A restored contact editor must use values tied to the current revision.
    const fields=current.fields?.map(field=>({...field,value:(saved.action==='patient-edit-contact'?undefined:saved.values?.[field.id])??field.value}));
    const restored={...current,...(fields?{fields}:{}),scroll:saved.scroll,scrollX:saved.scrollX};
    await plugin.render({screen:restored});
    current=restored;
    location=routeState(saved.action);
    return true;
  }
  async function upload(id, event){
    const owner=patient?.patient;
    if(!owner)return;
    const screenKey=current.screenKey;
    const valid=()=>active && current.screenKey===screenKey && patient?.patient.id===owner.id;
    const chosen=await (id==='upload-pdf'?plugin.pickPDF():id==='take-photo'?plugin.takePhoto():plugin.pickPhoto());
    if(!valid() || chosen?.cancelled)return;
    if(!chosen?.filename || !chosen.base64)throw new Error(tr('Datei nicht verfügbar','File unavailable'));
    const payload={customer_id:owner.id,filename:chosen.filename,base64:chosen.base64,key:uuid()};
    const description=owner.name+'\n'+chosen.filename;
    let failure='';
    while(valid()){
      const {confirmed}=await plugin.confirmUpload({title:tr('Datei hinzufügen','Add document'),
        message:failure?description+'\n\n'+failure:description,
        confirm:failure?tr('Erneut versuchen','Try again'):tr('Datei hochladen','Upload file'),
        cancel:tr('Abbrechen','Cancel')});
      if(!valid() || !confirmed)return;
      try{
        await request('book/record-upload/',payload);
        break;
      }catch(error){
        if(error.status===401 || !valid())throw error;
        failure=tr('Datei konnte nicht hochgeladen werden.','Unable to upload the file.');
      }
    }
    if(!valid())return;
    patientSection='records';
    await showPatient(owner.id,{reset:false,scroll:transition?.from?.location?.patientSection==='records'?event.scroll:undefined});
  }
  async function handle(event,{restoring=false}={}) {
    if(!active || (busy && !restoring) || (event.screenKey && event.screenKey!==current.screenKey))return;
    const id=event.id, fields={...(event.values||{})};
    // Office is deliberately unavailable in the mobile workspace; retain web/API business logic.
    if(/^(office$|intakes$|intake-(?:next|prev|reviews|review|link)|filter-intakes$|submission(?:-|:)|billing(?:-|:)|invoice-(?!pdf:)|add-(?:invoice|manual|material)-line|save-(?:billing-settings|verified-line|manual-line|material-line)|delete-line)/.test(id))return;
    const wasBusy=busy, previousTransition=transition;
    const origin=snapshot(event);
    transition={action:id,from:restoring?null:origin};
    busy=true;
    try {
      if(id==='calendar-client-search'&&current.layout==='simplybook-form'&&current.formType==='booking'){
        const query=String(fields._patient_query||'').trim();
        const result=await book('patients/?q='+encodeURIComponent(query));
        const previous=current.fields.find(f=>f.id==='customer_id');
        const selected=previous?.options?.find(o=>o.value===fields.customer_id);
        const options=result.items.map(x=>({...option(x.id,x.name),detail:[x.email,x.phone].filter(Boolean).join(' / ')}));
        if(selected&&!options.some(o=>o.value===selected.value))options.unshift(selected);
        return await render({...current,openChoice:'customer_id',choiceQuery:query,fields:current.fields.map(f=>({...f,value:fields[f.id]??f.value,...(f.id==='customer_id'?{options}: {})}))});
      }
      for(const key of Object.keys(fields).filter(key=>dateFields.has(key))){
        const canonical=canonicalDate(fields[key]);
        if(canonical!==null)fields[key]=canonical;
        else if(/^(save-|load-availability|filter-intakes|invoice-)/.test(id))throw new Error(tr('Bitte ein gültiges Datum im Format TT.MM.JJJJ eingeben.','Enter a valid date in DD.MM.YYYY format.'));
      }
      if(id==='logout'){await destroy();logout();return;}
      if(id==='retry-initial')return await openInitial();
      if(id==='back'){
        const previous=history.at(-1);
        if(!previous){
          if(location?.action==='home'){
            if(globalThis.Capacitor?.getPlatform?.()==='android')await globalThis.Capacitor?.Plugins?.App?.minimizeApp?.();
            return;
          }
          transition=null;
          return await screen('home');
        }
        transition=null;
        if(previous.screen){
          await plugin.render({screen:previous.screen,calendar:previous.calendarScreen});
          if(!active)return;
          current=previous.screen;
          location=previous.location;
          calendarScreen=previous.calendarScreen;
          applyRoute(location);
          ({patient,appointment,currentBlock,currentService,selectedRecord,currentPatientAccount}=previous.models);
          if(/^appointment:\d+$/.test(location.action))await showAppointment(Number(location.action.split(':')[1]),current.scroll);
          if(/^patient:\d+$/.test(location.action)&&patientSection==='contact')await showPatient(patient.patient.id,{reset:false,scroll:current.scroll});
        }else await restoreRoute(previous.location);
        history.pop();
        return;
      }
      if(['home','calendar','patients','identity-review','settings','services'].includes(id)){
        if(id==='patients'||id==='billing-search')search='';
        if(id==='patients')patientPage=1;
        if(id==='intakes'){intakeSearch='';intakeStatus='';intakePage=1;intakeFrom='';intakeTo='';}
        return await screen(id);
      }
      if(id==='cal-today'){date=today();return await screen('calendar');}
      if(id.startsWith('cal-mode:')){
        calendarMode=id.slice('cal-mode:'.length);
        if(!['day','week','provider','service'].includes(calendarMode))return;
        return await screen('calendar');
      }
      if(id.startsWith('cal-provider:')){
        providerFilter=id.slice('cal-provider:'.length);
        return await screen('calendar');
      }
      if(id.startsWith('cal-service:')){
        serviceFilter=id.slice('cal-service:'.length);
        return await screen('calendar');
      }
      if(id.startsWith('slot:')){
        const parts=id.split(':');
        const day=parts[1],time=parts[2]+':'+parts[3];
        if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!/^\d{2}:\d{2}$/.test(time))return;
        date=day;
        search='';
        return await appendForm(false,null,{date:day,start:time,staff_id:parts[4]||providerFilter});
      }
      if(id==='week-next'||id==='week-prev'){date=shiftDay(date,id==='week-next'?7:-7);return await screen('calendar');}
      if(id==='day-next'||id==='day-prev'){
        // Swipe the appointment body by a day, or by a week in weekly mode.
        const delta=calendarMode==='week'?7:1;
        date=shiftDay(date,id==='day-next'?delta:-delta);
        return await screen('calendar');
      }
      if(id.startsWith('date:')){date=id.slice(5);return await screen('calendar');}
      if(id==='search'||id==='billing-query'){search=fields.query||'';patientPage=1;return await screen(id==='search'?'patients':'billing-search');}
      if(id==='patient-page-next'||id==='patient-page-prev'){patientPage=Math.max(1,patientPage+(id.endsWith('next')?1:-1));return await screen('patients');}
      if(id.startsWith('patient-section:')&&patient){
        patientSection=id.slice('patient-section:'.length);
        if(patientSection==='contact')return await showPatient(patient.patient.id,{reset:false});
        return await renderPatient();
      }
      if(admin&&id==='patient-edit-contact'&&patient&&patientSection==='contact')return await contactForm();
      if(admin&&id==='patient-save-contact'&&patient&&location?.action==='patient-edit-contact'){
        const p=patient.patient, changes={};
        const phone=String(fields.phone??p.phone).trim(), email=String(fields.email??contactEmail(p.email)).trim();
        if(phone!==String(p.phone??'').trim()){
          if(phone&&!internationalPhone(phone))throw new Error(tr('Bitte eine gültige internationale Telefonnummer eingeben.','Enter a valid international phone number.'));
          changes.phone=phone?internationalPhone(phone):'';
        }
        if(email!==contactEmail(p.email)){
          if(email&&!validContactEmail(email))throw new Error(tr('Bitte eine gültige E-Mail-Adresse eingeben.','Enter a valid email address.'));
          changes.email=email;
        }
        if(!Object.keys(changes).length)return await renderPatient();
        try {
          const saved=await book('patient/'+p.id+'/contact/',{...changes,revision:p.contact_revision});
          patient={...patient,patient:{...p,...saved.patient}};
        } catch(err) {
          if(err.status===409)throw new Error(tr('Die Kontaktdaten wurden inzwischen geändert oder gehören zu einem anderen Patientenprofil. Bitte prüfen und erneut öffnen.','The contact details changed or are assigned to another patient profile. Check the details and reopen the editor.'));
          throw err;
        }
        return await renderPatient(undefined,tr('Kontaktdaten gespeichert.','Contact details saved.'));
      }
      if(/^patient-(?:contact-(?:call|whatsapp|email)|copy-(?:phone|email))$/.test(id)&&patient&&patientSection==='contact'&&location?.action==='patient:'+patient.patient.id){
        let p;
        const patientId=patient.patient.id;
        try {({patient:p}=await book('patient/'+patientId+'/contact/'));}
        catch(err) {
          if(err.status!==404)throw err;
          // The pre-release backend still exposes this authorized read.
          ({patient:p}=await book('patient/'+patientId+'/'));
        }
        if(p?.id!==patientId)throw new Error(tr('Patient nicht verfügbar.','Patient unavailable.'));
        // A stale row must never open a different recipient than the one displayed.
        if(p.phone!==patient.patient.phone||contactEmail(p.email)!==contactEmail(patient.patient.email)){
          patient={...patient,patient:{...patient.patient,...p}};
          return await renderPatient(event.scroll,tr('Kontaktdaten aktualisiert. Bitte Aktion erneut auswählen.','Contact details updated. Select the action again.'));
        }
        if(id.startsWith('patient-copy-')){
          const copied=id.endsWith('phone')?String(p.phone??'').trim():contactEmail(p.email);
          if(!copied)return;
          try {await plugin.copyContact({value:copied});}
          catch {throw new Error(tr('Kopieren fehlgeschlagen.','Unable to copy contact details.'));}
          return await renderPatient(event.scroll,id.endsWith('phone')
            ?tr('Telefonnummer kopiert.','Phone number copied.')
            :tr('E-Mail-Adresse kopiert.','Email address copied.'));
        }
        return await openNativeContact(id.endsWith('call')?'phone':id.split('-').at(-1),p,event);
      }
      if(admin&&id==='patient-link-account'&&patient)return await patientLinkForm(patient.patient.email||patient.patient.name||'');
      if(admin&&id==='patient-link-search'&&patient)return await patientLinkForm(fields.query||'');
      if(admin&&id==='patient-link-confirm'&&patient){
        if(fields.confirm!=='yes'||!Number.isInteger(Number(fields.customer_id))||Number(fields.customer_id)<=0)throw new Error(tr('Patientenkonto auswählen und Identität bestätigen.','Select an account and confirm identity.'));
        await office('link/',{customer_id:Number(fields.customer_id),book_customer_id:patient.patient.id,confirmed_same_patient:true});
        patientSection='account';return await renderPatient();
      }
      if(admin&&id==='patient-adjust-points'&&currentPatientAccount){
        return await render(view(tr('Punkte korrigieren','Adjust points'),{subtitle:currentPatientAccount.name,
          fields:[value('coin_delta',tr('Punkteänderung (positiv oder negativ)','Point adjustment (positive or negative)')),value('confirm',tr('Konto und Änderung geprüft?','Account and adjustment checked?'),'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))])],
          actions:[row('patient-save-points',tr('Korrektur bestätigen','Confirm adjustment')),row('patient-section:account',tr('Abbrechen','Cancel'))]}));
      }
      if(admin&&id==='patient-save-points'&&currentPatientAccount){
        const delta=Number(fields.coin_delta);
        if(fields.confirm!=='yes'||!Number.isInteger(delta)||delta===0||Math.abs(delta)>100000)throw new Error(tr('Gültige Änderung bestätigen.','Confirm a valid adjustment.'));
        await command('points/'+currentPatientAccount.id+'/',{coin_delta:delta});
        return await renderPatient();
      }
      if(admin&&id==='patient-invoices'&&currentPatientAccount){
         const account=currentPatientAccount;
         let items=[],message='';
         try{
           const result=await office('invoices/'+account.id+'/');
           if(!Array.isArray(result.items))throw new Error('invalid invoice response');
           items=result.items.filter(i=>Number(i.customer_id)===Number(account.id));
         }catch(err){if(err.status===401)throw err;message=tr('GOÄ Rechnungen momentan nicht verfügbar. Bitte erneut versuchen.','GOÄ invoices temporarily unavailable. Please try again.');}
         const statuses={draft:tr('Entwurf','Draft'),issued:tr('Ausgestellt','Issued'),cancelled:tr('Storniert','Cancelled'),paid:tr('Bezahlt','Paid')};
         return await render(view(tr('GOÄ Rechnungen','GOÄ invoices'),{subtitle:account.name,message,
           rows:items.map(i=>row('',[i.number||tr('Entwurf','Draft'),i.service_date,(Number(i.total_cents)/100).toFixed(2)+' EUR'].filter(Boolean).join(' · '),statuses[i.status]||i.status)),
           empty:message?'':tr('Keine GOÄ Rechnungen.','No GOÄ invoices.'),
           actions:[...(message?[row('patient-invoices',tr('Erneut laden','Reload'))]:[]),row('patient-section:account',tr('Zurück zum Konto','Back to account'))]}));
       }
       if(admin&&id==='patient-wallet-history'&&currentPatientAccount){
        const result=await request('customers/'+currentPatientAccount.id+'/wallet-history/',undefined,'/api/mobile/admin/');
        return await render(view(tr('Wallet-Verlauf','Wallet history'),{subtitle:currentPatientAccount.name,
          rows:(result.transactions||[]).map(x=>row('',x.description||x.kind_label,[x.created_at?.slice(0,10),x.direction_label,x.coin_amount?String(x.coin_amount)+' '+tr('Punkte','points'):(x.amount_cents/100).toFixed(2)+' EUR'].filter(Boolean).join(' · '))),
          empty:tr('Keine Transaktionen.','No transactions.'),actions:[row('patient-section:account',tr('Zurück zum Konto','Back to account'))]}));
      }
      if((id==='record-page-next'||id==='record-page-prev')&&patient){recordPage=Math.max(1,recordPage+(id.endsWith('next')?1:-1));return await showPatient(patient.patient.id,{reset:false});}
      if(admin&&id==='filter-intakes'){intakeSearch=fields.query||'';intakeStatus=fields.status||'';intakeFrom=fields.from||'';intakeTo=fields.to||'';intakePage=1;return await screen('intakes');}
      if(admin&&(id==='intake-next'||id==='intake-prev')){intakePage=Math.max(1,intakePage+(id.endsWith('next')?1:-1));return await screen('intakes');}
      if(admin&&id.startsWith('submission:')){
        const formId=Number(id.slice(11));
        submission=(canonicalForms?await book('forms/'+formId+'/'):await office('submission/'+formId+'/')).submission;
        const d=submission.identity, entries=(obj)=>Object.entries(obj||{}).filter(([,v])=>v!==null&&v!==''&&(!Array.isArray(v)||v.length))
          .map(([k,v])=>row('',k.replaceAll('_',' '),Array.isArray(v)?v.join(', '):String(v)));
        return await render(view(tr('Aufnahmebogen','Intake form'),{
          subtitle:[d.first_name,d.last_name,submission.created_at.slice(0,10)].filter(Boolean).join(' · '),
          message:submission.status==='review'?tr('Patientenidentität muss geprüft werden.','Patient identity requires review.'):'',
          sectionTitle:tr('PATIENT & ANAMNESE','PATIENT & MEDICAL HISTORY'),
          rows:[...entries(d),...entries(submission.answers),...(submission.consent_text?[row('',tr('Einwilligung','Consent'),submission.consent_text)]:[])],
          image:(submission.signature_png||'').split(',')[1]||'',
          actions:[...(canonicalForms||submission.book_customer_id&&submission.book_record_id?[row('submission-pdf',tr('Unterschriebenes PDF öffnen','Open signed PDF'))]:[]),
            ...(submission.book_customer_id?[row('patient:'+submission.book_customer_id,tr('Patientenakte öffnen','Open patient record'))]:[]),
            ...(submission.status==='review'?[row(canonicalForms?'submission-link':'intake-reviews',tr('Identität prüfen','Review identity'))]:[]),
            row('intakes',tr('Zurück zu Formularen','Back to forms'))]}));
      }
      if(admin&&id==='submission-pdf'&&submission){
        if(canonicalForms)return await showPDF('book/forms/'+submission.id+'/pdf/',tr('Aufnahmebogen','Intake form'));
        if(submission.book_customer_id&&submission.book_record_id)return await showPDF('book/patient/'+submission.book_customer_id+'/records/'+submission.book_record_id+'/',tr('Aufnahmebogen','Intake form'));
      }
      if(admin&&id==='submission-link'&&submission&&canonicalForms){
        const d=submission.identity;
        const q=fields.query??d.last_name??'';
        const r=await book('patients/?q='+encodeURIComponent(q));
        return await render(view(tr('Formular zuordnen','Link form'),{subtitle:[d.first_name,d.last_name,d.email,d.phone,d.date_of_birth].filter(Boolean).join(' · '),
          message:tr('Mindestens drei Identitätsmerkmale müssen übereinstimmen.','At least three identity attributes must match.'),
          fields:[value('query',tr('Patient suchen','Find patient'),q),value('customer_id',tr('Bestehende Patientenakte','Existing patient record'),'',[option('',tr('Auswählen','Select')),...r.items.map(x=>option(x.id,[x.name,x.email,x.phone].filter(Boolean).join(' · ')))]),
          value('confirm',tr('Identität persönlich geprüft?','Identity verified in person?'),'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))])],
          actions:[row('submission-link',tr('Erneut suchen','Search again')),row('submission-confirm',tr('Zuordnung bestätigen','Confirm link'))]}));
      }
      if(admin&&id==='submission-confirm'&&submission&&canonicalForms){
        if(fields.confirm!=='yes'||!fields.customer_id)throw new Error(tr('Identität bestätigen.','Confirm identity.'));
        await book('forms/'+submission.id+'/link/',{customer_id:Number(fields.customer_id),confirmed_same_patient:true});
        return await screen('intakes');
      }
      if(admin&&id==='save-billing-settings'){
        // Optimistic revision protects concurrent edits made in the original Office admin.
        await office('invoice-settings/',{...fields,next_sequence:Number(fields.next_sequence),
          revision:officeSettingsRevision,confirmed_financial_update:true});
        return await screen('billing-settings');
      }
      if(id.startsWith('patient:'))return await showPatient(Number(id.split(':')[1]));
      if(id.startsWith('appointment:'))return await showAppointment(Number(id.split(':')[1]));
      if(id==='appointment-editability-diagnostic')return await showEditabilityDiagnostic('appointment');
      if(id==='block-editability-diagnostic')return await showEditabilityDiagnostic('block');
      if(id==='appointment-reminder'){
        return await render(view(tr('Terminerinnerung','Appointment reminder'),{subtitle:appointment.customer_name,message:tr('App Benachrichtigung an diesen Patienten senden?','Send an app notification to this patient?'),actions:[row('confirm-appointment-reminder',tr('Erinnerung senden','Send reminder')),row('appointment:'+appointment.id,tr('Abbrechen','Cancel'))]}));
      }
      if(id==='confirm-appointment-reminder'){
        await command('book/appointment-reminder/',{id:appointment.id});
        return await render(view(tr('Erinnerung erstellt','Reminder created'),{message:tr('Die Erinnerung wurde im App Postfach erstellt. Push Zustellung hängt von den Geräteeinstellungen ab.','The reminder was created in the app inbox. Push delivery depends on device settings.'),actions:[row('appointment:'+appointment.id,tr('Zurück zum Termin','Back to appointment'))]}));
      }
      if(id==='appointment-call'||id==='appointment-whatsapp'){
        // Re-fetch authorized contact before opening a native external action.
        const detail=await book('patient/'+appointment.customer_id+'/');
        const message=language==='en'?'Hello, this is a friendly reminder of your appointment on '+germanDate(appointment.date)+' at '+appointment.start+' with A+ Esthetic.':'Guten Tag, wir möchten Sie freundlich an Ihren Termin am '+germanDate(appointment.date)+' um '+appointment.start+' bei A+ Esthetic erinnern.';
        return await openNativeContact(id==='appointment-call'?'phone':'whatsapp',detail.patient||{},event,message);
      }
      if(id==='apply-calendar-filter'){
        calendarMode=fields.calendar_mode;providerFilter=fields.provider_filter;serviceFilter=fields.service_filter;
        return await screen('calendar');
      }
      if(id==='new-block')return await blockForm(false);
      if(id.startsWith('block:')||id.startsWith('block-info:')){
        currentBlock=blockById.get(Number(id.split(':').at(-1)));
        if(!currentBlock)return await screen('calendar');
        const fresh=await book('calendar/?start='+startWeek(currentBlock.date)+'&days=7');
        const entry=fresh.blocks.find(item=>item.id===currentBlock.id ||
          (currentBlock.record_id!=null&&item.record_id===currentBlock.record_id));
        if(!entry){invalidateCalendar();return await screen('calendar');}
        currentBlock={...entry,calendar_editability_contract:fresh.calendar_editability_contract,calendar_actor_role:fresh.calendar_actor_role};
        if(currentBlock.editable)return await blockForm(true);
        const owner=sourceOfBlock(currentBlock);
        const viaSimplyBook=owner==='SimplyBook';
        return await render(view(tr('Kalendereintrag','Calendar entry'),{
          subtitle:currentBlock.date+' · '+currentBlock.start+' – '+currentBlock.end,
          message:viaSimplyBook
            ? (currentBlock.source_revision_available===false && admin
              ?tr('Für diesen SimplyBook-Eintrag fehlt eine bearbeitbare Quellrevision. Bitte Eintrag und Gültigkeit in SimplyBook prüfen.','This SimplyBook entry lacks a verified editable revision. Check its source entry and scope in SimplyBook.')
              :tr('Änderungen an diesem SimplyBook-Eintrag sind für Ihre Rolle oder in dieser Ansicht nicht verfügbar.','Editing this SimplyBook entry is unavailable for your role or in this view.'))
            :tr('Dieser Eintrag wird in der Book-Verwaltung verwaltet und ist in der App schreibgeschützt. Bitte Änderungen dort vornehmen.',
                'This entry is managed in Book administration and is read-only in the app. Make changes there.'),
          rows:[row('',tr('Verwaltet in','Managed in'),owner),
            row('',tr('Eintrag','Entry'),(currentBlock.text||'').split('\u2063')[0]),
            row('',tr('Behandler','Provider'),(catalog?.providers||[]).find(p=>p.id===currentBlock.staff_id)?.name||'')],
          actions:[...(admin&&viaSimplyBook?[row('block-editability-diagnostic',tr('Freigabediagnose','Editability diagnostic'))]:[]),row('calendar',tr('Zurück zum Kalender','Back to calendar'))],
        }));
      }
      if(['save-block-new','save-block-edit','remove-block'].includes(id)){
        if(id==='remove-block'){
          await command('book/block/',{operation:'delete',staff_id:currentBlock.staff_id,id:currentBlock.id});
        } else {
          if(!fields.date||!fields.staff_id||!['note','block'].includes(fields.kind)||!fields.start||!fields.end||fields.start>=fields.end||(fields.kind==='note'&&!String(fields.text||'').trim()))throw new Error(tr('Bitte Datum, Behandler, Zeitraum und Notiz prüfen.','Check date, provider, time range and note.'));
          await command('book/block/',{...fields,staff_id:Number(fields.staff_id),operation:id==='save-block-new'?'create':'update',...(id==='save-block-edit'?{id:currentBlock.id}:{})});
          date=fields.date;
        }
        invalidateCalendar();
        return await screen('calendar');
      }
      if(id==='availability')return await availabilityForm();
      if(id==='load-availability'){if(!fields.date||!fields.staff_id)throw new Error(tr('Bitte Behandler und Datum auswählen.','Choose provider and date.'));date=fields.date;return await availabilityForm(fields.staff_id,true);}
      if(id==='save-availability'){if(!availabilityTarget)throw new Error(tr('Arbeitszeit bitte neu laden.','Reload working hours.'));await command('book/availability/',{...fields,staff_id:Number(availabilityTarget.staff_id),date:availabilityTarget.date,closed:fields.closed==='yes'});invalidateCalendar();date=availabilityTarget.date;availabilityTarget=null;return await screen('calendar');}
      if(admin&&id.startsWith('service:')){
        currentService=catalog.services.find(s=>s.id===Number(id.split(':')[1]));
        if(!currentService)return;
        if(isSyncedService(currentService)){
          return await render(view(currentService.name,{
            message:tr('Diese Behandlung wird aus SimplyBook synchronisiert. Bitte Änderungen direkt in der SimplyBook-Verwaltung vornehmen. Die aktualisierten Daten werden anschließend hier angezeigt.',
                       'This treatment is synced from SimplyBook. Edit it in SimplyBook administration; the updated data will appear here.'),
            rows:[row('',tr('Verwaltet in','Managed in'),'SimplyBook'),
              row('',tr('Dauer','Duration'),String(currentService.duration_minutes)+' min'),
              row('',tr('Preis','Price'),currentService.price_label||'')],
            actions:[row('services',tr('Zurück zu Behandlungen','Back to treatments'))],
          }));
        }
        const boolOptions=[option('yes',tr('Ja','Yes')),option('no',tr('Nein','No'))];
        return await render(view(currentService.name,{fields:[
          value('name',tr('Name','Name'),currentService.name),value('description',tr('Beschreibung','Description'),currentService.description),
          value('duration_minutes',tr('Dauer (Min.)','Duration (min.)'),currentService.duration_minutes),
          value('buffer_minutes',tr('Puffer (Min.)','Buffer (min.)'),currentService.buffer_minutes),
          value('price_label',tr('Preis','Price'),currentService.price_label),
          value('active',tr('Aktiv','Active'),currentService.active?'yes':'no',boolOptions),
          value('bookable',tr('Buchbar','Bookable'),currentService.bookable?'yes':'no',boolOptions),
        ],actions:[row('save-service',tr('Speichern','Save'))]}));
      }
      if(admin&&id==='save-service'){
        await command('book/service/',{...fields,id:currentService.id,duration_minutes:Number(fields.duration_minutes),buffer_minutes:Number(fields.buffer_minutes),active:fields.active==='yes',bookable:fields.bookable==='yes'});
        catalog=null;return await screen('services');
      }
      if(admin&&id==='booking-notifications')return await screen('booking-notifications');
      if(admin&&id==='register-booking-push'){
        const register=globalThis.APlusNativePush?.register;
        if(typeof register!=='function')throw new Error(tr('Push Registrierung ist nicht verfügbar.','Push registration is unavailable.'));
        await register();
        return await screen('booking-notifications');
      }
      if(id==='language')return await render(view(tr('Sprache','Language'),{message:tr('Sprachwechsel wird beim nächsten Öffnen angewendet.','Language applies when reopening.'),fields:[value('language',tr('Sprache','Language'),language,[option('de','Deutsch'),option('en','English')])],actions:[row('save-language',tr('Speichern','Save'))]}));
      if(id==='save-language'){
        if(!['de','en'].includes(fields.language))throw new Error(tr('Ungültige Sprache.','Invalid language.'));
        language=fields.language;
        locale=language==='en'?'en-GB':'de-DE';
        localStorage.setItem('aplus_language',language);
        // Keep navigation and screen labels in sync without an app restart.
        return await screen('settings');
      }
      if(id==='new-appointment'){search='';return await appendForm(false);}
      if(id==='new-patient-appointment')return await appendForm(false,patient.patient);
      if(id.startsWith('record-detail:')&&patient){
        selectedRecord=patient.records.find(r=>r.id===id.slice('record-detail:'.length));
        if(!selectedRecord)throw new Error(tr('Akteneintrag nicht verfügbar.','Record unavailable.'));
        return await render(view(selectedRecord.title,{subtitle:patient.patient.name,
          rows:[row('',tr('Erfasst','Recorded'),selectedRecord.date?.slice(0,10)||''),row('',tr('Notiz','Note'),selectedRecord.note||'—'),
            ...(selectedRecord.filename?[row('',tr('Datei','File'),selectedRecord.filename)]:[])],
          actions:[...(selectedRecord.has_file?[row('record-open',tr('Datei öffnen','Open file'))]:[]),
            ...(selectedRecord.editable?[row('record-edit',tr('Notiz korrigieren','Correct note'))]:[]),row('patient-section:records',tr('Zur Patientenakte','Back to record'))]}));
      }
      if(id==='record-open'&&selectedRecord&&patient)return await showPDF('book/patient/'+patient.patient.id+'/records/'+selectedRecord.id+'/',selectedRecord.title,true);
      if(id==='record-edit'&&selectedRecord?.editable&&patient){
        return await render(view(tr('Notiz korrigieren','Correct note'),{subtitle:patient.patient.name,
          message:tr('Die ursprüngliche Fassung bleibt in der Änderungshistorie erhalten.','The original version is retained in the revision history.'),
          fields:[value('title',tr('Titel','Title'),selectedRecord.title),value('note',tr('Notiz','Note'),selectedRecord.note)],
          actions:[row('record-save-edit',tr('Korrektur speichern','Save correction')),row('patient-section:records',tr('Abbrechen','Cancel'))]}));
      }
      if(id==='record-save-edit'&&selectedRecord?.editable&&patient){
        await command('book/record-edit/',{customer_id:patient.patient.id,record_id:selectedRecord.id,revision:selectedRecord.revision,title:fields.title,note:fields.note});
        patientSection='records';return await showPatient(patient.patient.id,{reset:false});
      }
      if(id.startsWith('record:'))return await showPDF('book/patient/'+patient.patient.id+'/records/'+id.slice(7)+'/',tr('Patientendokument','Patient document'),true);
      if(admin&&id.startsWith('invoice-pdf:'))return await showPDF('office/pdf/'+Number(id.slice(12))+'/',tr('GOÄ Entwurf','GOÄ draft'));
      if(id==='edit-appointment')return await appendForm(true);
      if(id==='save-new'||id==='save-edit'){
        if(id==='save-new'&&(!fields.customer_id||!fields.service_id||!fields.staff_id))throw new Error(tr('Bitte Dienstleistung, Dienstleister und Patienten auswählen.','Choose a service, provider and client.'));
        const payload={operation:id==='save-new'?'create':'update',...fields};
        if(id==='save-edit'&&appointment.source_managed){
          if(!admin||!appointment.source_editable)
            throw new Error(tr('Dieser SimplyBook-Termin ist schreibgeschützt.','This SimplyBook appointment is read-only.'));
          // The source identity is immutable; only date/start are offered to staff.
          payload.customer_id=appointment.customer_id;
          payload.staff_id=appointment.staff_id;
          payload.service_id=appointment.service_id;
        }
        if(id==='save-edit') for(const k of ['customer_id','staff_id','service_id']) if(payload[k]==null || payload[k]==='') payload[k]=appointment[k];
        for(const k of ['customer_id','staff_id','service_id']) { payload[k]=Number(payload[k]); if(!Number.isSafeInteger(payload[k])||payload[k]<=0) throw new Error(tr('Ungültige Buchungsdaten.','Invalid booking data.')); }
        if(id==='save-edit'){payload.id=appointment.id;payload.revision=appointment.revision;payload.status=fields.status||appointment.status;}
        const result=await command('book/appointment/',payload);
        appointmentsById.clear();
        invalidateCalendar();
        date=payload.date;
        if(result.external_confirmation_pending){
          return await render(view(tr('Bestätigung ausstehend','Confirmation pending'),{
            message:tr('Die Terminanfrage wurde gespeichert. SimplyBook prüft und bestätigt die Reservierung.','The request was saved. SimplyBook will verify and confirm the reservation.'),
            actions:[row('calendar',tr('Zurück zum Kalender','Back to calendar'))],
          }));
        }
        return await screen('calendar');
      }
      if(id==='cancel-appointment')return await render(view(tr('Absage bestätigen','Confirm cancellation'),{
        subtitle:appointment.customer_name,actions:[row('confirm-cancel',tr('Termin absagen','Cancel appointment'))]}));
      if(id==='confirm-cancel'){await command('book/appointment/',{operation:'cancel',id:appointment.id,revision:appointment.revision});appointmentsById.clear();invalidateCalendar();return await screen('calendar');}
      if(['upload-pdf','upload-photo','take-photo'].includes(id))return await upload(id,event);
      if(id==='note')return await render(view(tr('Neue Notiz','New note'),{fields:[value('title',tr('Titel','Title')),value('note',tr('Notiz','Note'))],actions:[row('save-note',tr('Speichern','Save'))]}));
      if(id==='save-note'){await command('book/record-note/',{customer_id:patient.patient.id,...fields});patientSection='records';recordPage=1;return await showPatient(patient.patient.id,{reset:false});}
      if(admin && id.startsWith('review:')){
        const [,left,right]=id.split(':').map(Number), list=await book('identity-review/');
        reviewPair=list.items.find(x=>x.left.id===left&&x.right.id===right);
        if(!reviewPair)throw new Error(tr('Prüfung nicht verfügbar','Review unavailable'));
        return await render(view(tr('Identität prüfen','Verify identity'),{message:reviewPair.reason,rows:[
          row('',reviewPair.left.name,[reviewPair.left.email,reviewPair.left.phone,reviewPair.left.date_of_birth].filter(Boolean).join(' · ')),
          row('',reviewPair.right.name,[reviewPair.right.email,reviewPair.right.phone,reviewPair.right.date_of_birth].filter(Boolean).join(' · ')),
        ],fields:[value('primary_id',tr('Hauptakte','Primary identity'),reviewPair.left.id,[option(reviewPair.left.id,reviewPair.left.name),option(reviewPair.right.id,reviewPair.right.name)]),
          value('confirm',tr('Identität persönlich geprüft?','Identity verified in person?'),'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))])],
          actions:[row('review-approve',tr('Bestätigen','Approve')),row('review-reject',tr('Nicht identisch','Not the same person'))]}));
      }
      if(id==='review-approve'||id==='review-reject'){
        if(!admin||!reviewPair)return;
        const approve=id==='review-approve';
        if(approve&&fields.confirm!=='yes')throw new Error(tr('Identität bestätigen.','Confirm identity.'));
        await book('identity-review/',{left_id:reviewPair.left.id,right_id:reviewPair.right.id,primary_id:Number(fields.primary_id),
          action:approve?'approve':'reject',confirmed_same_patient:approve?'on':'',fingerprint:reviewPair.fingerprint});
        return await screen('identity-review');
      }
      if(admin&&id.startsWith('intake:')){
        const result=await office('intake-reviews/');intakeRecord=result.items.find(x=>x.id===Number(id.split(':')[1]));
        if(!intakeRecord)throw new Error(tr('Aufnahme nicht verfügbar','Intake unavailable'));
        const d=intakeRecord.submission, list=await office('customers/?q='+encodeURIComponent(d.first_name));
        return await render(view(tr('Aufnahme prüfen','Review intake'),{rows:[row('',d.first_name+' '+d.last_name,[d.email,d.phone,d.date_of_birth].filter(Boolean).join(' · '))],
          fields:[value('customer_id',tr('Bestehendes Konto','Existing account'),list.items[0]?.id,list.items.map(x=>option(x.id,x.name+' · '+x.email))),
            value('confirm',tr('Identität geprüft?','Identity verified?'),'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))])],
          actions:[row('intake-approve',tr('Bestätigen','Approve')),row('intake-reject',tr('Ablehnen','Reject'))]}));
      }
      if(admin&&['intake-approve','intake-reject'].includes(id)){
        const yes=id==='intake-approve';if(yes&&fields.confirm!=='yes')throw new Error(tr('Identität bestätigen.','Confirm identity.'));
        await office('intake-review/'+intakeRecord.id+'/',{decision:yes?'approve':'reject',customer_id:Number(fields.customer_id),confirmed_same_patient:yes});
        return await screen('intake-reviews');
      }
      if(admin&&id.startsWith('billing:'))return await showBilling(Number(id.split(':')[1]));
      if(admin&&id==='link-search'){
        const list=await book('patients/?q='+encodeURIComponent(billingUser.name.split(' ')[0]));
        return await render(view(tr('Book Identität prüfen','Verify Book identity'),{
          fields:[value('book_customer_id',tr('Book Patient','Book patient'),list.items[0]?.id,list.items.map(x=>option(x.id,x.name+' · '+x.email))),
            value('confirm',tr('Identität persönlich geprüft?','Identity verified in person?'),'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))])],
          actions:[row('save-link',tr('Verknüpfen','Link'))]}));
      }
      if(admin&&id==='save-link'){
        if(fields.confirm!=='yes')throw new Error(tr('Identität bestätigen.','Confirm identity.'));
        await office('link/',{customer_id:billingUser.id,book_customer_id:Number(fields.book_customer_id),confirmed_same_patient:true});
        return await showBilling(billingUser.id);
      }
      if(admin&&id==='invoice-form')return await invoiceForm();
      if(admin&&id.startsWith('invoice-detail:'))return await invoiceDetail(Number(id.split(':')[1]));
      if(admin&&id==='invoice-edit'){
        editingInvoice=selectedInvoice.invoice;const draft=selectedInvoice.draft;
        const result=await book('patient/'+billingUser.book_customer_id+'/');
        billingVisits=result.appointments.filter(a=>a.public_id===editingInvoice.book_appointment_public_id);
        if(!billingVisits.length)throw new Error(tr('Besuch nicht verfügbar','Visit unavailable'));
        invoiceLines=draft.lines;invoiceMeta={visit_id:draft.visit_id,service_date:draft.service_date===selectedInvoice.original_date?'':draft.service_date,date_correction_reason:draft.date_correction_reason,treatment:draft.treatment||'',...draft.address};
        return await invoiceForm(false);
      }
      if(admin&&id==='invoice-simulate')return await render(view(tr('Testrechnung bestätigen','Confirm test invoice'),{message:tr('Nur synthetische QA-Rechnung, nicht zur Zahlung.','Synthetic QA invoice only, not for payment.'),actions:[row('confirm-simulation',tr('Testrechnung nummerieren','Number test invoice'))]}));
      if(admin&&id==='confirm-simulation'){
        await office('issue-simulation/'+selectedInvoice.invoice.id+'/',{revision:selectedInvoice.invoice.revision,confirmed_synthetic:true});
        return await invoiceDetail(selectedInvoice.invoice.id);
      }
      if(admin&&id==='reference-case'){
        invoiceMeta={...fields};const sample=await office('reference-case/');const money=cents=>(cents/100).toFixed(2)+' EUR';
        return await render(view(tr('Synthetische Referenz','Synthetic reference'),{message:tr('Nur Rechenvergleich. Der Zielfaktor ist keine ärztliche Freigabe.','Arithmetic comparison only. The target-derived factor is not physician approval.'),rows:[row('',tr('Zielbetrag','Target amount'),money(sample.target_cents)),row('',tr('Ärztliche Leistungen','Medical fees'),money(sample.medical_cents)),row('',tr('Auslagen','Expenses'),money(sample.material_cents)),row('',tr('Abgeleiteter Referenzfaktor','Derived reference factor'),sample.derived_factor)],actions:[row('invoice-return',tr('Zum Entwurf','Return to draft'))]}));
      }
      if(admin&&id==='add-invoice-line'){invoiceMeta={...fields};return await lineForm(invoiceLines.length);}
      if(admin&&id==='add-manual-line'){invoiceMeta={...fields};return await lineForm(invoiceLines.length,false,true);}
      if(admin&&id==='add-material-line'){invoiceMeta={...fields};return await lineForm(invoiceLines.length,true);}
      if(admin&&id.startsWith('invoice-line:')){invoiceMeta={...fields};return await lineForm(Number(id.split(':')[1]));}
      if(admin&&id.startsWith('save-material:')){const idx=Number(id.split(':')[1]);const material={...fields,kind:'material',material_eligible:fields.material_eligible==='yes'};await office('quote/',{lines:[material]});invoiceLines[idx]=material;return await invoiceForm(false);}
      if(admin&&id.startsWith('save-verified-line:')){
        const idx=Number(id.split(':')[1]);
        const data={...fields,tariff_source:'official_catalog',clinical_confirmed:fields.clinical_confirmed==='yes',
          analog:fields.analog==='yes',analog_confirmed:fields.analog_confirmed==='yes'};
        const result=await office('quote/',{lines:[data]});
        invoiceLines[idx]={...data,goae_description:data.analog?data.goae_description:result.items[0].description};
        return await invoiceForm(false);
      }
      if(admin&&id.startsWith('save-line:')){
        const idx=Number(id.split(':')[1]);
        await office('quote/',{lines:[fields]});
        invoiceLines[idx]=fields;return await invoiceForm(false);
      }
      if(admin&&id.startsWith('delete-line:')){invoiceLines.splice(Number(id.split(':')[1]),1);return await invoiceForm(false);}
      if(admin&&id==='invoice-quote'){invoiceMeta={...fields};return await quote();}
      if(admin&&id==='invoice-return')return await invoiceForm(false);
      if(admin&&id==='save-invoice'){
        const {street,postal_code,city,visit_id,service_date,date_correction_reason,treatment}=invoiceMeta;
        const body={customer_id:billingUser.id,visit_id,address:{street,postal_code,city},service_date,date_correction_reason,treatment,save_missing_address:true,lines:invoiceLines};
        if(editingInvoice){await office('edit-draft/'+editingInvoice.id+'/',{...body,revision:editingInvoice.revision});editingInvoice=null;}
        else await command('office/draft/',body,'request_id');
        return await showBilling(billingUser.id);
      }
    } catch(err) {
      if(!active)return;
      if(err.status===401){await destroy();logout();return;}
      if(restoring)throw err;
      if(origin.location)applyRoute(origin.location);
      ({patient,appointment,currentBlock,currentService,selectedRecord,currentPatientAccount}=origin.models);
      calendarScreen=origin.calendarScreen;
      location=origin.location;
      current={...origin.screen,message:err.message||tr('Bitte erneut versuchen.','Please try again.')};
      await plugin.render({screen:current,calendar:calendarScreen});
    } finally {
      transition=previousTransition;
      busy=wasBusy;
      if(!busy && active){
        if(current.screenKey===origin.screen.screenKey)current=snapshot(event).screen;
        checkpoint();
        if(queuedRoute){const route=queuedRoute;queuedRoute=null;void handle({id:route});}
      }
    }
  }
  let presented = false;
  let initialSnapshot;
  const openInitial=async()=>{
    if(initialPatient)await showPatient(initialPatient);
    else if(initialCalendar)await screen('calendar');
    else if(!await restoreRoute(initialSnapshot))await screen('home');
    if(initialSnapshot && !initialPatient && !initialCalendar)
      history.splice(0,history.length,...(initialSnapshot.history||[]).map(location=>({location})));
    initialSnapshot=null;
  };
  function destroy(){
    if(closing)return closing;
    active=false;
    requests.abort();
    signal?.removeEventListener('abort',cancel);
    queuedRoute=null;
    history.length=0;
    initialSnapshot=null;
    location=null;
    current={};
    calendarScreen=null;
    patient=null;
    selectedRecord=null;
    appointment=null;
    currentPatientAccount=null;
    currentBlock=null;
    submission=null;
    billingUser=null;
    billingVisits=null;
    selectedInvoice=null;
    invoiceMeta={};
    invoiceLines=[];
    transition=null;
    appointmentsById.clear();
    pendingCommands.clear();
    blockById.clear();
    calendarCache.clear();
    closing=(async()=>{
      try { await listener?.remove(); }
      finally { if(presented)await plugin.dismiss(); }
    })();
    return closing;
  }
  function cancel(){
    requests.abort();
    if(presented)void destroy().catch(()=>{});
  }
  try {
    signal?.throwIfAborted();
    signal?.addEventListener('abort',cancel,{once:true});
    initialSnapshot=await navigation?.read('staff');
    requests.signal.throwIfAborted();
    listener = await plugin.addListener('action',event=>void handle(event));
    requests.signal.throwIfAborted();
    await plugin.present({screen:current});
    presented = true;
    requests.signal.throwIfAborted();
    // Failure of the first data API must never tear down a successfully
    // presented native interface and trap the user in the WebView login boot.
    try {
      await openInitial();
      checkpoint();
    } catch(error) {
      if(!active || requests.signal.aborted)throw error;
      if(error.status===401){
        await destroy();
        logout();
        return {destroy:async()=>{},openPatient:()=>{},openCalendar:()=>{},back:()=>false};
      }
      await render(view(tr('Verbindung unterbrochen','Connection interrupted'),{
        message:tr('Die Praxisdaten sind vorübergehend nicht erreichbar.','Practice data is temporarily unavailable.')+
          (error.status?' (HTTP '+error.status+')':''),
        actions:[row('retry-initial',tr('Erneut versuchen','Try again')),row('logout',tr('Abmelden','Sign out'))],
      }));
      location=null;
    }
  } catch(error) {
    try { await destroy(); }
    catch (_) { /* Preserve the original initialization failure. */ }
    throw error;
  } finally {
    busy=false;
  }
  function open(route){
    if(!active)return;
    if(busy)queuedRoute=route;
    else void handle({id:route});
  }
  return {destroy,openPatient:id=>open('patient:'+id),openCalendar:()=>open('calendar'),back:()=>{void handle({id:'back'});return active;}};
}
