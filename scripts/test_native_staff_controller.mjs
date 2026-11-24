import assert from 'node:assert/strict';
import { mock } from 'node:test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
mock.timers.enable({apis:['Date'], now: new Date('2026-11-23T12:00:00+01:00')});
import { mountNativeWorkspace, germanDate, canonicalDate, displayCopy } from '../www/mobile/native-workspace.mjs';
assert.equal(displayCopy('Wallet-Verlauf – Test'),'Wallet Verlauf · Test');
assert.equal(germanDate('2026-11-25 · 16:00'),'25.11.2026 · 16:00');
assert.equal(canonicalDate('25.11.2026'),'2026-11-25');
assert.equal(canonicalDate('29.02.2024'),'2024-02-29');
assert.equal(canonicalDate('29.02.2026'),null);

let current, onAction, closed = false, lastTimelineScreen;
const fixtureDir=process.env.APLUS_NATIVE_QA_FIXTURES;
function capture(name){
  if(!fixtureDir)return;
  mkdirSync(fixtureDir,{recursive:true});
  writeFileSync(join(fixtureDir,name+'.json'),JSON.stringify({screen:current,calendar:lastTimelineScreen}));
}
const preferences={aplus_language:'en'};
globalThis.localStorage={getItem:key=>preferences[key]??null,setItem:(key,value)=>{preferences[key]=value;}};
Object.defineProperty(globalThis,'navigator',{value:{language:'en'}});
globalThis.Capacitor={Plugins:{NativeStaff:{
  async present({screen}){current=screen;},
  async render({screen}){current=screen;if(screen.timeline)lastTimelineScreen=screen;},
  async dismiss(){closed=true;},
  async pickPhoto(){return {filename:'synthetic-photo.jpg',base64:'AA=='};},
  async addListener(name,fn){assert.equal(name,'action');onAction=fn;return{remove(){onAction=null;}};},
}}};
let lastCalendar, lastFinancialUpdate, officeRevision='v1', sourceEditEnabled=false, accountMode='linked', invoiceRequests=0;
const officeSettings={company_name:'A+ Esthetic Demo',street:'Testweg 1',postal_code:'60313',city:'Frankfurt',
  email:'office@example.test',phone:'0691',tax_number:'',vat_id:'',bank_name:'',iban:'',bic:'',
  invoice_prefix:'RE',next_sequence:1};
