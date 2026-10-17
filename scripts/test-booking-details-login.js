'use strict';
// Static interaction regressions that run in CI without a real patient account.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const booking=fs.readFileSync('www/booking-book-flow.js','utf8');
const core=fs.readFileSync('www/core-app.js','utf8');
const esc=x=>String(x??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function section(text,start,end){
  const a=text.indexOf(start),b=text.indexOf(end,a);
  assert(a>=0 && b>a,'Missing application section '+start);
  return text.slice(a,b);
}
const rows=new Function('Intl','Date','esc',
  section(booking,'  function appointmentRows(','\n  async function loadAvailability(')+'\nreturn appointmentRows;')(Intl,Date,esc);
const appointment={id:'abc',service:'Ästhetische Erstberatung',status:'Neu',status_code:'new',staff:'Q. Hameed',starts_at:'2027-01-01T10:00:00+01:00'};
const editable={change_deadline_hours:24,appointments:[{...appointment,change_allowed:true}]};
let html=rows([appointment],editable);
assert(html.includes('data-open-appointment="abc"'),'Each booking needs a details control');
assert(html.includes('aria-expanded="false"'),'Details must be accessible');
assert(html.includes('Termin stornieren'),'Eligible customers need a cancellation button');
assert(html.includes('wartet noch auf die Bestätigung'),'New status must be explained');
assert(html.includes('Q. Hameed'),'Doctor must be shown in details');
assert(!html.includes('data-cancel-confirmation hidden') || html.includes('data-open-appointment'),'Cancellation requires explicit intent');
html=rows([{...appointment,status:'Bestätigt',status_code:'confirmed'}],editable);
assert(html.includes('Dieser Termin wurde bestätigt'),'Confirmed status must be explained');
html=rows([{...appointment,status:'Abgesagt',status_code:'cancelled'}],{appointments:[]});
assert(!html.includes('data-start-cancel'),'Cancelled bookings cannot be cancelled again');
html=rows([appointment],null);
assert(html.includes('data-reload-cancellations'),'Failed permissions request must have a retry');

const callState={token:'stale',calls:[],notices:[]};
const loginRequest=new Function('Headers','fetch','state','logout','showLogin','API','setTimeout',
  section(core,'  async function request(','\n  function loader()')+'\nreturn request;')(
  Headers,
  async(url,options)=>{
    callState.calls.push({url,authorization:options.headers.get('Authorization')});
    return {status:401,ok:false,headers:{get:()=> 'application/json'},json:async()=>({ok:false,error:'invalid_credentials'})};
  },
  callState,
  ()=>callState.notices.push('logout'),
  msg=>callState.notices.push(msg),
  'https://app.a-esthetic.de/api/mobile',
  setTimeout
);
(async()=>{
  await assert.rejects(loginRequest('/login/',{method:'POST',json:{email:'invalid@example.de',password:'invalid'}}),
    err=>err.code==='invalid_credentials' && err.message.includes('Bitte überprüfe deine Eingaben'));
  assert.equal(callState.calls.length,1,'Do not retry failed credentials');
  assert.equal(callState.calls[0].authorization,null,'Old session token must not be sent on login');
  assert.deepEqual(callState.notices,[],'Wrong password must not be treated as expired session');
  assert(core.includes('Die E-Mail-Adresse oder das Passwort ist falsch. Bitte überprüfe deine Eingaben und versuche es erneut.'));
  console.log('Booking details, status descriptions, cancellation visibility and login 401 tests passed.');
})().catch(err=>{console.error(err);process.exitCode=1;});
