// A+ Esthetic native admin calendar model. Pure transformation only; never writes Book.
import {shiftDay, startWeek, minutes} from './calendar.mjs';

const clamp = (value, low, high) => Math.min(high,Math.max(low,value));
const clock = value => /^\d\d:\d\d/.test(String(value||'')) ? String(value).slice(0,5) : '';
const startOf = item => ({
  date: String(item.start_at || '').slice(0,10) || item.date,
  time: clock(String(item.start_at||'').slice(11,16)) || clock(item.start),
});
const endOf = item => ({
  date: String(item.end_at || '').slice(0,10) || item.date,
  time: clock(String(item.end_at||'').slice(11,16)) || clock(item.end),
});
const spanFor = (item, day) => {
  const s = startOf(item), e = endOf(item);
  if (!day || !s.date || !e.date || day<s.date || day>e.date) return null;
  const lower = day===s.date ? minutes(s.time) : 0;
  const upper = day===e.date ? minutes(e.time) : 1440;
  return upper>lower ? {lower:clamp(lower,0,1440),upper:clamp(upper,0,1440)}:null;
};
const matching = (item, mode, col, provider, service) =>
  (provider === 'all' || String(item.staff_id)===provider) &&
  (service === 'all' || String(item.service_id)===service || item.kind) &&
  (mode==='week' ? item.date===col.date || Boolean(spanFor(item,col.date))
    : mode==='provider' ? String(item.staff_id)===String(col.ref)
    : mode==='service' ? String(item.service_id)===String(col.ref)
    : true);

// Pack overlapping bookings into equal-width lanes for visual fidelity.
// Connected components share a lane count; independent events use full width.
export function packCalendarLanes(items) {
  const ordered=[...items].sort((a,b)=>a.lower-b.lower || b.upper-a.upper || String(a.id).localeCompare(String(b.id)));
  let group=[], ends=[], result=[];
  function flush(){
    for(const entry of group) result.push({...entry,lanes:ends.length});
    group=[];ends=[];
  }
  for(const item of ordered){
    if(group.length && item.lower>=Math.max(...ends))flush();
    let lane=ends.findIndex(t=>t<=item.lower);
    if(lane===-1)lane=ends.length;
    ends[lane]=item.upper;
    group.push({...item,lane});
  }
  flush();
  return result;
}

export function buildNativeCalendarTimeline({date,mode='day',providers=[],services=[],
  provider='all',service='all',calendar={}}) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date))throw new Error('Invalid calendar day');
  if(!['day','week','provider','service'].includes(mode))throw new Error('Invalid calendar view');
  const weekStart=startWeek(date);
  const week=Array.from({length:7},(_,i)=>shiftDay(weekStart,i));
  const columns= mode==='week'
    ?week.map(day=>({id:day,date:day,title:day,ref:''}))
    :mode==='provider'
      ?providers.filter(p=>provider==='all'||String(p.id)===provider)
        .map(p=>({id:'staff:'+p.id,date,title:p.name,ref:String(p.id)}))
      :mode==='service'
        ?services.filter(s=>s.active && (service==='all'||String(s.id)===service))
          .map(s=>({id:'service:'+s.id,date,title:s.name,ref:String(s.id)}))
        :[{id:date,date,title:date,ref:''}];
  const events=[];
  const bands=[];
  const bookings=Array.isArray(calendar.appointments)?calendar.appointments:[];
  const blocks=Array.isArray(calendar.blocks)?calendar.blocks:[];
  const availability=Array.isArray(calendar.availability)?calendar.availability:[];
  for(const [index,col] of columns.entries()){
    const colEvents=[];
    for(const item of bookings){
      const span=spanFor(item,col.date);
      if(!span || !matching(item,mode,col,provider,service))continue;
      colEvents.push({
        id:'appointment:'+item.id,kind:'appointment',date:col.date,column:index,
        lower:span.lower,upper:span.upper,
        title:String(item.customer_name||''),detail:String(item.service_name||''),
        meta:String(item.staff_name||''),start:clock(item.start)||'',
        end:clock(item.end)||'',status:String(item.status||''),
      });
    }
    for(const item of blocks){
      const span=spanFor(item,col.date);
      if(!span || (provider!=='all' && String(item.staff_id)!==provider) ||
        (mode==='provider' && String(item.staff_id)!==col.ref) ||
        (mode==='service' && item.service_id && String(item.service_id)!==col.ref))continue;
      colEvents.push({
        id:(item.editable?'block:':'block-info:')+item.id,kind:item.kind==='note'?'note':'block',
        date:col.date,column:index,lower:span.lower,upper:span.upper,
        title:String(item.text||'').split('\u2063')[0].trim(),
        detail:item.kind==='note'?'Notiz':'Gesperrt',
        start:clock(item.start)||'',end:clock(item.end)||'',
      });
    }
    events.push(...packCalendarLanes(colEvents));
    for(const slot of availability){
      if(slot.date!==col.date || (provider!=='all'&&String(slot.staff_id)!==provider) ||
        (mode==='provider'&&String(slot.staff_id)!==col.ref)) continue;
      if(mode==='service'){
        const svc=services.find(s=>String(s.id)===col.ref);
        if(!svc || !providers.some(p=>p.id===slot.staff_id && (p.services||[]).includes(svc.id)))continue;
      }
      for(const range of slot.ranges||[]){
        const lower=minutes(range.start), upper=minutes(range.end);
        if(Number.isFinite(lower)&&Number.isFinite(upper)&&upper>lower)
          bands.push({column:index,lower,upper});
      }
    }
  }
  return {
    mode,date,weekStart,week,
    columns,events,bands,appointmentCount:events.filter(x=>x.kind==='appointment').length,
    // Preserve all-day visibility without hiding overnight appointments. Native starts
    // near morning but can scroll above/below working hours.
    firstHour:0,lastHour:24,provider,service,
    providers:providers.map(p=>({id:String(p.id),label:p.name})),
    services:services.filter(s=>s.active).map(s=>({id:String(s.id),label:s.name})),
  };
}
