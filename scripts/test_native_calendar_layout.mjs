import assert from 'node:assert/strict';
import {buildNativeCalendarTimeline, packCalendarLanes} from '../www/mobile/native-calendar-layout.mjs';

const providers=[
  {id:1,name:'Doctor A',services:[10,11]},
  {id:2,name:'Doctor B',services:[10]},
];
const services=[
  {id:10,name:'Consultation',active:true},
  {id:11,name:'Laser',active:true},
];
const appointment=(id,day,from,to,staff=1,service=10)=>({
  id,staff_id:staff,service_id:service,customer_name:'TEST-'+id,
  service_name:service===10?'Consultation':'Laser',staff_name:staff===1?'Doctor A':'Doctor B',
  date:day,start:from,end:to,
  start_at:day+'T'+from+':00+01:00',end_at:day+'T'+to+':00+01:00',
  status:'confirmed',
});
const calendar={
  appointments:[
    appointment(1,'2026-11-23','09:00','10:00'),
    appointment(2,'2026-11-23','09:30','10:30',2,10),
    appointment(3,'2026-11-23','12:00','12:45',1,11),
    appointment(4,'2026-11-24','09:15','10:00',1,10),
    appointment(5,'2026-11-29','14:00','15:00',1,11),
  ],
  blocks:[
    {id:90,kind:'note',editable:true,text:'TEST NOTE',staff_id:1,
      start_at:'2026-11-23T11:00:00+01:00',end_at:'2026-11-23T11:30:00+01:00'},
    {id:91,kind:'block',editable:false,text:'TEST BREAK',staff_id:2,
      start_at:'2026-11-23T13:00:00+01:00',end_at:'2026-11-23T13:45:00+01:00'},
  ],
  availability:[
    {date:'2026-11-23',staff_id:1,ranges:[{start:'08:00',end:'17:00'}]},
    {date:'2026-11-23',staff_id:2,ranges:[{start:'09:00',end:'18:00'}]},
  ],
};
const model=(mode, provider='all',service='all',date='2026-11-23')=>
  buildNativeCalendarTimeline({date,mode,providers,services,provider,service,calendar});
const day=model('day');
assert.equal(day.mode,'day');
assert.equal(day.weekStart,'2026-11-23');
assert.equal(day.columns.length,1);
assert.equal(day.events.filter(e=>e.kind==='appointment').length,3);
assert.equal(day.events.find(e=>e.id==='appointment:1').lower,540);
assert.equal(day.events.find(e=>e.id==='appointment:1').upper,600);
assert.equal(day.events.find(e=>e.id==='appointment:1').lanes,2);
assert.equal(day.events.find(e=>e.id==='appointment:2').lanes,2);
assert.notEqual(day.events.find(e=>e.id==='appointment:1').lane,
  day.events.find(e=>e.id==='appointment:2').lane);
assert.equal(day.events.find(e=>e.id==='appointment:3').lanes,1);
assert.equal(day.events.find(e=>e.id==='block:90').kind,'note');
assert.equal(day.events.filter(e=>e.kind==='block')[0].id,'');
assert.equal(day.bands.length,2);
const week=model('week');
assert.equal(week.columns.length,7);
assert.deepEqual(week.week,['2026-11-23','2026-11-24','2026-11-25','2026-11-26','2026-11-27','2026-11-28','2026-11-29']);
assert.equal(week.events.find(e=>e.id==='appointment:4').column,1);
assert.equal(week.events.find(e=>e.id==='appointment:5').column,6);
const providerView=model('provider');
assert.equal(providerView.columns.length,2);
assert.equal(providerView.events.find(e=>e.id==='appointment:2').column,1);
assert.equal(model('provider','1').columns.length,1);
assert.equal(model('service').columns.length,2);
assert.equal(model('service','all','11').events.filter(e=>e.kind==='appointment').length,1);
assert.equal(model('day','2').events.filter(e=>e.kind==='appointment').length,1);
assert.equal(model('week','all','11').events.filter(e=>e.kind==='appointment').length,2);
assert.equal(packCalendarLanes([
  {id:'A',lower:540,upper:580},
  {id:'B',lower:580,upper:600},
]).every(e=>e.lanes===1),true,'touching appointments are not overlapping');
const midnight = buildNativeCalendarTimeline({
  date:'2026-11-23',mode:'week',providers,services,calendar:{
    appointments:[{...appointment(12,'2026-11-23','23:30','00:30'),
      end_at:'2026-11-24T00:30:00+01:00'}],
  },
});
assert.equal(midnight.events.length,2);
assert.equal(midnight.events[0].upper,1440);
assert.equal(midnight.events[1].lower,0);
assert.throws(()=>model('bad'),/Invalid calendar view/);
console.log('PASS native calendar timeline: day/week/provider/service, real hour geometry, lanes, notes, blocks, availability, midnight, filters');
