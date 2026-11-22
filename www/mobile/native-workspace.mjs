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
  let date = today(), search = '', active = true, busy = false, listener, patient, catalog, appointment;
  let current = {title:'A+ Esthetic',busy:true,tabs:[]};
  const tabs = [
    {...row('home',tr('Übersicht','Home')), icon:'square.grid.2x2'},
    {...row('calendar',tr('Kalender','Calendar')),icon:'calendar'},
    {...row('patients',tr('Patienten','Patients')),icon:'person.2'},
    ...(admin ? [{...row('office','Office'),icon:'doc.text'}] : []),
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
      rememberAppointments(data.appointments);
      const found=(data.appointments||[]).filter(a=>a.date===date);
      const blocked=(data.blocks||[]).filter(a=>String(a.start_at).slice(0,10)===date);
      return render(view(tr('Kalender','Calendar'),{subtitle:dateLabel(date,locale,{weekday:'long',day:'numeric',month:'long'}),
        week:days,message:date===shiftDay(weekStart,6)?tr('Sonntag · Online-Buchung geschlossen','Sunday · Online booking closed'):'',
        rows:[...found.map(a=>row('appointment:'+a.id,a.start+' · '+a.customer_name,a.service_name+' · '+a.staff_name)),
          ...blocked.map(b=>row('',b.start+' · '+(b.text||tr('Gesperrt','Blocked')),b.end||''))],
        actions:[row('new-appointment',tr('Termin hinzufügen','Add appointment'))]}));
    }
    if(name==='patients'){
      const r=await book('patients/?q='+encodeURIComponent(search));
      return render(view(tr('Patienten','Patients'),{fields:[value('query',tr('Suchen','Search'),search)],
        actions:[row('search',tr('Suchen','Search'))],rows:r.items.map(x=>row('patient:'+x.id,x.name,x.email||x.phone||''))}));
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
      ...patient.records.map(r=>row('',r.title,r.note||r.date.slice(0,10))),
    ],actions:[row('note',tr('Behandlungsnotiz hinzufügen','Add treatment note'))]}));
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
  async function appendForm(edit=false) {
    catalog=await book('catalog/');
    const r=await book('patients/?q='+encodeURIComponent(search));
    const options=r.items.map(x=>option(x.id,x.name));
    const fields=[
      value('customer_id',tr('Patient','Patient'),edit?appointment.customer_id:options[0]?.value,options),
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
  let billingUser, billingVisits, reviewPair, intakeRecord;
  async function showBilling(id) {
    const r=await office('customers/?q='+encodeURIComponent(search));
    billingUser=r.items.find(u=>u.id===id);
    if(!billingUser)throw new Error(tr('Patient nicht verfügbar','Patient unavailable'));
    stack.push('billing:'+id);
    const list=await office('invoices/'+id+'/');
    return render(view(billingUser.name,{subtitle:billingUser.email,
      rows:list.items.map(i=>row('',i.service_date+' · '+(i.total_cents/100).toFixed(2)+' EUR',i.status)),
      actions:[row(billingUser.book_customer_id?'invoice-form':'link-search',billingUser.book_customer_id?tr('GOÄ Entwurf','GOÄ draft'):tr('Book Identität verifizieren','Verify Book identity'))]}));
  }
  async function invoiceForm(){
    const r=await book('patient/'+billingUser.book_customer_id+'/');
    billingVisits=r.appointments.filter(a=>a.status==='completed');
    if(!billingVisits.length)throw new Error(tr('Kein abgeschlossener Besuch.','No completed visit.'));
    const addr=billingUser.address;
    return render(view(tr('GOÄ Entwurf erstellen','Create GOÄ draft'),{
      message:tr('Gebührennummer, Einfachsatz und Steuerstatus ärztlich prüfen.','Clinician must verify tariff code, base fee and tax classification.'),
      fields:[value('visit_id',tr('Besuch','Visit'),billingVisits[0].public_id,billingVisits.map(a=>option(a.public_id,a.date+' · '+a.service_name))),
        value('street',tr('Straße','Street'),addr.street),value('postal_code',tr('PLZ','Postal code'),addr.postal_code),value('city',tr('Ort','City'),addr.city),
        value('goae_number','GOÄ Nr.'),value('goae_description',tr('Leistung','Service')),
        value('goae_base_eur',tr('Einfachsatz EUR','Base fee EUR')),value('goae_factor',tr('Faktor','Factor'),'1.00'),
        value('quantity',tr('Anzahl','Quantity'),'1'),value('goae_vat_rate',tr('Umsatzsteuer','VAT'),'',[
          option('',tr('Bitte auswählen','Select')),option('0','0%'),option('7','7%'),option('19','19%')]),
        value('goae_justification',tr('Begründung','Justification'))],
      actions:[row('save-invoice',tr('Entwurf speichern','Save draft'))]}));
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
        return await screen(['home','calendar','patients','office','intakes','identity-review','billing-search'].includes(back)?back:'home');
      }
      if(['home','calendar','patients','office','intakes','identity-review','billing-search'].includes(id)){
        if(id==='patients'||id==='billing-search')search='';
        return await screen(id);
      }
      if(id==='week-next'||id==='week-prev'){date=shiftDay(date,id==='week-next'?7:-7);return await screen('calendar',{push:false});}
      if(id.startsWith('date:')){date=id.slice(5);return await screen('calendar',{push:false});}
      if(id==='search'||id==='billing-query'){search=fields.query||'';return await screen(id==='search'?'patients':'billing-search',{push:false});}
      if(id.startsWith('patient:'))return await showPatient(Number(id.split(':')[1]));
      if(id.startsWith('appointment:'))return await showAppointment(Number(id.split(':')[1]));
      if(id==='new-appointment'){search='';return await appendForm(false);}
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
      if(admin&&id==='save-invoice'){
        const {street,postal_code,city,visit_id,...line}=fields;
        await command('office/draft/',{customer_id:billingUser.id,visit_id,address:{street,postal_code,city},save_missing_address:true,lines:[line]},'request_id');
        return await showBilling(billingUser.id);
      }
    } catch(err) {
      if(err.status===401){await destroy();logout();return;}
      await render({...current,message:err.message||tr('Bitte erneut versuchen.','Please try again.'),fields:(current.fields||[]).map(f=>({...f,value:fields[f.id]??f.value}))});
    } finally {busy=false;}
  }
  async function destroy(){if(!active)return;active=false;await listener?.remove();await plugin.dismiss();}
  listener=await plugin.addListener('action',event=>void handle(event));
  try {
    await plugin.present({screen:current});
    if(initialPatient)await showPatient(initialPatient);
    else await screen(initialCalendar?'calendar':'home');
  } catch(error){await destroy();throw error;}
  return {destroy,openPatient:id=>void showPatient(id),openCalendar:()=>void screen('calendar'),back:()=>{void handle({id:'back'});return true;}};
}
