'use strict';
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

const source = readFileSync('www/core-app.js','utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));

test('foreground events leave a mounted native workspace alone even if its web root is empty', async () => {
  const events = new Map();
  const count = {resolve:0,mount:0,login:0};
  const root = {
    innerHTML:'',
    get firstElementChild(){return this.innerHTML ? {} : null;},
    querySelector(selector){return this.innerHTML.includes(selector.slice(1,-1)) ? {addEventListener(){}} : null;},
  };
  const window = {
    APlusRuntime:{origin:'https://example.test'},
    APlusAuth:{login(){count.login++;}},
    APlusAdminMode:{
      async resolve(){count.resolve++;return {role:'admin'};},
      async mount(){count.mount++;},
    },
    Capacitor:{getPlatform:()=> 'android', Plugins:{App:{
      addListener(name,fn){events.set(name,fn);},
    }}},
    addEventListener(name,fn){events.set(name,fn);},
  };
  const document = {
    getElementById(){return root;},
    addEventListener(name,fn){events.set(name,fn);},
    visibilityState:'visible',
  };
  const localStorage = {getItem:key=>key==='aplus_token'?'synthetic-session':null};
  vm.runInNewContext(source,{window,document,localStorage});
  await settle();
  assert.deepEqual(count,{resolve:1,mount:1,login:0});
  events.get('appStateChange')?.({isActive:true});
  await settle();
  root.innerHTML='';
  events.get('visibilitychange')?.();
  await settle();
  events.get('pageshow')?.({persisted:true});
  await settle();
  assert.deepEqual(count,{resolve:1,mount:1,login:0});
});

test('customer recreation restores the route and Back history, and sign-out clears its checkpoint',async()=>{
  const events=new Map();
  const storage=new Map([['aplus_token','synthetic-customer-session']]);
  const requests=[];
  let cleared=0,login=0;
  const root={
    innerHTML:'',
    querySelector(){return null;},
    querySelectorAll(){return [];},
  };
  const document={
    getElementById:()=>root,addEventListener:(name,fn)=>events.set(name,fn),
    querySelector:()=>null,querySelectorAll:()=>[],visibilityState:'visible',
  };
  const window={
    APlusRuntime:{origin:'https://example.test'},AEstheticIconSet:{},
    APlusAuth:{login(){login++;}},APlusAdminMode:{resolve:async()=>({role:'customer'}),back:()=>false,unmount(){}},
    APlusNativeStaff:{
      async readNavigation({scope,session}){
        assert.equal(scope,'customer');assert.match(session,/^[a-f0-9]{64}$/);
        return {state:{route:'appointments',history:['dashboard'],scroll:91}};
      },
      async saveNavigation(){},async clearNavigation(){cleared++;},
    },
    Capacitor:{getPlatform:()=> 'android',Plugins:{App:{addListener:(name,fn)=>events.set(name,fn)}}},
    location:{search:''},addEventListener:(name,fn)=>events.set(name,fn),
    scrollTo(x,y){this.scrollY=y;},
  };
  const fetch=async url=>{
    const path=new URL(url).pathname;
    requests.push(path);
    return new Response(JSON.stringify(path.endsWith('/me/')?{profile:{first_name:'Synthetic'}}:{appointments:[]}),
      {headers:{'Content-Type':'application/json'}});
  };
  vm.runInNewContext(source,{window,document,fetch,crypto,TextEncoder,URLSearchParams,Headers,AbortController,setTimeout,clearTimeout,
    localStorage:{getItem:key=>storage.get(key),removeItem:key=>storage.delete(key)}});
  // WebCrypto navigation hashing runs on a worker thread. A fixed number of
  // setImmediate turns can expire before that worker is scheduled on CI.
  const deadline=Date.now()+3000;
  while(!root.innerHTML.includes('booking-form')&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,10));
  assert.match(root.innerHTML,/booking-form/);
  assert.equal(window.scrollY,91);
  events.get('pageshow')?.({persisted:true});
  events.get('appStateChange')?.({isActive:true});
  await settle();
  assert.equal(requests.filter(path=>path.endsWith('/booking/')).length,1);
  window.APlusNativeBack();
  await settle();
  assert.match(root.innerHTML,/route-dashboard/);
  window.APlusSignOut();
  assert.equal(storage.has('aplus_token'),false);
  assert.equal(cleared,1);
  assert.equal(login,1);
});

test('admin workspace has one owner through duplicate mounts and session replacement',async()=>{
  const adminSource=readFileSync('www/admin-mode.js','utf8');
  let finish,created=0,destroyed=0,cancelled=0;
  const window={APlusRuntime:{origin:'https://example.test'}};
  const createWorkspace=(_root,_token,_role,_logout,{signal})=>{
    created++;
    signal.addEventListener('abort',()=>cancelled++);
    return new Promise(resolve=>{finish=()=>resolve({destroy(){destroyed++;}});});
  };
  const controllerOnly=adminSource.slice(0,adminSource.indexOf('  async function createWorkspace('))+'})();';
  vm.runInNewContext(controllerOnly,{window,location:{search:''},URLSearchParams,AbortController,createWorkspace});
  const admin=window.APlusAdminMode;
  const first=admin.mount({},'session-one',{role:'admin'},()=>{});
  assert.equal(admin.mount({},'session-one',{role:'admin'},()=>{}),first);
  await settle();
  assert.equal(created,1);
  const second=admin.mount({},'session-two',{role:'admin'},()=>{});
  assert.equal(cancelled,1);
  assert.equal(created,1);
  finish();
  await first;
  await settle();
  assert.equal(destroyed,1);
  assert.equal(created,2);
  finish();
  await second;
  await admin.unmount();
  assert.equal(destroyed,2);
});
