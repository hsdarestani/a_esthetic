// One screen/state controller; all controls are rendered by UIKit/SwiftUI or
// Android Views. No staff HTML, browser navigation or web forms are mounted.
import { today, startWeek, shiftDay } from './calendar.mjs';

const value = (id, label, initial = '', options) => ({id,label,value:String(initial ?? ''), ...(options ? {options} : {})});
const row = (id,label,detail='') => ({id,label,detail});
const option = (value,label) => ({value:String(value),label:String(label)});
const dateLabel = (date, locale, options) => new Date(date+'T12:00:00Z').toLocaleDateString(locale,{...options,timeZone:'UTC'});
const optionFor = (list) => list.map(x=>option(x.id,x.name));
const uuid = () => globalThis.crypto.randomUUID();

export async function mountNativeWorkspace({token, identity, origin, logout, initialPatient, initialCalendar}) {
  const plugin = globalThis.Capacitor?.Plugins?.NativeStaff;
  if (!plugin) throw new Error('Native staff renderer unavailable');
  const admin = identity.role === 'admin';
  const language = (localStorage.getItem('aplus_language') || navigator.language || 'de').startsWith('en') ? 'en' : 'de';
  const tr = (de,en) => language === 'en' ? en : de;
  const locale = language === 'en' ? 'en-GB' : 'de-DE';
  const stack = [];
  const appointmentsById = new Map();
  const rememberAppointments = items => { for(const a of items||[]) appointmentsById.set(a.id,a); };
  let date = today(), search = '', calendarMode='day', providerFilter='all', serviceFilter='all', active = true, busy = false, listener, patient, catalog, appointment;
  let current = {title:'A+ Esthetic',busy:true,tabs:[]};
  const blockById = new Map();
  const tabs = [
    {...row('home',tr('Übersicht','Home')), icon:'square.grid.2x2'},
    {...row('calendar',tr('Kalender','Calendar')),icon:'calendar'},
    {...row('patients',tr('Patienten','Patients')),icon:'person.2'},
    ...(admin ? [{...row('office','Office'),icon:'doc.text'}] : []),
    {...row('settings',tr('Einstellungen','Settings')),icon:'gearshape'},
  ];
  async function request(path, data) {
    const response = await fetch(origin+'/api/mobile/staff/'+path,{
      method:data ? 'POST':'GET', headers:{Authorization:'Bearer '+token,Accept:'application/json','Content-Type':'application/json'},
      cache:'no-store', ...(data?{body:JSON.stringify(data)}:{}),
    });
    if(!response.ok){const err=new Error(tr('Vorgang konnte nicht abgeschlossen werden.','Unable to complete request.'));err.status=response.status;throw err;}
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
  const view = (title, content={}) => ({title, tabs, ...content});
  async function render(screen) { if(!active)return; current=screen; await plugin.render({screen}); }
  async function screen(name, {push=true}={}) {
    if(push && stack.at(-1)!==name)stack.push(name);
    if(name==='home'){
      const r=await book('overview/');
      rememberAppointments(r.upcoming);
      return render(view(tr('Willkommen','Welcome'),{subtitle:identity.name,rows:[
        row('calendar',tr('Heute','Today'),String(r.today)+' '+tr('Termine','appointments')),
        ...(r.upcoming||[]).slice(0,12).map(a=>row('appointment:'+a.id,a.customer_name,a.date+' · '+a.start+' · '+a.service_name)),
      ],actions:[row('logout',tr('Abmelden','Sign out'))]}));
    }
    if(name==='calendar'){
      const weekStart=startWeek(date), data=await book('calendar/?start='+weekStart+'&days=7');
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
      return render(view(tr('Kalender','Calendar'),{subtitle:dateLabel(date,locale,{weekday:'long',day:'numeric',month:'long'}),
        week:days,message:date===shiftDay(weekStart,6)?tr('Sonntag · Online-Buchung geschlossen','Sunday · Online booking closed'):'',
        fields:[
          value('calendar_mode',tr('Ansicht','View'),calendarMode,[option('day',tr('Tag','Day')),option('week',tr('Woche','Week')),option('provider',tr('Behandler','Provider')),option('service',tr('Behandlung','Service'))]),
          value('provider_filter',tr('Behandler','Provider'),providerFilter,[option('all',tr('Alle','All')),...optionFor(catalog.providers)]),
          value('service_filter',tr('Behandlung','Service'),serviceFilter,[option('all',tr('Alle','All')),...optionFor(catalog.services.filter(x=>x.active))]),
        ],
        rows:[...found.map(a=>row('appointment:'+a.id,(calendarMode==='week'?a.date+' · ':'')+a.start+' · '+a.customer_name,a.service_name+' · '+a.staff_name)),
          ...blocked.map(b=>row(b.editable?'block:'+b.id:'',b.start+' · '+(b.text||tr('Gesperrt','Blocked')),b.end||''))],
        actions:[row('apply-calendar-filter',tr('Ansicht aktualisieren','Apply filters')),
          row('new-appointment',tr('Termin hinzufügen','Add appointment')),row('new-block',tr('Sperrzeit / Notiz','Block / note')),
          row('availability',tr('Arbeitszeit','Working hours'))]}));
    }
    if(name==='patients'){
      const r=await book('patients/?q='+encodeURIComponent(search));
      return render(view(tr('Patienten','Patients'),{fields:[value('query',tr('Suchen','Search'),search)],
        actions:[row('search',tr('Suchen','Search'))],rows:r.items.map(x=>row('patient:'+x.id,x.name,x.email||x.phone||''))}));
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
        String(s.duration_minutes)+' min · '+String(s.buffer_minutes)+' min '+tr('Puffer','buffer')))}));
    }
    if(name==='office' && admin){
      return render(view('Office',{rows:[
        row('intakes',tr('Aufnahmebogen prüfen','Review intake')),
        row('identity-review',tr('Patientenidentität prüfen','Review identity')),
        row('billing-search',tr('GOÄ Rechnung erstellen','Create GOÄ draft')),
      ]}));
    }
    if(name==='intakes'&&admin){
      const r=await office('intake-reviews/');
      return render(view(tr('Aufnahmen','Intake reviews'),{rows:r.items.map(x=>row('intake:'+x.id,
        x.submission.first_name+' '+x.submission.last_name,x.created_at.slice(0,10)))}));
    }
    if(name==='identity-review'&&admin){
      const r=await book('identity-review/');
      return render(view(tr('Identität prüfen','Review identity'),{rows:r.items.map(x=>row(
        'review:'+x.left.id+':'+x.right.id,x.left.name+' / '+x.right.name,x.reason))}));
    }
    if(name==='billing-search'&&admin){
      const r=search.length>=2?await office('customers/?q='+encodeURIComponent(search)):{items:[]};
      return render(view(tr('GOÄ Rechnung','GOÄ invoice'),{fields:[value('query',tr('Patient suchen','Find patient'),search)],
        actions:[row('billing-query',tr('Suchen','Search'))], rows:r.items.map(x=>row('billing:'+x.id,x.name,x.email))}));
    }
  }

  async function showPatient(id) {
    patient=await book('patient/'+id+'/');
    rememberAppointments(patient.appointments);
    stack.push('patient:'+id);
    const p=patient.patient;
    return render(view(p.name,{subtitle:p.email,rows:[
      ...patient.appointments.map(a=>row('appointment:'+a.id,a.date+' · '+a.start,a.service_name)),
      ...patient.records.map(r=>row(r.has_file?'record:'+r.id:'',r.title,r.note||r.date.slice(0,10))),
    ],actions:[row('new-patient-appointment',tr('Termin für Patient hinzufügen','Book for patient')),row('note',tr('Behandlungsnotiz hinzufügen','Add treatment note'))]}));
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
    appointment=await getAppointment(id);stack.push('appointment:'+id);
    return render(view(appointment.customer_name,{subtitle:appointment.service_name,rows:[
      row('',appointment.date+' · '+appointment.start+' – '+appointment.end, appointment.staff_name),
      row('',tr('Status','Status'),appointment.status),row('',tr('Notiz','Note'),appointment.notes||''),
    ],actions:appointment.source_managed?[]:[row('edit-appointment',tr('Bearbeiten','Edit')),row('cancel-appointment',tr('Absagen','Cancel'))]}));
  }
  async function appendForm(edit=false, chosenPatient=null) {
    catalog=await book('catalog/');
    const r=await book('patients/?q='+encodeURIComponent(search));
    const options=r.items.map(x=>option(x.id,x.name));
    if(chosenPatient&&!options.some(x=>x.value===String(chosenPatient.id)))options.unshift(option(chosenPatient.id,chosenPatient.name));
    const fields=[
      value('customer_id',tr('Patient','Patient'),edit?appointment.customer_id:chosenPatient?.id||options[0]?.value,options),
      value('staff_id',tr('Behandler','Provider'),edit?appointment.staff_id:catalog.providers[0]?.id,optionFor(catalog.providers)),
      value('service_id',tr('Behandlung','Treatment'),edit?appointment.service_id:catalog.services[0]?.id,optionFor(catalog.services.filter(x=>x.active))),
      value('date',tr('Datum (JJJJ-MM-TT)','Date (YYYY-MM-DD)'),edit?appointment.date:date),
      value('start',tr('Beginn (HH:MM)','Start (HH:MM)'),edit?appointment.start:'10:00'),
      value('notes',tr('Notiz','Notes'),edit?appointment.notes:''),
    ];
    stack.push(edit?'edit-appointment':'new-appointment');
    return render(view(edit?tr('Termin bearbeiten','Edit appointment'):tr('Neuer Termin','New appointment'),
      {fields,actions:[row(edit?'save-edit':'save-new',tr('Speichern','Save'))]}));
  }
  let currentBlock, currentService;
  async function blockForm(edit){
    catalog=catalog||await book('catalog/');
    return render(view(edit?tr('Kalendereintrag bearbeiten','Edit calendar entry'):tr('Sperrzeit / Notiz','Block / note'),{fields:[
      value('staff_id',tr('Behandler','Provider'),edit?currentBlock.staff_id:catalog.providers[0]?.id,optionFor(catalog.providers)),
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
    return render(view(tr('Arbeitszeit','Working hours'),{subtitle:date,fields:[
      value('staff_id',tr('Behandler','Provider'),provider.id,optionFor(catalog.providers)),value('date',tr('Datum','Date'),date),
      value('operation',tr('Gültigkeit','Scope'),'daily',[option('daily',tr('Diesen Tag','This day')),option('weekly',tr('Wöchentlich','Weekly')),option('reset',tr('Tagesausnahme zurücksetzen','Reset override'))]),
      value('closed',tr('Geschlossen','Closed'),ranges.length?'no':'yes',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))]),
      value('start_1',tr('Beginn','Start'),ranges[0]?.start||'09:00'),value('end_1',tr('Ende','End'),ranges[0]?.end||'18:00'),
      value('start_2',tr('Zweiter Beginn (optional)','Second start (optional)'),ranges[1]?.start||''),
      value('end_2',tr('Zweites Ende (optional)','Second end (optional)'),ranges[1]?.end||''),
    ],actions:[row('load-availability',tr('Behandler / Datum laden','Load provider / date')),row('save-availability',tr('Speichern','Save'))]}));
  }
  let billingUser, billingVisits, reviewPair, intakeRecord, invoiceLines=[], invoiceMeta={}, editingInvoice=null, selectedInvoice=null;
  async function showBilling(id) {
    const r=await office('customers/?q='+encodeURIComponent(search));
    billingUser=r.items.find(u=>u.id===id);
    if(!billingUser)throw new Error(tr('Patient nicht verfügbar','Patient unavailable'));
    stack.push('billing:'+id);
    const list=await office('invoices/'+id+'/');
    return render(view(billingUser.name,{subtitle:billingUser.email,
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
      invoiceLines=[];
      invoiceMeta={visit_id:billingVisits[0].public_id,street:addr.street,postal_code:addr.postal_code,city:addr.city,
        service_date:'',date_correction_reason:''};
    }
    const fields=[
      value('visit_id',tr('Besuch','Visit'),invoiceMeta.visit_id,billingVisits.map(a=>option(a.public_id,a.date+' · '+a.service_name))),
      value('service_date',tr('Abweichendes Leistungsdatum (optional)','Corrected visit date (optional)'),invoiceMeta.service_date),
      value('date_correction_reason',tr('Begründung der Datumskorrektur','Reason for date correction'),invoiceMeta.date_correction_reason),
      value('street',tr('Straße','Street'),invoiceMeta.street),value('postal_code',tr('PLZ','Postal code'),invoiceMeta.postal_code),value('city',tr('Ort','City'),invoiceMeta.city),
    ];
    return render(view(tr('GOÄ Entwurf erstellen','Create GOÄ draft'),{
      message:tr('Gebührennummer, Einfachsatz und Steuerstatus ärztlich prüfen.','Clinician must verify tariff code, base fee and tax classification.'),
      fields, rows:invoiceLines.map((line,i)=>row('invoice-line:'+i,(line.kind==='material'?tr('Auslage','Expense'):line.goae_number)+' · '+line.goae_description,
        tr('Anzahl','Quantity')+' '+line.quantity+(line.kind==='material'?'':' · '+line.goae_factor+'×'))),
      actions:[row('add-invoice-line',tr('GOÄ Leistung hinzufügen','Add GOÄ service')),row('add-material-line',tr('Auslage hinzufügen','Add expense')),
        ...(invoiceLines.length?[row('invoice-quote',tr('Beträge prüfen','Review totals'))]:[])],
    }));
  }
  async function invoiceDetail(id){
    selectedInvoice=await office('detail/'+id+'/');
    const i=selectedInvoice.invoice;
    return render(view(i.number||tr('GOÄ Entwurf','GOÄ draft'),{subtitle:i.service_date,
      rows:[row('',tr('Status','Status'),i.status),row('',tr('Gesamt','Total'),(i.total_cents/100).toFixed(2)+' EUR')],
      actions:[row('invoice-pdf:'+id,tr('PDF anzeigen','View PDF')),...(i.status==='draft'?[row('invoice-edit',tr('Entwurf bearbeiten','Edit draft'))]:[]),
        ...(i.status==='draft'&&selectedInvoice.can_simulate?[row('invoice-simulate',tr('Testrechnung nummerieren','Number test invoice'))]:[])]}));
  }
  async function lineForm(index,material=false){
    const line=invoiceLines[index]||{};
    if(material||line.kind==='material')return render(view(tr('Auslage erfassen','Record expense'),{message:tr('Nur tatsächlich entstandene, nach § 10 berechnungsfähige Auslagen erfassen.','Only actual eligible expenses under § 10.'),fields:[
      value('goae_description',tr('Art der Auslage','Expense description'),line.goae_description),value('goae_base_eur',tr('Tatsächlicher Einzelpreis EUR','Actual unit cost EUR'),line.goae_base_eur),
      value('quantity',tr('Anzahl','Quantity'),line.quantity||'1'),value('goae_vat_rate',tr('Umsatzsteuer','VAT'),line.goae_vat_rate||'',[option('',tr('Bitte auswählen','Select')),option('0','0%'),option('7','7%'),option('19','19%')]),
      value('material_receipt_reference',tr('Belegreferenz','Receipt reference'),line.material_receipt_reference),value('material_eligible',tr('Berechnungsfähigkeit geprüft?','Eligibility verified?'),line.material_eligible?'yes':'no',[option('no',tr('Nein','No')),option('yes',tr('Ja','Yes'))]),
    ],actions:[row('save-material:'+index,tr('Auslage speichern','Save expense')),...(invoiceLines[index]?[row('delete-line:'+index,tr('Position entfernen','Remove line'))]:[])]}));
    return render(view(tr('GOÄ Position','GOÄ line'),{fields:[
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
    const r=await office('quote/',{lines:invoiceLines});
    const money=cents=>(cents/100).toFixed(2)+' EUR';
    return render(view(tr('Entwurf prüfen','Review draft'),{rows:[
      ...r.items.map(i=>row('',(i.goae_number||tr('Auslage','Expense'))+' · '+i.description,money(i.gross_cents))),
      row('',tr('Netto','Net'),money(r.subtotal_cents)),
      row('',tr('Steuer','Tax'),money(r.tax_cents)),
      row('',tr('Gesamt','Total'),money(r.total_cents)),
    ],message:tr('Entwurf – nicht zur Zahlung verwenden.','Draft – not for payment.'),
      actions:[row('save-invoice',tr('Entwurf speichern','Save draft')),row('invoice-return',tr('Weiter bearbeiten','Continue editing'))]}));
  }

  async function showPDF(path,title){
    const response=await fetch(origin+'/api/mobile/staff/'+path,{headers:{Authorization:'Bearer '+token},cache:'no-store'});
    if(!response.ok)throw new Error(tr('Datei nicht verfügbar','File unavailable'));
    const blob=await response.blob();
    if(blob.size>8000000)throw new Error(tr('Datei zu groß','File too large'));
    const bytes=new Uint8Array(await blob.arrayBuffer());
    if(String.fromCharCode(...bytes.slice(0,5))!=='%PDF-')throw new Error(tr('Dieses Dateiformat wird noch nicht unterstützt','This file type is not supported'));
    let chunk='';for(let i=0;i<bytes.length;i+=16384)chunk+=String.fromCharCode(...bytes.subarray(i,i+16384));
    await plugin.previewPDF({title,base64:btoa(chunk)});
  }
  async function handle(event) {
    if(!active || busy) return;
    const id=event.id, fields=event.values||{};
    busy=true;
    try {
      if(id==='logout'){await destroy();logout();return;}
      if(id==='back'){
        stack.pop();const back=stack.pop()||'home';
        if(back.startsWith('patient:'))return await showPatient(Number(back.split(':')[1]));
        if(back.startsWith('billing:'))return await showBilling(Number(back.split(':')[1]));
        if(back.startsWith('appointment:'))return await showAppointment(Number(back.split(':')[1]));
        return await screen(['home','calendar','patients','office','intakes','identity-review','billing-search','settings','services'].includes(back)?back:'home');
      }
      if(['home','calendar','patients','office','intakes','identity-review','billing-search','settings','services'].includes(id)){
        if(id==='patients'||id==='billing-search')search='';
        return await screen(id);
      }
      if(id==='week-next'||id==='week-prev'){date=shiftDay(date,id==='week-next'?7:-7);return await screen('calendar',{push:false});}
      if(id.startsWith('date:')){date=id.slice(5);return await screen('calendar',{push:false});}
      if(id==='search'||id==='billing-query'){search=fields.query||'';return await screen(id==='search'?'patients':'billing-search',{push:false});}
      if(id.startsWith('patient:'))return await showPatient(Number(id.split(':')[1]));
      if(id.startsWith('appointment:'))return await showAppointment(Number(id.split(':')[1]));
      if(id==='apply-calendar-filter'){
        calendarMode=fields.calendar_mode;providerFilter=fields.provider_filter;serviceFilter=fields.service_filter;
        return await screen('calendar',{push:false});
      }
      if(id==='new-block')return await blockForm(false);
      if(id.startsWith('block:')){currentBlock=blockById.get(Number(id.split(':')[1]));if(currentBlock?.editable)return await blockForm(true);return;}
      if(['save-block-new','save-block-edit','remove-block'].includes(id)){
        if(id==='remove-block'){
          await command('book/block/',{operation:'delete',staff_id:currentBlock.staff_id,id:currentBlock.id});
        } else {
          await command('book/block/',{...fields,staff_id:Number(fields.staff_id),operation:id==='save-block-new'?'create':'update',...(id==='save-block-edit'?{id:currentBlock.id}:{})});
        }
        return await screen('calendar');
      }
      if(id==='availability')return await availabilityForm();
      if(id==='load-availability'){date=fields.date||date;return await availabilityForm(fields.staff_id);}
      if(id==='save-availability'){await command('book/availability/',{...fields,staff_id:Number(fields.staff_id),closed:fields.closed==='yes'});date=fields.date;return await screen('calendar');}
      if(admin&&id.startsWith('service:')){
        currentService=catalog.services.find(s=>s.id===Number(id.split(':')[1]));
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
      if(id==='save-language'){localStorage.setItem('aplus_language',fields.language);return await screen('settings');}
      if(id==='new-appointment'){search='';return await appendForm(false);}
      if(id==='new-patient-appointment')return await appendForm(false,patient.patient);
      if(id.startsWith('record:'))return await showPDF('book/patient/'+patient.patient.id+'/records/'+id.slice(7)+'/',tr('Patientendokument','Patient document'));
      if(admin&&id.startsWith('invoice-pdf:'))return await showPDF('office/pdf/'+Number(id.slice(12))+'/',tr('GOÄ Entwurf','GOÄ draft'));
      if(id==='edit-appointment')return await appendForm(true);
      if(id==='save-new'||id==='save-edit'){
        const payload={operation:id==='save-new'?'create':'update',...fields};
        for(const k of ['customer_id','staff_id','service_id'])payload[k]=Number(payload[k]);
        if(id==='save-edit'){payload.id=appointment.id;payload.revision=appointment.revision;payload.status=appointment.status;}
        await command('book/appointment/',payload);appointmentsById.clear();return await screen('calendar');
      }
      if(id==='cancel-appointment')return await render(view(tr('Absage bestätigen','Confirm cancellation'),{
        subtitle:appointment.customer_name,actions:[row('confirm-cancel',tr('Termin absagen','Cancel appointment'))]}));
      if(id==='confirm-cancel'){await command('book/appointment/',{operation:'cancel',id:appointment.id,revision:appointment.revision});appointmentsById.clear();return await screen('calendar');}
      if(id==='note')return await render(view(tr('Neue Notiz','New note'),{fields:[value('title',tr('Titel','Title')),value('note',tr('Notiz','Note'))],actions:[row('save-note',tr('Speichern','Save'))]}));
      if(id==='save-note'){await command('book/record-note/',{customer_id:patient.patient.id,...fields});return await showPatient(patient.patient.id);}
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
        return await screen('intakes');
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
        invoiceLines=draft.lines;invoiceMeta={visit_id:draft.visit_id,service_date:draft.service_date===selectedInvoice.original_date?'':draft.service_date,date_correction_reason:draft.date_correction_reason,...draft.address};
        return await invoiceForm(false);
      }
      if(admin&&id==='invoice-simulate')return await render(view(tr('Testrechnung bestätigen','Confirm test invoice'),{message:tr('Nur synthetische QA-Rechnung, nicht zur Zahlung.','Synthetic QA invoice only, not for payment.'),actions:[row('confirm-simulation',tr('Testrechnung nummerieren','Number test invoice'))]}));
      if(admin&&id==='confirm-simulation'){
        await office('issue-simulation/'+selectedInvoice.invoice.id+'/',{revision:selectedInvoice.invoice.revision,confirmed_synthetic:true});
        return await invoiceDetail(selectedInvoice.invoice.id);
      }
      if(admin&&id==='add-invoice-line'){invoiceMeta={...fields};return await lineForm(invoiceLines.length);}
      if(admin&&id==='add-material-line'){invoiceMeta={...fields};return await lineForm(invoiceLines.length,true);}
      if(admin&&id.startsWith('invoice-line:')){invoiceMeta={...fields};return await lineForm(Number(id.split(':')[1]));}
      if(admin&&id.startsWith('save-material:')){const idx=Number(id.split(':')[1]);const material={...fields,kind:'material',material_eligible:fields.material_eligible==='yes'};await office('quote/',{lines:[material]});invoiceLines[idx]=material;return await invoiceForm(false);}
      if(admin&&id.startsWith('save-line:')){
        const idx=Number(id.split(':')[1]);
        await office('quote/',{lines:[fields]});
        invoiceLines[idx]=fields;return await invoiceForm(false);
      }
      if(admin&&id.startsWith('delete-line:')){invoiceLines.splice(Number(id.split(':')[1]),1);return await invoiceForm(false);}
      if(admin&&id==='invoice-quote'){invoiceMeta={...fields};return await quote();}
      if(admin&&id==='invoice-return')return await invoiceForm(false);
      if(admin&&id==='save-invoice'){
        const {street,postal_code,city,visit_id,service_date,date_correction_reason}=invoiceMeta;
        const body={customer_id:billingUser.id,visit_id,address:{street,postal_code,city},service_date,date_correction_reason,save_missing_address:true,lines:invoiceLines};
        if(editingInvoice){await office('edit-draft/'+editingInvoice.id+'/',{...body,revision:editingInvoice.revision});editingInvoice=null;}
        else await command('office/draft/',body,'request_id');
        return await showBilling(billingUser.id);
      }
    } catch(err) {
      if(err.status===401){await destroy();logout();return;}
      await render({...current,message:err.message||tr('Bitte erneut versuchen.','Please try again.'),fields:(current.fields||[]).map(f=>({...f,value:fields[f.id]??f.value}))});
    } finally {busy=false;}
  }
  async function destroy(){if(!active)return;active=false;appointmentsById.clear();pendingCommands.clear();blockById.clear();await listener?.remove();await plugin.dismiss();}
  listener=await plugin.addListener('action',event=>void handle(event));
  try {
    await plugin.present({screen:current});
    if(initialPatient)await showPatient(initialPatient);
    else await screen(initialCalendar?'calendar':'home');
  } catch(error){await destroy();throw error;}
  return {destroy,openPatient:id=>void showPatient(id),openCalendar:()=>void screen('calendar'),back:()=>{void handle({id:'back'});return true;}};
}