globalThis.fetch=async(url,opts)=>{
  assert.match(opts.headers.Authorization,/^Bearer synthetic-test-token$/);
  const path=new URL(url).pathname;
  let result;
  if(path.endsWith('/overview/'))result={today:3,upcoming_count:14,patient_count:37,provider_count:2,intake_review_count:1,
    provider_today:[{id:1,name:'Demo clinician',count:3}],upcoming:[{id:44,customer_name:'Synthetic patient',date:'2026-11-23',start:'10:00',staff_name:'Demo clinician',service_name:'Consult',status:'confirmed'}]};
  else if(path.endsWith('/catalog/'))result={
    providers:[{id:1,name:'Demo clinician'},{id:2,name:'A+ Esthetic (SimplyBook #7)',source_managed:true}],
    services:[{id:1,name:'Consult',active:true},{id:2,name:'Imported',slug:'simplybook-event-7',active:true,source_managed:true}],
  };
  else if(path.endsWith('/calendar/')){
    lastCalendar=new URL(url).searchParams.get('start');
    result={
      appointments:[{id:44,customer_id:23,customer_name:'Synced patient',service_name:'Consult',staff_name:'Demo clinician',staff_id:1,service_id:1,
        date:'2026-11-23',start:'10:00',end:'10:30',
        start_at:'2026-11-23T10:00:00+01:00',end_at:'2026-11-23T10:30:00+01:00',source_managed:true,source_editable:sourceEditEnabled,status:'confirmed'}],
      blocks:[
        {id:90,staff_id:1,editable:false,source_managed:true,date:'2026-11-23',start:'12:00',end:'13:00',
          kind:'block',text:'Synced SimplyBook note',start_at:'2026-11-23T12:00:00+01:00',end_at:'2026-11-23T13:00:00+01:00'},
        {id:91,staff_id:1,editable:false,source_managed:false,date:'2026-11-23',start:'13:00',end:'14:00',
          kind:'note',text:'Legacy Book note',start_at:'2026-11-23T13:00:00+01:00',end_at:'2026-11-23T14:00:00+01:00'},
      ],availability:[]
    };
  }
  else if(path.endsWith('/patients/'))result={items:[{id:23,name:'Demo patient',email:'demo@example.test'}],has_more:new URL(url).searchParams.get('page')==='1'};
  else if(path.endsWith('/patient/23/'))result={patient:{id:23,name:'Demo patient',email:'demo@example.test',phone:'069000000'},appointments:[{id:46,public_id:'00000000-0000-4000-8000-000000000046',date:'2026-11-20',start:'11:30',service_name:'Consult',staff_name:'Demo clinician',status:'completed'}],records:[{id:'00000000-0000-4000-8000-000000000099',title:'Synthetic clinical note',date:'2026-11-20',note:'Synthetic record for UI testing',kind:'note',has_file:false}]};
  else if(path.endsWith('/customers/'))result={items:[{id:25,name:'Demo patient',email:'demo@example.test',book_customer_id:accountMode==='unlinked'?null:23,address:{street:'Testweg 1',postal_code:'60313',city:'Frankfurt'}}]};
  else if(path.endsWith('/patient-account/23/')){if(accountMode==='fallback'||accountMode==='unlinked')return {ok:false,status:404};result={customer_id:25};}
  else if(path.endsWith('/customers/25/')){if(accountMode==='missing-detail')return {ok:false,status:404};result={customer:{id:25,name:'Demo patient',coins:240,credit_cents:1500},packages:[{id:1,name:'Synthetic package',remaining_sessions:2,expires_at:'2027-01-01',status:'active'}]};}
  else if(path.endsWith('/record-upload/'))result={ok:true,id:100};
  else if(path.endsWith('/invoices/25/')){invoiceRequests++;return {ok:false,status:404};}
  else if(path.endsWith('/tariff-catalog/'))result={items:[{number:'1',de:'Beratung',en:'Consultation',points:80}],treatments:{},synthetic_reference_available:false};
  else if(path.endsWith('/quote/'))result={subtotal_cents:1072,tax_cents:204,total_cents:1276,items:[{goae_number:'1',description:'Consultation',quantity:'1',factor:'2.30',gross_cents:1276}]};
  else if(path.endsWith('/forms/'))result={items:[{id:17,name:'Synthetic patient',email:'synthetic@example.test',created_at:'2026-11-23T14:00:00Z',status:'review'}]};
  else if(path.endsWith('/forms/17/'))result={submission:{id:17,identity:{first_name:'Synthetic',last_name:'Patient'},answers:{allergies:'None'},created_at:'2026-11-23T14:00:00Z',status:'review',signature_png:''}};
  else if(path.endsWith('/invoice-settings/')){
    if(opts.body){lastFinancialUpdate=JSON.parse(opts.body);officeRevision='v2';result={ok:true,revision:officeRevision};}
    else result={ok:true,revision:officeRevision,ready_for_issue:false,settings:officeSettings};
  }
  else throw Error('Unexpected endpoint '+path);
  return {ok:true,json:async()=>result};
};
const pause=()=>new Promise(r=>setTimeout(r,20));
const click=async(id,values={})=>{onAction({id,values});await pause();};
let native=await mountNativeWorkspace({token:'synthetic-test-token',identity:{role:'admin',name:'Demo Admin'},
  origin:'https://example.test',logout:()=>{}});
