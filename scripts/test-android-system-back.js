/* Run with: node scripts/test-android-system-back.js */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('www/core-app.js', 'utf8');
const begin = source.indexOf('  function handleNativeBack(){');
const end = source.indexOf('\n  function registerNativeBackButton()', begin);
assert(begin >= 0 && end > begin, 'Android system Back handler must exist');
const makeHandler = new Function('document', 'state', 'routeHistory', 'go', 'window',
  source.slice(begin, end) + '\nreturn handleNativeBack;');

function scenario({route='appointments',history=[],elements={}} = {}) {
  const calls = [];
  const exit = () => calls.push('exit');
  const go = (target,options) => calls.push(['go',target,options]);
  const state = {route,token:'test-token',me:{id:1}};
  const document = {querySelector(selector){return elements[selector]||null;}};
  const handler = makeHandler(document,state,history,go,{Capacitor:{Plugins:{App:{exitApp:exit}}}});
  handler();
  return {calls,history};
}

assert.deepEqual(scenario({route:'appointments'}).calls,[['go','dashboard',{fromBack:true}]]);
assert.deepEqual(scenario({route:'records',history:['dashboard','points']}).calls,[['go','points',{fromBack:true}]]);
assert.deepEqual(scenario({route:'dashboard'}).calls,['exit']);
let closed=0;
assert.deepEqual(scenario({elements:{
  '.settings-overlay':{querySelector(){return {click(){closed++;}};}}
}}).calls,[]);
assert.equal(closed,1);
let previousStep=0;
assert.deepEqual(scenario({elements:{
  '.book-step.is-active[data-book-step]':{dataset:{bookStep:'3'},querySelector(){return {click(){previousStep++;}};}}
}}).calls,[]);
assert.equal(previousStep,1);
let cancelled=0;
assert.deepEqual(scenario({elements:{
  '.book-cancel-confirm:not([hidden])':{querySelector(){return {click(){cancelled++;}};}}
}}).calls,[]);
assert.equal(cancelled,1);
console.log('Android system Back route, overlay, cancellation and booking-step tests passed.');
