import assert from 'node:assert/strict';
import { mock } from 'node:test';
mock.timers.enable({apis:['Date'], now: new Date('2026-11-23T12:00:00+01:00')});
import { mountNativeWorkspace } from '../www/mobile/native-workspace.mjs';

let current, onAction, closed = false;
const preferences={aplus_language:'en'};
globalThis.localStorage={getItem:key=>preferences[key]??null,setItem:(key,value)=>{preferences[key]=value;}};
Object.defineProperty(globalThis,'navigator',{value:{language:'en'}});
globalThis.Capacitor={Plugins:{NativeStaff:{
  async present({screen}){current=screen;},
  async render({screen}){current=screen;},
  async dismiss(){closed=true;},
  async addListener(name,fn){assert.equal(name,'action');onAction=fn;return{remove(){onAction=null;}};},
}}};
let lastCalendar, lastFinancialUpdate, officeRevision='v1', sourceEditEnabled=false;
const officeSettings={company_name:'A+ Esthetic Demo',street:'Testweg 1',postal_code:'60313',city:'Frankfurt',
  email:'office@example.test',phone:'0691',tax_number:'',vat_id:'',bank_name:'',iban:'',bic:'',
  invoice_prefix:'RE',next_sequence:1};
globalThis.fetch=async(url,opts)=>{
  assert.match(opts.headers.Authorization,/^Bearer synthetic-test-token$/);
  const path=new URL(url).pathname;
  let result;
  if(path.endsWith('/overview/'))result={today:0,upcoming:[]};
  else if(path.endsWith('/catalog/'))result={
    providers:[{id:1,name:'Demo clinician'},{id:2,name:'A+ Esthetic (SimplyBook #7)',source_managed:true}],
    services:[{id:1,name:'Consult',active:true},{id:2,name:'Imported',slug:'simplybook-event-7',active:true,source_managed:true}],
  };
  else if(path.endsWith('/calendar/')){
    lastCalendar=new URL(url).searchParams.get('start');
    result={
      appointments:[{id:44,customer_id:23,customer_name:'Synced patient',service_name:'Consult',staff_name:'Demo clinician',staff_id:1,service_id:1,
        date:'2026-11-23',start:'09:00',end:'09:30',
        start_at:'2026-11-23T09:00:00+01:00',end_at:'2026-11-23T09:30:00+01:00',source_managed:true,source_editable:sourceEditEnabled,status:'confirmed'}],
      blocks:[
        {id:90,staff_id:1,editable:false,source_managed:true,date:'2026-11-23',start:'12:00',end:'13:00',
          kind:'block',text:'Synced SimplyBook note',start_at:'2026-11-23T12:00:00+01:00',end_at:'2026-11-23T13:00:00+01:00'},
        {id:91,staff_id:1,editable:false,source_managed:false,date:'2026-11-23',start:'13:00',end:'14:00',
          kind:'note',text:'Legacy Book note',start_at:'2026-11-23T13:00:00+01:00',end_at:'2026-11-23T14:00:00+01:00'},
      ],availability:[]
    };
  }
  else if(path.endsWith('/patients/'))result={items:[{id:23,name:'Demo patient',email:'demo@example.test'}]};
  else if(path.endsWith('/patient/23/'))result={patient:{id:23,name:'Demo patient',email:'demo@example.test'},appointments:[],records:[]};
  else if(path.endsWith('/customers/'))result={items:[]};
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
assert.equal(current.tabs.filter(t=>t.selected).length,1);
assert.equal(current.tabs.find(t=>t.selected).id,'home');
assert.ok(current.tabs.some(t=>t.id==='office'));
await click('calendar');
assert.equal(current.week.length,7);
assert.equal(current.tabs.find(t=>t.selected).id,'calendar');
assert.equal(current.timeline.mode,'day','native calendar must be a real time grid');
assert.equal(current.timeline.columns.length,1);
assert.equal(current.timeline.firstHour,0);
assert.equal(current.timeline.lastHour,24);
assert.equal(current.timeline.providers.length,2);
assert.ok(current.timeline.events.some(e=>e.id==='block-info:90'));
await click('block-info:90');
assert.match(current.message,/SimplyBook/);
assert.ok(!current.actions.some(x=>x.id==='save-block-edit'));
await click('calendar');
await click('block-info:91');
assert.match(current.message,/Book administration/);
await click('calendar');
await click('new-appointment');
assert.ok(!current.fields.find(f=>f.id==='staff_id').options.some(o=>o.value==='2'),'imported provider unavailable for local booking');
assert.ok(!current.fields.find(f=>f.id==='service_id').options.some(o=>o.value==='2'),'imported service unavailable for local booking');
await click('calendar');
await click('new-block');
assert.ok(!current.fields.find(f=>f.id==='staff_id').options.some(o=>o.value==='2'),'imported provider unavailable for local blocks');
await click('calendar');
await click('settings');
await click('services');
await click('service:2');
assert.match(current.message,/SimplyBook/);
assert.ok(!current.actions.some(a=>a.id==='save-service'));
await click('calendar');
await click('availability');
await click('load-availability',{staff_id:'2',date:'2026-11-23'});
assert.match(current.message,/SimplyBook/);
assert.ok(!current.actions.some(a=>a.id==='save-availability'));
await click('calendar');
await click('appointment:44');
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
await click('office');
assert.equal(current.tabs.find(t=>t.selected).id,'office');
assert.ok(current.rows.some(x=>x.id==='billing-settings'));
await click('billing-settings');
assert.equal(current.title,'Invoice settings');
assert.ok(current.fields.some(x=>x.id==='next_sequence'&&x.kind==='integer'));
const settingsInput=Object.fromEntries(current.fields.map(field=>[field.id,field.value]));
await click('save-billing-settings',settingsInput);
assert.equal(lastFinancialUpdate.revision,'v1','uses form revision instead of silently refreshing');
assert.equal(lastFinancialUpdate.confirmed_financial_update,true);
await click('patients');
await click('patient:23');
assert.equal(current.title,'Demo patient');
assert.equal(current.tabs.find(t=>t.selected).id,'patients');
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
console.log('PASS: native controller, calendar swipes, bilingual switching, audited Office settings, medical notes and role tabs');