assert.equal(current.title,'Welcome');
assert.equal(current.hero,'Practice overview');
assert.match(current.rows[0].detail,/23\.11\.2026/);
assert.equal(current.metrics[0].detail,'3');
capture('01-dashboard');
assert.equal(current.tabs.filter(t=>t.selected).length,1);
assert.equal(current.tabs.find(t=>t.selected).id,'home');
assert.deepEqual(current.tabs.map(t=>t.id),['home','calendar','patients','settings']);
assert.ok(!current.shortcuts.some(t=>['intakes','billing-search'].includes(t.id)));
assert.ok(!current.metrics.some(t=>t.id==='intakes'));
await click('calendar');
assert.equal(current.week.length,7);
assert.equal(current.tabs.find(t=>t.selected).id,'calendar');
assert.equal(current.timeline.mode,'day','native calendar must be a real time grid');
assert.equal(current.timeline.columns.length,1);
assert.equal(current.timeline.firstHour,10);
assert.equal(current.timeline.lastHour,20);
assert.equal(current.timeline.providers.length,2);
assert.ok(current.timeline.events.some(e=>e.id==='block-info:90'));
capture('02-calendar');
await click('block-info:90');
assert.match(current.message,/SimplyBook/);
assert.ok(!current.actions.some(x=>x.id==='save-block-edit'));
await click('calendar');
await click('block-info:91');
assert.match(current.message,/Book administration/);
await click('calendar');
await click('new-appointment');
assert.equal(current.presentation,'calendar-sheet');
assert.equal(current.layout,'simplybook-form');
assert.equal(current.formType,'booking');
assert.deepEqual(current.fields.slice(0,3).map(f=>f.id),['service_id','staff_id','customer_id']);
assert.equal(current.fields.find(f=>f.id==='customer_id').value,'');
assert.equal(current.fields.find(f=>f.id==='service_id').value,'');
capture('03-new-appointment');
assert.ok(!current.fields.find(f=>f.id==='staff_id').options.some(o=>o.value==='2'),'imported provider unavailable for local booking');
assert.ok(!current.fields.find(f=>f.id==='service_id').options.some(o=>o.value==='2'),'imported service unavailable for local booking');
await click('calendar-client-search',{...Object.fromEntries(current.fields.map(f=>[f.id,f.value])),_patient_query:'Demo'});
assert.equal(current.openChoice,'customer_id');
assert.equal(current.choiceQuery,'Demo');
assert.ok(current.fields.find(f=>f.id==='customer_id').options.some(o=>o.label==='Demo patient'));
capture('03b-client-picker');
await click('calendar');
await click('new-block');
assert.equal(current.layout,'simplybook-form');
assert.equal(current.formType,'block');
assert.equal(current.fields.find(f=>f.id==='kind').value,'note');
capture('04-block');
assert.ok(!current.fields.find(f=>f.id==='staff_id').options.some(o=>o.value==='2'),'imported provider unavailable for local blocks');
await click('calendar');
await click('settings');
await click('services');
await click('service:2');
assert.match(current.message,/SimplyBook/);
assert.ok(!current.actions.some(a=>a.id==='save-service'));
await click('calendar');
await click('availability');
assert.equal(current.layout,'simplybook-form');
assert.equal(current.formType,'availability');
capture('06-working-hours');
await click('load-availability',{staff_id:'2',date:'23.11.2026'});
assert.match(current.message,/SimplyBook/);
assert.ok(!current.actions.some(a=>a.id==='save-availability'));
await click('calendar');
await click('appointment:44');
capture('05-appointment-details');
assert.match(current.message,/SimplyBook/);
assert.ok(!current.actions.some(x=>x.id==='edit-appointment' || x.id==='cancel-appointment'));
await click('calendar');
const selectedDay=()=>current.week.find(x=>x.selected)?.id;
const originalDay=selectedDay();
await click('day-next');
assert.notEqual(selectedDay(),originalDay,'calendar body swipe advances one day');
await click('day-prev');
assert.equal(selectedDay(),originalDay,'calendar body swipe reverses one day');
const previous=lastCalendar;
await click('week-next');
assert.notEqual(lastCalendar,previous);
await click('apply-calendar-filter',{calendar_mode:'week',provider_filter:'all',service_filter:'all'});
const previousWeek=lastCalendar;
await click('day-next');
assert.notEqual(lastCalendar,previousWeek,'calendar body swipe advances a full week in week mode');
await click('cal-mode:provider');
assert.equal(current.timeline.mode,'provider');
await click('cal-mode:service');
assert.equal(current.timeline.mode,'service');
await click('cal-mode:day');
assert.equal(current.timeline.mode,'day');
await click('cal-provider:1');
assert.equal(current.timeline.provider,'1');
await click('cal-provider:all');
assert.equal(current.timeline.provider,'all');
await click('cal-today');
assert.equal(current.timeline.date,selectedDay().slice('date:'.length),'selected week strip ID includes action prefix');
await click('settings');
assert.equal(current.title,'Settings');
await click('language');
assert.equal(current.title,'Language');
await click('save-language',{language:'de'});
assert.equal(preferences.aplus_language,'de');
assert.equal(current.title,'Einstellungen');
assert.ok(current.tabs.some(tab=>tab.label==='Kalender'));
await click('calendar');
assert.equal(current.title,'Kalender');
await click('settings');
await click('language');
await click('save-language',{language:'en'});
assert.equal(current.title,'Settings');
assert.ok(current.tabs.some(tab=>tab.label==='Calendar'));
for(const removed of ['office','intakes','billing-search','invoice-form','billing-settings','submission:17']){
  await click(removed);assert.equal(current.title,'Settings','removed Office action must not navigate');
}
await click('patients');
capture('12-patients');
assert.ok(current.actions.some(x=>x.id==='patient-page-next'));
await click('patient-page-next');
assert.match(current.sectionTitle,/Page 2/);
await click('patient:23');
capture('13-patient-profile');
assert.equal(current.title,'Demo patient');
assert.equal(current.tabs.find(t=>t.selected).id,'patients');
await click('patient-section:records');
capture('14-patient-records');
assert.equal(current.segments.find(x=>x.selected).id,'patient-section:records');
await click('record-detail:00000000-0000-4000-8000-000000000099');
assert.equal(current.title,'Synthetic clinical note');
capture('15-record-detail');
await click('patient-section:account');
assert.equal(current.metrics[0].detail,'240');
capture('16-patient-account');
assert.equal(invoiceRequests,0,'Office invoice request removed from account tab');
accountMode='fallback';await click('patient-section:contact');await click('patient-section:account');assert.equal(current.metrics[0].detail,'240');assert.equal(current.segments.find(s=>s.selected).id,'patient-section:account');
accountMode='unlinked';await click('patient-section:account');assert.equal(current.segments.find(s=>s.selected).id,'patient-section:account');assert.ok(!current.message.includes('404'));assert.ok(current.actions.some(a=>a.id==='patient-link-account'));
await click('patient-link-account');assert.equal(current.title,'Link customer account');assert.equal(current.fields.find(f=>f.id==='customer_id').value,'');assert.equal(current.fields.find(f=>f.id==='confirm').value,'no');
accountMode='missing-detail';await click('patient-section:account');assert.match(current.message,/no longer available/);assert.equal(current.segments.find(s=>s.selected).id,'patient-section:account');
accountMode='linked';await click('patient-section:account');
await click('patient-section:records');
await click('upload-photo');
assert.ok(current.actions.some(x=>x.id==='confirm-upload'));
await click('discard-upload');
await click('patient-section:records');
await click('note');
assert.equal(current.title,'New note');
assert.equal(current.fields.find(x=>x.id==='note').kind,'multiline');
assert.equal(current.fields.find(x=>x.id==='title').kind,'text');
await native.destroy();
assert.ok(closed);
sourceEditEnabled=true;
native=await mountNativeWorkspace({token:'synthetic-test-token',identity:{role:'admin',name:'Demo Admin'},
  origin:'https://example.test',logout:()=>{}});
