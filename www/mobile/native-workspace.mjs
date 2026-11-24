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
  id,label:dateFields.has(id)&&!options?label.replace(/\s*\((?:JJJJ-MM-TT|YYYY-MM-DD)\)/,'')+' · TT.MM.JJJJ':label,value:dateFields.has(id)&&!options?germanDate(initial):String(initial ?? ''),kind:options?'select':inputKind(id),
  ...(options ? {options} : {}),
});
const row = (id,label,detail='') => ({id,label:germanDate(label),detail:germanDate(detail)});
const option = (value,label) => ({value:String(value),label:germanDate(label)});
const dateLabel = (date, locale, options) => new Date(date+'T12:00:00Z').toLocaleDateString('de-DE',{...options,timeZone:'UTC'});
const optionFor = (list) => list.map(x=>option(x.id,x.name));
const sourceOfBlock = block => block?.source_managed || /\u2063[\u200b\u200c]+\u2063/.test(block?.text||'')
  ? 'SimplyBook' : 'Book';
const isSyncedProvider = p => Boolean(p?.source_managed || String(p?.name||'').startsWith('A+ Esthetic (SimplyBook #'));
const isSyncedService = s => Boolean(s?.source_managed || String(s?.slug||'').startsWith('simplybook-event-'));
const uuid = () => globalThis.crypto.randomUUID();

