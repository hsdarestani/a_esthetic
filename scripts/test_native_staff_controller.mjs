import assert from 'node:assert/strict';
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
let lastCalendar;
globalThis.fetch=async(url,opts)=>{
  assert.match(opts.headers.Authorization,/^Bearer synthetic-test-token$/);
  const path=new URL(url).pathname;
  let result;
  if(path.endsWith('/overview/'))result={today:0,upcoming:[]};
  else if(path.endsWith('/catalog/'))result={providers:[{id:1,name:'Demo clinician'}],services:[{id:1,name:'Consult',active:true}]};
  else if(path.endsWith('/calendar/')){lastCalendar=new URL(url).searchParams.get('start');result={appointments:[],blocks:[],availability:[]};}
  else if(path.endsWith('/patients/'))result={items:[{id:23,name:'Demo patient',email:'demo@example.test'}]};
  else if(path.endsWith('/patient/23/'))result={patient:{id:23,name:'Demo patient',email:'demo@example.test'},appointments:[],records:[]};
  else if(path.endsWith('/customers/'))result={items:[]};
  else throw Error('Unexpected endpoint '+path);
  return {ok:true,json:async()=>result};
};
const pause=()=>new Promise(r=>setTimeout(r,20));
const click=async(id,values={})=>{onAction({id,values});await pause();};
let native=await mountNativeWorkspace({token:'synthetic-test-token',identity:{role:'admin',name:'Demo Admin'},
  origin:'https://example.test',logout:()=>{}});
assert.equal(current.title,'Welcome');
assert.ok(current.tabs.some(t=>t.id==='office'));
await click('calendar');
assert.equal(current.week.length,7);
const previous=lastCalendar;
await click('week-next');
assert.notEqual(lastCalendar,previous);
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
await click('patients');
await click('patient:23');
assert.equal(current.title,'Demo patient');
await native.destroy();
assert.ok(closed);
native=await mountNativeWorkspace({token:'synthetic-test-token',identity:{role:'doctor',name:'Demo Doctor'},
  origin:'https://example.test',logout:()=>{}});
assert.ok(!current.tabs.some(t=>t.id==='office'));
await native.destroy();
console.log('PASS: native controller dispatch, week navigation, immediate bilingual switching, patient details and role tabs');