await click('calendar');
await click('appointment:44');
assert.ok(current.actions.some(action=>action.id==='edit-appointment'),'server-enabled source booking can be rescheduled by admin');
assert.ok(current.actions.some(action=>action.id==='cancel-appointment'),'server-enabled source booking can be cancelled by admin');
await click('edit-appointment');
assert.deepEqual(current.fields.map(field=>field.id),['date','start'],
  'source appointment offers only the two supported editable time fields');
await native.destroy();
native=await mountNativeWorkspace({token:'synthetic-test-token',identity:{role:'doctor',name:'Demo Doctor'},
  origin:'https://example.test',logout:()=>{}});
assert.ok(!current.tabs.some(t=>t.id==='office'));
await native.destroy();
delete preferences.aplus_language;
native=await mountNativeWorkspace({token:'synthetic-test-token',identity:{role:'admin',name:'Demo Admin'},origin:'https://example.test',logout:()=>{}});
assert.equal(current.language,'de','German default even on English device');
assert.equal(current.rows[0].badge,'Bestätigt');
capture('01-dashboard');
await click('calendar');
await click('new-appointment');capture('03-new-appointment');
await click('calendar-client-search',{...Object.fromEntries(current.fields.map(f=>[f.id,f.value])),_patient_query:'Demo'});capture('03b-client-picker');
await click('calendar');await click('new-block');capture('04-block');
await click('calendar');await click('availability');capture('06-working-hours');
await click('patients');await click('patient:23');capture('13-patient-profile');
await click('patient-section:contact');capture('16a-patient-contact');
await click('patient-section:account');capture('16-patient-account');
await native.destroy();
console.log('PASS: native controller, SimplyBook form layouts, calendar swipes, German defaults, Office hidden, medical notes and role tabs');