export async function mountNativeWorkspace({token, identity, origin, logout, initialPatient, initialCalendar}) {
  const plugin = globalThis.APlusNativeStaff || globalThis.Capacitor?.Plugins?.NativeStaff;
  if (!plugin) throw new Error('Native staff renderer unavailable');
  const admin = identity.role === 'admin';
  let language = localStorage.getItem('aplus_language') === 'en' ? 'en' : 'de';
  const tr = (de,en) => language === 'en' ? en : de;
  let locale = language === 'en' ? 'en-GB' : 'de-DE';
  const stack = [];
  const appointmentsById = new Map();
  const rememberAppointments = items => { for(const a of items||[]) appointmentsById.set(a.id,a); };
  let date = today(), search = '', calendarMode='day', providerFilter='all', serviceFilter='all', active = true, busy = false, listener, patient, catalog, appointment;
  let activeTab = 'home';
  let patientPage=1, recordPage=1, patientSection='overview', intakeSearch='', intakeStatus='', intakePage=1, intakeFrom='', intakeTo='', submission, canonicalForms=true;
  let current = {title:'A+ Esthetic',busy:true,tabs:[]};
  const blockById = new Map();
  const calendarCache = new Map();
  const calendarInFlight = new Map();
  let prefetchBusy = false;
  function getCalendarWeek(day) {
    const key=startWeek(day);
    const cached=calendarCache.get(key);
    if(cached && Date.now()-cached.at<45000)return Promise.resolve(cached.data);
    if(calendarInFlight.has(key))return calendarInFlight.get(key);
    const pending=book('calendar/?start='+key+'&days=7').then(data=>{
      calendarCache.set(key,{at:Date.now(),data});
      if(calendarCache.size>6)calendarCache.delete(calendarCache.keys().next().value);
      return data;
    }).finally(()=>calendarInFlight.delete(key));
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
    ...(admin ? [{...row('office','Office'),icon:'doc.text'}] : []),
    {...row('settings',tr('Einstellungen','Settings')),icon:'gearshape'},
  ];
  async function request(path, data, prefix='/api/mobile/staff/') {
    const response = await fetch(origin+prefix+path,{
      method:data ? 'POST':'GET', headers:{Authorization:'Bearer '+token,Accept:'application/json','Content-Type':'application/json'},
      cache:'no-store', ...(data?{body:JSON.stringify(data)}:{}),
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
    ...(content.subtitle?{subtitle:germanDate(content.subtitle)}:{}),
    ...Object.fromEntries(['rows','secondaryRows'].filter(key=>content[key]).map(key=>[key,content[key].map(item=>({...item,...(item.badge?{badge:localizedStatus(item.badge)}:{})}))]))});
  async function render(screen) { if(!active)return; current=screen; await plugin.render({screen}); }
  async function screen(name, {push=true}={}) {
    if(['home','calendar','patients','office','settings'].includes(name))activeTab=name;
    if(push && stack.at(-1)!==name)stack.push(name);
    if(name==='home'){
      const r=await book('overview/');
      rememberAppointments(r.upcoming);
      const upcoming=r.upcoming||[];
      return render(view(tr('Willkommen','Welcome'),{hero:tr('Praxisübersicht','Practice overview'),subtitle:identity.name+' · '+dateLabel(today(),locale,{weekday:'long',day:'numeric',month:'long'}),
        metrics:[row('calendar',tr('Termine heute','Appointments today'),String(r.today)),
          row('calendar',r.upcoming_count==null?tr('Nächste Termine (Auszug)','Next appointments (shown)'):tr('Bevorstehend','Upcoming'),String(r.upcoming_count??upcoming.length)),
          ...(r.patient_count==null?[]:[row('patients',tr('Kontaktprofile','Contact profiles'),String(r.patient_count))]),
          ...(r.provider_count==null?[]:[row('calendar',tr('Behandler','Providers'),String(r.provider_count))]),
          ...(admin&&r.intake_review_count!=null?[row('intakes',tr('Formulare zu prüfen','Forms to review'),String(r.intake_review_count))]:[])],
        shortcuts:[row('calendar',tr('Kalender','Calendar')),row('patients',tr('Patientenakten','Patient records')),
          ...(admin?[row('intakes',tr('Eingereichte Formulare','Submitted forms')),row('billing-search',tr('GOÄ Rechnung','GOÄ invoice'))]:[])],
        sectionTitle:tr('NÄCHSTE TERMINE','NEXT APPOINTMENTS'),
        rows:upcoming.map(a=>({...row('appointment:'+a.id,a.customer_name,[a.date,a.start,a.service_name,a.staff_name].filter(Boolean).join(' · ')),badge:a.status||''})),
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
          value('service_filter',tr('Behandlung','Service'),serviceFilter,[option('all',tr('Alle','All')),...optionFor(catalog.services.filter(x=>x.active))]),
        ],
        rows:[...found.map(a=>row('appointment:'+a.id,(calendarMode==='week'?a.date+' · ':'')+a.start+' · '+a.customer_name,a.service_name+' · '+a.staff_name)),
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
        ...(admin?[row('services',tr('Behandlungskatalog','Treatment catalog'))]:[]),
        row('language',tr('Sprache','Language')),
      ],actions:[row('logout',tr('Abmelden','Sign out'))]}));
    }
    if(name==='services'&&admin){
      catalog=await book('catalog/');
      return render(view(tr('Behandlungen','Treatments'),{rows:catalog.services.map(s=>row('service:'+s.id,s.name,
        String(s.duration_minutes)+' min · '+String(s.buffer_minutes)+' min '+tr('Puffer','buffer')+
        (isSyncedService(s)?' · SimplyBook':'')))}));
    }
    if(name==='office' && admin){
      return render(view('Office',{subtitle:tr('Formulare und private Abrechnung','Forms and private billing'),rows:[
        row('intakes',tr('Eingereichte Formulare','Submitted forms'),tr('Anamnese · Unterschrift · Zuordnung','Medical history · Signature · Identity')),
        row('billing-search',tr('GOÄ Rechnungserstellung','GOÄ invoicing'),tr('Rechner · Entwürfe · PDF','Calculator · Drafts · PDF')),
      ]}));
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

  async function showPatient(id,{reset=true}={}) {
    activeTab='patients';
    if(reset){patientSection='overview';recordPage=1;currentPatientAccount=null;selectedRecord=null;}
    patient=await book('patient/'+id+'/?page='+recordPage);
    rememberAppointments(patient.appointments);
    if(stack.at(-1)!=='patient:'+id)stack.push('patient:'+id);
    return renderPatient();
  }
  async function renderPatient(){
    const p=patient.patient;
    const sections=[['overview',tr('Übersicht','Overview')],['appointments',tr('Termine','Appointments')],['records',tr('Patientenakte','Records')],['contact',tr('Kontakt','Contact')],
      ...(admin?[['account',tr('Kundenkonto','Customer account')]]:[])];
    const appointments=patient.appointments||[], records=patient.records||[];
    const timeline=appointments.map(a=>({...row('appointment:'+a.id,a.date+' · '+a.start,[a.service_name,a.staff_name].filter(Boolean).join(' · ')),badge:a.status}));
    const recordRows=records.map(r=>({...row('record-detail:'+r.id,r.title,[r.date?.slice(0,10),r.note,r.filename].filter(Boolean).join(' · ')),badge:r.kind||''}));
    let accountContent={};
    if(patientSection==='account'&&admin){
      const linked=await office('patient-account/'+p.id+'/');
      if(!linked.customer_id){
        currentPatientAccount=null;
        accountContent={message:tr('Das A+ Kundenkonto ist noch nicht eindeutig mit der Patientenakte verknüpft.','The A+ customer account is not yet linked to this patient record.'),
          actions:[row('patient-link-account',tr('Konto suchen und Identität prüfen','Find account and verify identity'))]};
      }else{
        const detail=await request('customers/'+linked.customer_id+'/',undefined,'/api/mobile/admin/');
        const list=await office('invoices/'+linked.customer_id+'/');
        currentPatientAccount=detail.customer;
        accountContent={
          metrics:[row('',tr('A+ Punkte','A+ points'),String(detail.customer.coins)),row('',tr('Guthaben','Credit'),(detail.customer.credit_cents/100).toFixed(2)+' EUR')],
          shortcuts:[row('patient-adjust-points',tr('Punkte korrigieren','Adjust points')),row('patient-wallet-history',tr('Wallet-Verlauf','Wallet history'))],
          sectionTitle:tr('PAKETE','PACKAGES'),
          rows:(detail.packages||[]).map(x=>({...row('',x.name,String(x.remaining_sessions)+' '+tr('Sitzungen · bis','sessions · until')+' '+x.expires_at),badge:x.status})),
          empty:tr('Keine Pakete.','No packages.'),
          secondaryTitle:tr('GOÄ RECHNUNGEN','GOÄ INVOICES'),
          secondaryRows:(list.items||[]).map(x=>row(x.status==='draft'?'invoice-pdf:'+x.id:'',(x.number||tr('Entwurf','Draft'))+' · '+x.service_date,(x.total_cents/100).toFixed(2)+' EUR · '+x.status)),
        };
      }
    }
    return render(view(p.name,{hero:p.name,heroLabel:tr('PATIENTENAKTE','PATIENT RECORD'),subtitle:[p.email,p.phone].filter(Boolean).join(' · '),
      segments:sections.map(([id,label])=>({...row('patient-section:'+id,label),selected:patientSection===id})),
      ...(patientSection==='overview'?{metrics:[row('patient-section:appointments',tr('Termine (Auszug)','Appointments (shown)'),String(appointments.length)),row('patient-section:records',tr('Akteneinträge (Auszug)','Records (shown)'),String(records.length))],
        shortcuts:[row('new-patient-appointment',tr('Termin hinzufügen','Book appointment')),row('note',tr('Notiz hinzufügen','Add note')),row('upload-pdf',tr('PDF hinzufügen','Add PDF'))],
        sectionTitle:tr('LETZTE TERMINE','RECENT APPOINTMENTS'),rows:timeline.slice(0,3),empty:tr('Keine Termine.','No appointments.')}:
      patientSection==='appointments'?{rows:timeline,empty:tr('Keine Termine.','No appointments.'),actions:[row('new-patient-appointment',tr('Termin hinzufügen','Book appointment'))]}:
      patientSection==='records'?{sectionTitle:tr('DIGITALE AKTE','DIGITAL RECORD')+' · '+tr('Seite','Page')+' '+recordPage,rows:recordRows,empty:tr('Noch keine Akteneinträge.','No records yet.'),
        shortcuts:[row('note',tr('Notiz hinzufügen','Add note')),row('upload-pdf',tr('PDF hinzufügen','Add PDF')),
          row('take-photo',tr('Kamera','Camera')),row('upload-photo',tr('Foto auswählen','Choose photo'))],
        actions:[...(patient.has_more?[row('record-page-next',tr('Nächste Seite','Next page'))]:[]),...(recordPage>1?[row('record-page-prev',tr('Vorherige Seite','Previous page'))]:[])]}:
      patientSection==='account'?accountContent:
      {rows:[row('',tr('Name','Name'),p.name),row('','E-Mail',p.email||'—'),row('',tr('Telefon','Phone'),p.phone||'—'),
          ...(p.date_of_birth?[row('',tr('Geburtsdatum','Date of birth'),p.date_of_birth)]:[])]})}));
  }
  async function getAppointment(id) {
    if(appointmentsById.has(id))return appointmentsById.get(id);
    const result=await book('appointments/?page=1');
    let item=result.items.find(x=>x.id===id);
    if(!item && patient)item=patient.appointments.find(x=>x.id===id);
    if(!item){
      const r=await book('calendar/?start='+startWeek(date)+'&days=7');item=r.appointments.find(x=>x.id===id);
    }
    if(!item)throw new Error(tr('Termin nicht verfügbar.','Appointment unavailable.'));
    return item;
  }
  async function showAppointment(id) {
    activeTab='calendar';
    appointment=await getAppointment(id);stack.push('appointment:'+id);
    return render(view(appointment.customer_name,{
      subtitle:appointment.service_name,
      message:appointment.source_managed
        ? (admin&&appointment.source_editable
           ? tr('Mit SimplyBook synchronisiert. Terminzeit oder Stornierung wird zuerst direkt in SimplyBook bestätigt und danach hier gespeichert. Änderungen an Patient, Behandler und Behandlung bitte weiterhin in SimplyBook vornehmen.',
                'Synced with SimplyBook. Time changes and cancellations are confirmed in SimplyBook first, then saved here. Edit patient, provider or treatment in SimplyBook directly.')
           : tr('Dieser Termin wird aus SimplyBook synchronisiert. Bitte die Änderung direkt in der SimplyBook-Verwaltung vornehmen; sie wird danach hier übernommen.',
                'This appointment is synced from SimplyBook. Change it in SimplyBook; the update will appear here.'))
        : '',
      rows:[
        row('',appointment.date+' · '+appointment.start+' – '+appointment.end, appointment.staff_name),
        row('',tr('Status','Status'),appointment.status),row('',tr('Notiz','Note'),appointment.notes||''),
      ],actions:appointment.source_managed && !(admin&&appointment.source_editable)
        ? [row('calendar',tr('Zurück zum Kalender','Back to calendar'))]
        : [row('edit-appointment',tr('Bearbeiten','Edit')),row('cancel-appointment',tr('Absagen','Cancel'))],
    }));
  }
  async function appendForm(edit=false, chosenPatient=null, slot={}) {
    catalog=await book('catalog/');
    const r=await book('patients/?q='+encodeURIComponent(search));
    const options=r.items.map(x=>option(x.id,x.name));
    if(chosenPatient&&!options.some(x=>x.value===String(chosenPatient.id)))options.unshift(option(chosenPatient.id,chosenPatient.name));
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
      value('customer_id',tr('Patient','Patient'),edit?appointment.customer_id:chosenPatient?.id||options[0]?.value,options),
      value('staff_id',tr('Behandler','Provider'),edit?appointment.staff_id:(slot.staff_id && providersForBooking.some(p=>String(p.id)===String(slot.staff_id)) ? slot.staff_id : providersForBooking[0]?.id),optionFor(providersForBooking)),
      value('service_id',tr('Behandlung','Treatment'),edit?appointment.service_id:servicesForBooking[0]?.id,optionFor(servicesForBooking)),
      value('date',tr('Datum (JJJJ-MM-TT)','Date (YYYY-MM-DD)'),edit?appointment.date:(slot.date||date)),
      value('start',tr('Beginn (HH:MM)','Start (HH:MM)'),edit?appointment.start:(slot.start||'10:00')),
      value('notes',tr('Notiz','Notes'),edit?appointment.notes:''),
    ];
    stack.push(edit?'edit-appointment':'new-appointment');
    return render(view(edit?tr('Termin bearbeiten','Edit appointment'):tr('Neuer Termin','New appointment'),
      {fields,actions:[row(edit?'save-edit':'save-new',tr('Speichern','Save'))]}));
  }
  let currentBlock, currentService, pendingUpload, selectedRecord;
  async function blockForm(edit){
    catalog=catalog||await book('catalog/');
    return render(view(edit?tr('Kalendereintrag bearbeiten','Edit calendar entry'):tr('Sperrzeit / Notiz','Block / note'),{fields:[
      value('staff_id',tr('Behandler','Provider'),edit?currentBlock.staff_id:catalog.providers.find(p=>!isSyncedProvider(p))?.id,optionFor(catalog.providers.filter(p=>!isSyncedProvider(p)))),
      value('date',tr('Datum','Date'),edit?currentBlock.date:date),
      value('kind',tr('Art','Type'),edit?currentBlock.kind:'block',[option('block',tr('Sperrzeit','Blocked time')),option('note',tr('Notiz','Note'))]),
      value('start',tr('Beginn','Start'),edit?currentBlock.start:'12:00'),
      value('end',tr('Ende','End'),edit?currentBlock.end:'13:00'),
      value('text',tr('Text','Text'),edit?currentBlock.text:''),
    ],actions:[row(edit?'save-block-edit':'save-block-new',tr('Speichern','Save')),...(edit?[row('remove-block',tr('Eintrag löschen','Delete entry'))]:[])]}));
  }
  async function availabilityForm(id){
    catalog=await book('catalog/');
    const provider=catalog.providers.find(p=>String(p.id)===String(id))||catalog.providers[0];
    if(!provider)throw new Error(tr('Kein Behandler','No provider'));
    const data=await book('calendar/?start='+date+'&days=1');
    const current=data.availability.find(r=>r.staff_id===provider.id&&r.date===date);
    const ranges=current?.ranges||[];
    if(isSyncedProvider(provider)){
      return render(view(tr('Arbeitszeit – SimplyBook','Working hours – SimplyBook'),{
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
    return render(view(tr('Arbeitszeit','Working hours'),{subtitle:date,fields:[
      value('staff_id',tr('Behandler','Provider'),provider.id,optionFor(catalog.providers)),value('date',tr('Datum','Date'),date),
      value('operation',tr('Gültigkeit','Scope'),'daily',[option('daily',tr('Diesen Tag','This day')),option('weekly',tr('Wöchentlich','Weekly')),option('reset',tr('Tagesausnahme zurücksetzen','Reset override'))]),
      value('closed',tr('Geschlossen','Closed'),ranges.length?'no':'yes',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))]),
      value('start_1',tr('Beginn','Start'),ranges[0]?.start||'09:00'),value('end_1',tr('Ende','End'),ranges[0]?.end||'18:00'),
      value('start_2',tr('Zweiter Beginn (optional)','Second start (optional)'),ranges[1]?.start||''),
      value('end_2',tr('Zweites Ende (optional)','Second end (optional)'),ranges[1]?.end||''),
    ],actions:[row('load-availability',tr('Behandler / Datum laden','Load provider / date')),row('save-availability',tr('Speichern','Save'))]}));
  }
  let billingUser, billingVisits, reviewPair, intakeRecord, invoiceLines=[], invoiceMeta={}, editingInvoice=null, selectedInvoice=null, tariffCatalog=null, officeSettingsRevision=null, currentPatientAccount;
  async function showBilling(id) {
    const r=await office('customers/?q='+encodeURIComponent(search));
    billingUser=r.items.find(u=>u.id===id);
    if(!billingUser)throw new Error(tr('Patient nicht verfügbar','Patient unavailable'));
    stack.push('billing:'+id);
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
    const response=await fetch(origin+'/api/mobile/staff/'+path,{headers:{Authorization:'Bearer '+token},cache:'no-store'});
    if(!response.ok)throw new Error(tr('Datei nicht verfügbar','File unavailable'));
    const blob=await response.blob();
    if(blob.size>8000000)throw new Error(tr('Datei zu groß','File too large'));
    const bytes=new Uint8Array(await blob.arrayBuffer());
    let chunk='';for(let i=0;i<bytes.length;i+=16384)chunk+=String.fromCharCode(...bytes.subarray(i,i+16384));
    if(String.fromCharCode(...bytes.slice(0,5))!=='%PDF-'){
      if(allowImage&&((bytes[0]===0xff&&bytes[1]===0xd8)||(bytes[0]===0x89&&String.fromCharCode(...bytes.slice(1,4))==='PNG'))){
        return render(view(title,{image:btoa(chunk),actions:[row('patient-section:records',tr('Zur Patientenakte','Back to patient record'))]}));
      }
      throw new Error(tr('Dieses Dateiformat wird noch nicht unterstützt','This file type is not supported'));
    }
    await plugin.previewPDF({title,base64:btoa(chunk)});
  }
  async function handle(event) {
    if(!active || busy) return;
    const id=event.id, fields={...(event.values||{})};
    busy=true;
    try {
      for(const key of Object.keys(fields).filter(key=>dateFields.has(key))){
        const canonical=canonicalDate(fields[key]);
        if(canonical!==null)fields[key]=canonical;
        else if(/^(save-|load-availability|filter-intakes|invoice-)/.test(id))throw new Error(tr('Bitte ein gültiges Datum im Format TT.MM.JJJJ eingeben.','Enter a valid date in DD.MM.YYYY format.'));
      }
      if(id==='logout'){await destroy();logout();return;}
      if(id==='retry-initial')return await screen('home',{push:false});
      if(id==='back'){
        stack.pop();const back=stack.pop()||'home';
        if(back.startsWith('patient:'))return await showPatient(Number(back.split(':')[1]));
        if(back.startsWith('billing:'))return await showBilling(Number(back.split(':')[1]));
        if(back.startsWith('appointment:'))return await showAppointment(Number(back.split(':')[1]));
        return await screen(['home','calendar','patients','office','intakes','intake-reviews','identity-review','billing-search','billing-settings','settings','services'].includes(back)?back:'home');
      }
      if(['home','calendar','patients','office','intakes','intake-reviews','identity-review','billing-search','billing-settings','settings','services'].includes(id)){
        if(id==='patients'||id==='billing-search')search='';
        if(id==='patients')patientPage=1;
        if(id==='intakes'){intakeSearch='';intakeStatus='';intakePage=1;intakeFrom='';intakeTo='';}
        return await screen(id);
      }
      if(id==='cal-today'){date=today();return await screen('calendar',{push:false});}
      if(id.startsWith('cal-mode:')){
        calendarMode=id.slice('cal-mode:'.length);
        if(!['day','week','provider','service'].includes(calendarMode))return;
        return await screen('calendar',{push:false});
      }
      if(id.startsWith('cal-provider:')){
        providerFilter=id.slice('cal-provider:'.length);
        return await screen('calendar',{push:false});
      }
      if(id.startsWith('cal-service:')){
        serviceFilter=id.slice('cal-service:'.length);
        return await screen('calendar',{push:false});
      }
      if(id.startsWith('slot:')){
        const parts=id.split(':');
        const day=parts[1],time=parts[2]+':'+parts[3];
        if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!/^\d{2}:\d{2}$/.test(time))return;
        date=day;
        search='';
        return await appendForm(false,null,{date:day,start:time,staff_id:parts[4]||providerFilter});
      }
      if(id==='week-next'||id==='week-prev'){date=shiftDay(date,id==='week-next'?7:-7);return await screen('calendar',{push:false});}
      if(id==='day-next'||id==='day-prev'){
        // Swipe the appointment body by a day, or by a week in weekly mode.
        const delta=calendarMode==='week'?7:1;
        date=shiftDay(date,id==='day-next'?delta:-delta);
        return await screen('calendar',{push:false});
      }
      if(id.startsWith('date:')){date=id.slice(5);return await screen('calendar',{push:false});}
      if(id==='search'||id==='billing-query'){search=fields.query||'';patientPage=1;return await screen(id==='search'?'patients':'billing-search',{push:false});}
      if(id==='patient-page-next'||id==='patient-page-prev'){patientPage=Math.max(1,patientPage+(id.endsWith('next')?1:-1));return await screen('patients',{push:false});}
      if(id.startsWith('patient-section:')&&patient){patientSection=id.slice('patient-section:'.length);return await renderPatient();}
      if(admin&&id==='patient-link-account'&&patient){search=patient.patient.name||'';return await screen('billing-search');}
      if(admin&&id==='patient-adjust-points'&&currentPatientAccount){
        return await render(view(tr('Punkte korrigieren','Adjust points'),{subtitle:currentPatientAccount.name,
          fields:[value('coin_delta',tr('Änderung (+/- Punkte)','Adjustment (+/- points)')),value('confirm',tr('Konto und Änderung geprüft?','Account and adjustment checked?'),'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))])],
          actions:[row('patient-save-points',tr('Korrektur bestätigen','Confirm adjustment')),row('patient-section:account',tr('Abbrechen','Cancel'))]}));
      }
      if(admin&&id==='patient-save-points'&&currentPatientAccount){
        const delta=Number(fields.coin_delta);
        if(fields.confirm!=='yes'||!Number.isInteger(delta)||delta===0||Math.abs(delta)>100000)throw new Error(tr('Gültige Änderung bestätigen.','Confirm a valid adjustment.'));
        await command('points/'+currentPatientAccount.id+'/',{coin_delta:delta});
        return await renderPatient();
      }
      if(admin&&id==='patient-wallet-history'&&currentPatientAccount){
        const result=await request('customers/'+currentPatientAccount.id+'/wallet-history/',undefined,'/api/mobile/admin/');
        return await render(view(tr('Wallet-Verlauf','Wallet history'),{subtitle:currentPatientAccount.name,
          rows:(result.transactions||[]).map(x=>row('',x.description||x.kind_label,[x.created_at?.slice(0,10),x.direction_label,x.coin_amount?String(x.coin_amount)+' '+tr('Punkte','points'):(x.amount_cents/100).toFixed(2)+' EUR'].filter(Boolean).join(' · '))),
          empty:tr('Keine Transaktionen.','No transactions.'),actions:[row('patient-section:account',tr('Zurück zum Konto','Back to account'))]}));
      }
      if((id==='record-page-next'||id==='record-page-prev')&&patient){recordPage=Math.max(1,recordPage+(id.endsWith('next')?1:-1));return await showPatient(patient.patient.id,{reset:false});}
      if(admin&&id==='filter-intakes'){intakeSearch=fields.query||'';intakeStatus=fields.status||'';intakeFrom=fields.from||'';intakeTo=fields.to||'';intakePage=1;return await screen('intakes',{push:false});}
      if(admin&&(id==='intake-next'||id==='intake-prev')){intakePage=Math.max(1,intakePage+(id.endsWith('next')?1:-1));return await screen('intakes',{push:false});}
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
        return await screen('intakes',{push:false});
      }
      if(admin&&id==='save-billing-settings'){
        // Optimistic revision protects concurrent edits made in the original Office admin.
        await office('invoice-settings/',{...fields,next_sequence:Number(fields.next_sequence),
          revision:officeSettingsRevision,confirmed_financial_update:true});
        return await screen('billing-settings',{push:false});
      }
      if(id.startsWith('patient:'))return await showPatient(Number(id.split(':')[1]));
      if(id.startsWith('appointment:'))return await showAppointment(Number(id.split(':')[1]));
      if(id==='apply-calendar-filter'){
        calendarMode=fields.calendar_mode;providerFilter=fields.provider_filter;serviceFilter=fields.service_filter;
        return await screen('calendar',{push:false});
      }
      if(id==='new-block')return await blockForm(false);
      if(id.startsWith('block:')||id.startsWith('block-info:')){
        currentBlock=blockById.get(Number(id.split(':').at(-1)));
        if(!currentBlock)return await screen('calendar',{push:false});
        if(currentBlock.editable && id.startsWith('block:'))return await blockForm(true);
        const owner=sourceOfBlock(currentBlock);
        const viaSimplyBook=owner==='SimplyBook';
        return await render(view(tr('Kalendereintrag','Calendar entry'),{
          subtitle:currentBlock.date+' · '+currentBlock.start+' – '+currentBlock.end,
          message:viaSimplyBook
            ?tr('Dieser Eintrag wird aus SimplyBook synchronisiert und kann deshalb nicht hier geändert werden. Bitte Sperrzeit oder Notiz direkt in der SimplyBook-Verwaltung bearbeiten. Die Änderung erscheint nach der nächsten Synchronisierung.',
                'This entry is synced from SimplyBook and cannot be edited here. Change the blocked time or note in SimplyBook administration. It will appear after the next sync.')
            :tr('Dieser Eintrag wird in der Book-Verwaltung verwaltet und ist in der App schreibgeschützt. Bitte Änderungen dort vornehmen.',
                'This entry is managed in Book administration and is read-only in the app. Make changes there.'),
          rows:[row('',tr('Verwaltet in','Managed in'),owner),
            row('',tr('Eintrag','Entry'),(currentBlock.text||'').split('\u2063')[0]),
            row('',tr('Behandler','Provider'),(catalog?.providers||[]).find(p=>p.id===currentBlock.staff_id)?.name||'')],
          actions:[row('calendar',tr('Zurück zum Kalender','Back to calendar'))],
        }));
      }
      if(['save-block-new','save-block-edit','remove-block'].includes(id)){
        if(id==='remove-block'){
          await command('book/block/',{operation:'delete',staff_id:currentBlock.staff_id,id:currentBlock.id});
        } else {
          await command('book/block/',{...fields,staff_id:Number(fields.staff_id),operation:id==='save-block-new'?'create':'update',...(id==='save-block-edit'?{id:currentBlock.id}:{})});
        }
        calendarCache.clear();
        return await screen('calendar');
      }
      if(id==='availability')return await availabilityForm();
      if(id==='load-availability'){date=fields.date||date;return await availabilityForm(fields.staff_id);}
      if(id==='save-availability'){await command('book/availability/',{...fields,staff_id:Number(fields.staff_id),closed:fields.closed==='yes'});calendarCache.clear();date=fields.date;return await screen('calendar');}
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
      if(id==='language')return await render(view(tr('Sprache','Language'),{message:tr('Sprachwechsel wird beim nächsten Öffnen angewendet.','Language applies when reopening.'),fields:[value('language',tr('Sprache','Language'),language,[option('de','Deutsch'),option('en','English')])],actions:[row('save-language',tr('Speichern','Save'))]}));
      if(id==='save-language'){
        if(!['de','en'].includes(fields.language))throw new Error(tr('Ungültige Sprache.','Invalid language.'));
        language=fields.language;
        locale=language==='en'?'en-GB':'de-DE';
        localStorage.setItem('aplus_language',language);
        // Keep navigation and screen labels in sync without an app restart.
        return await screen('settings',{push:false});
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
        const payload={operation:id==='save-new'?'create':'update',...fields};
        if(id==='save-edit'&&appointment.source_managed){
          if(!admin||!appointment.source_editable)
            throw new Error(tr('Dieser SimplyBook-Termin ist schreibgeschützt.','This SimplyBook appointment is read-only.'));
          // The source identity is immutable; only date/start are offered to staff.
          payload.customer_id=appointment.customer_id;
          payload.staff_id=appointment.staff_id;
          payload.service_id=appointment.service_id;
        }
        for(const k of ['customer_id','staff_id','service_id'])payload[k]=Number(payload[k]);
        if(id==='save-edit'){payload.id=appointment.id;payload.revision=appointment.revision;payload.status=appointment.status;}
        await command('book/appointment/',payload);appointmentsById.clear();calendarCache.clear();return await screen('calendar');
      }
      if(id==='cancel-appointment')return await render(view(tr('Absage bestätigen','Confirm cancellation'),{
        subtitle:appointment.customer_name,actions:[row('confirm-cancel',tr('Termin absagen','Cancel appointment'))]}));
      if(id==='confirm-cancel'){await command('book/appointment/',{operation:'cancel',id:appointment.id,revision:appointment.revision});appointmentsById.clear();return await screen('calendar');}
      if(['upload-pdf','upload-photo','take-photo'].includes(id)){
        const chosen=await (id==='upload-pdf'?plugin.pickPDF():id==='take-photo'?plugin.takePhoto():plugin.pickPhoto());
        if(chosen.cancelled)return;
        // Never upload until the clinician confirms the exact patient and file.
        pendingUpload={...chosen,customer_id:patient.patient.id};
        return await render(view(tr('Datei hinzufügen','Add document'),{subtitle:patient.patient.name,
          rows:[row('',chosen.filename,tr('Privater Akteneintrag','Private clinical record'))],
          actions:[row('confirm-upload',tr('Datei hochladen','Upload file')),row('discard-upload',tr('Abbrechen','Cancel'))]}));
      }
      if(id==='discard-upload'){pendingUpload=null;return await showPatient(patient.patient.id);}
      if(id==='confirm-upload'){
        if(!pendingUpload||pendingUpload.customer_id!==patient.patient.id)throw new Error(tr('Patient erneut auswählen.','Select the patient again.'));
        await command('book/record-upload/',{customer_id:pendingUpload.customer_id,filename:pendingUpload.filename,base64:pendingUpload.base64});
        pendingUpload=null;patientSection='records';return await showPatient(patient.patient.id,{reset:false});
      }
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
        return await screen('identity-review',{push:false});
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
      if(err.status===401){await destroy();logout();return;}
      await render({...current,message:err.message||tr('Bitte erneut versuchen.','Please try again.'),fields:(current.fields||[]).map(f=>({...f,value:fields[f.id]??f.value}))});
    } finally {busy=false;}
  }
  async function destroy(){if(!active)return;active=false;pendingUpload=null;appointmentsById.clear();pendingCommands.clear();blockById.clear();calendarCache.clear();await listener?.remove();await plugin.dismiss();}
  let presented = false;
  try {
    listener = await plugin.addListener('action',event=>void handle(event));
    await plugin.present({screen:current});
    presented = true;
    // Failure of the first data API must never tear down a successfully
    // presented native interface and trap the user in the WebView login boot.
    try {
      if(initialPatient)await showPatient(initialPatient);
      else await screen(initialCalendar?'calendar':'home');
    } catch(error) {
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
    }
  } catch(error) {
    try { if(presented)await destroy(); else { active=false;await listener?.remove(); } }
    catch (_) { /* Preserve the original initialization failure. */ }
    throw error;
  }
  return {destroy,openPatient:id=>void showPatient(id),openCalendar:()=>void screen('calendar'),back:()=>{void handle({id:'back'});return true;}};
}
