(() => {
  'use strict';

  const API = 'https://esthetic.smarbiz.sbs/api/mobile';
  const LEGAL = {
    privacy: 'https://esthetic.smarbiz.sbs/datenschutz/',
    terms: 'https://esthetic.smarbiz.sbs/nutzungsbedingungen/',
    imprint: 'https://esthetic.smarbiz.sbs/impressum/',
    deletion: 'https://esthetic.smarbiz.sbs/konto-loeschen/',
  };
  const routes = [
    ['appointments', '◫', 'Termine'],
    ['reviews', '★', 'Bewertungen'],
    ['friends', '↗', 'Freunde'],
    ['wallet', '€', 'Wallet'],
    ['records', '▤', 'Akte'],
  ];
  const state = { route: 'appointments', token: localStorage.getItem('aplus_token') || '', me: null, cache: {}, selectedSlot: '' };
  const root = document.getElementById('app');

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const money = cents => new Intl.NumberFormat('de-DE', {style:'currency', currency:'EUR'}).format((Number(cents)||0)/100);
  const fmt = value => value ? new Intl.DateTimeFormat('de-DE',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : '—';
  const dateBits = value => {
    const d = new Date(value); return {day:d.toLocaleDateString('de-DE',{day:'2-digit'}), month:d.toLocaleDateString('de-DE',{month:'short'}), full:d.toLocaleDateString('de-DE',{weekday:'short',day:'2-digit',month:'2-digit'}), time:d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})};
  };
  const isPast = a => new Date(a.starts_at).getTime() < Date.now() || ['cancelled','completed','done'].includes(String(a.status_code||'').toLowerCase());

  async function request(path, options={}) {
    const headers = new Headers(options.headers || {});
    if (state.token) headers.set('Authorization', `Bearer ${state.token}`);
    if (options.json !== undefined) { headers.set('Content-Type','application/json'); options.body = JSON.stringify(options.json); }
    const response = await fetch(`${API}${path}`, {...options, headers});
    if (response.status === 401) { logout(false); throw new Error('authentication_required'); }
    const type = response.headers.get('content-type') || '';
    const data = type.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok || data?.ok === false) {
      const error = new Error(data?.message || data?.error || `HTTP ${response.status}`); error.code=data?.error; throw error;
    }
    return data;
  }

  function loader() { return '<div class="loader"><div><div class="spinner"></div>Laden …</div></div>'; }
  function errorBox(err) { return `<div class="notice error">${esc(err?.message || 'Etwas ist schiefgelaufen. Bitte erneut versuchen.')}</div>`; }
  function pageHead(kicker,title,subtitle='') { return `<div class="page-head"><div class="eyebrow">${esc(kicker)}</div><h1>${esc(title)}</h1>${subtitle?`<p>${esc(subtitle)}</p>`:''}</div>`; }

  function shell(content) {
    const email = state.me?.profile?.email || '';
    root.innerHTML = `<div class="core-shell">
      <header class="core-header"><span class="core-header-spacer"></span><div class="core-brand"><strong>${state.route==='records'?'Patientenakte':'A+ Esthetic'}</strong><span>${state.route==='appointments'?'TERMINBUCHUNG':'A+ ESTHETIC'}</span></div><button class="core-icon-btn" data-settings aria-label="Einstellungen">⚙</button></header>
      <main class="core-main">${content}</main>
      <nav class="core-nav">${routes.map(([key,icon,label])=>`<button class="nav-btn ${state.route===key?'is-active':''}" data-route="${key}"><span>${icon}</span><span>${label}</span></button>`).join('')}</nav>
    </div>`;
    root.querySelectorAll('[data-route]').forEach(btn=>btn.addEventListener('click',()=>go(btn.dataset.route)));
    root.querySelector('[data-settings]')?.addEventListener('click',()=>showSettings(email));
  }

  function showSettings(email) {
    const node=document.createElement('div'); node.className='settings-overlay';
    node.innerHTML=`<div class="settings-card"><div class="settings-head"><h2>Einstellungen & Recht</h2><button class="core-icon-btn" data-close>×</button></div>
      <div class="settings-user"><strong>${esc(state.me?.member?.name || 'A+ Kunde')}</strong><span>${esc(email)}</span></div>
      <a class="settings-link" href="${LEGAL.privacy}" target="_blank" rel="noopener">Datenschutz <span>›</span></a>
      <a class="settings-link" href="${LEGAL.terms}" target="_blank" rel="noopener">Nutzungsbedingungen <span>›</span></a>
      <a class="settings-link" href="${LEGAL.imprint}" target="_blank" rel="noopener">Impressum <span>›</span></a>
      <a class="settings-link" href="${LEGAL.deletion}" target="_blank" rel="noopener">Konto löschen <span>›</span></a>
      <button class="danger wide" data-logout style="margin-top:18px">Abmelden</button></div>`;
    document.body.appendChild(node);
    const close=()=>node.remove(); node.addEventListener('click',e=>{if(e.target===node)close()}); node.querySelector('[data-close]').onclick=close; node.querySelector('[data-logout]').onclick=()=>logout();
  }

  function logout(render=true) { localStorage.removeItem('aplus_token'); state.token=''; state.me=null; state.cache={}; if(render) showLogin(); }

  function showLogin(message='') {
    root.innerHTML=`<div class="login-shell"><form class="login-card" data-login><div class="login-logo"><strong>A+ Esthetic</strong><span>PATIENT APP</span></div><h1>Anmelden</h1><p>Termine, A+ Guthaben und Patientenakte an einem Ort.</p>${message?`<div class="notice error">${esc(message)}</div>`:''}<label class="field"><span>E-Mail</span><input name="email" type="email" autocomplete="username" required></label><label class="field"><span>Passwort</span><input name="password" type="password" autocomplete="current-password" required></label><button class="primary wide" type="submit">Anmelden</button></form></div>`;
    root.querySelector('[data-login]').addEventListener('submit', async e=>{
      e.preventDefault(); const btn=e.currentTarget.querySelector('button'); btn.disabled=true; btn.textContent='Anmeldung …';
      try { const fd=new FormData(e.currentTarget); const data=await request('/login/',{method:'POST',json:{email:fd.get('email'),password:fd.get('password')}}); state.token=data.token; localStorage.setItem('aplus_token',state.token); await boot(); }
      catch(err){ showLogin(err.code==='invalid_credentials'?'E-Mail oder Passwort ist nicht korrekt.':err.message); }
    });
  }

  async function boot() {
    if (!state.token) return showLogin();
    try { state.me=await request('/me/'); go('appointments'); } catch(err) { if(state.token) showLogin(err.message); }
  }

  async function go(route) {
    if (!routes.some(r=>r[0]===route)) route='appointments'; state.route=route; shell(loader());
    try {
      if(route==='appointments') await renderAppointments();
      if(route==='reviews') await renderReviews();
      if(route==='friends') await renderFriends();
      if(route==='wallet') await renderWallet();
      if(route==='records') await renderRecords();
    } catch(err) { shell(`${pageHead('A+ Esthetic','Fehler')} ${errorBox(err)}`); }
  }

  async function renderAppointments() {
    const data=await request('/booking/'); state.cache.booking=data;
    const all=Array.isArray(data.appointments)?data.appointments:[];
    const upcoming=all.filter(a=>!isPast(a)&&a.status_code!=='cancelled').sort((a,b)=>new Date(a.starts_at)-new Date(b.starts_at));
    const previous=all.filter(a=>isPast(a)||a.status_code==='cancelled').sort((a,b)=>new Date(b.starts_at)-new Date(a.starts_at));
    const next=upcoming[0];
    let html=pageHead('Termine','Ihre Termine','Neue Termine buchen und bisherige Behandlungen im Blick behalten.');
    if(next){const d=dateBits(next.starts_at);html+=`<section class="card appointment-feature"><div class="eyebrow">Nächster Termin</div><div class="appointment-time">${d.full} · ${d.time}</div><div class="appointment-meta">${esc(next.service)} · ${esc(next.staff)}</div></section>`;}
    html+=`<section class="card"><div class="section-title" style="margin-top:0"><h2>Neuen Termin buchen</h2></div><form data-booking><label class="field"><span>Behandlung</span><select name="service_id" required><option value="">Bitte wählen …</option>${(data.services||[]).map(s=>`<option value="${s.id}">${esc(s.name)}${s.price_label?` · ${esc(s.price_label)}`:''}</option>`).join('')}</select></label><label class="field"><span>Datum</span><input name="day" type="date" min="${new Date().toISOString().slice(0,10)}" required></label><div data-slots></div><input type="hidden" name="starts_at"><button class="primary wide" type="submit" disabled>Termin buchen</button></form></section>`;
    html+=`<div class="section-title"><h2>Bevorstehend</h2><small>${upcoming.length}</small></div>${upcoming.length?upcoming.map(appointmentRow).join(''):'<div class="empty">Keine weiteren Termine.</div>'}`;
    html+=`<div class="section-title"><h2>Vergangene Termine</h2><small>${previous.length}</small></div>${previous.length?previous.map(appointmentRow).join(''):'<div class="empty">Noch keine früheren Termine.</div>'}`;
    shell(html); bindBookingForm();
  }

  function appointmentRow(a){const d=dateBits(a.starts_at);const code=String(a.status_code||'').toLowerCase();return `<article class="appointment-row"><div class="date-box"><b>${d.day}</b><span>${d.month}</span></div><div><div class="row-title">${esc(a.service)}</div><div class="row-sub">${d.time} · ${esc(a.staff)}</div><span class="status ${code}">${esc(a.status)}</span></div></article>`;}

  function bindBookingForm(){
    const form=root.querySelector('[data-booking]'); if(!form)return; const service=form.elements.service_id,day=form.elements.day,hidden=form.elements.starts_at,slots=form.querySelector('[data-slots]'),submit=form.querySelector('button[type=submit]');
    const load=async()=>{hidden.value='';submit.disabled=true;state.selectedSlot='';if(!service.value||!day.value){slots.innerHTML='';return;}slots.innerHTML='<div class="loader" style="min-height:80px"><div><div class="spinner"></div></div></div>';try{const data=await request(`/slots/?service_id=${encodeURIComponent(service.value)}&day=${encodeURIComponent(day.value)}`);const values=data.slots||[];slots.innerHTML=values.length?`<div class="field"><span>Uhrzeit</span><div class="slot-grid">${values.map(v=>`<button type="button" class="slot" data-slot="${esc(v)}">${dateBits(v).time}</button>`).join('')}</div></div>`:'<div class="notice">An diesem Tag ist kein freier Termin verfügbar.</div>';slots.querySelectorAll('[data-slot]').forEach(btn=>btn.onclick=()=>{slots.querySelectorAll('.slot').forEach(x=>x.classList.remove('is-selected'));btn.classList.add('is-selected');hidden.value=btn.dataset.slot;submit.disabled=false;});}catch(err){slots.innerHTML=errorBox(err);}};
    service.onchange=load; day.onchange=load; form.onsubmit=async e=>{e.preventDefault();if(!hidden.value)return;submit.disabled=true;submit.textContent='Wird gebucht …';try{await request('/booking/',{method:'POST',json:{service_id:Number(service.value),starts_at:hidden.value}});await renderAppointments();}catch(err){submit.disabled=false;submit.textContent='Termin buchen';slots.insertAdjacentHTML('afterend',errorBox(err));}};
  }

  async function renderReviews(){
    const data=await request('/reviews/');const items=data.activities||[];
    let html=pageHead('Google','Bewertungen','Google-Bewertung abgeben und bisherige Bewertungsaktivitäten sehen.');
    html+=`<section class="review-cta"><div class="eyebrow">Google Bewertung</div><h2 style="font:500 27px Georgia,serif;margin:9px 0 7px">Erfahrung teilen</h2><p class="row-sub" style="margin-bottom:14px">Die Bewertung wird direkt bei Google abgegeben. A+ speichert nur den Status in Ihrer App-Historie.</p><button class="primary wide" data-open-review>Bei Google bewerten</button></section>`;
    html+=`<section class="card"><h2 style="margin-bottom:14px">Bewertung eintragen</h2><form data-review-submit><label class="field"><span>Sterne (optional)</span><select name="rating"><option value="">Nicht angeben</option>${[5,4,3,2,1].map(n=>`<option value="${n}">${'★'.repeat(n)}</option>`).join('')}</select></label><label class="field"><span>Notiz für Ihre Historie (optional)</span><textarea name="review_text" placeholder="Kurze Notiz …"></textarea></label><button class="secondary wide">Als abgegeben markieren</button></form></section>`;
    html+=`<div class="section-title"><h2>Ihre Historie</h2><small>${items.length}</small></div>${items.length?items.map(r=>`<article class="review-row"><div class="review-row-head"><strong>${r.rating?`${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}`:'Google Bewertung'}</strong><span class="status ${r.status}">${esc(r.status_label)}</span></div>${r.review_text?`<div class="row-sub">${esc(r.review_text)}</div>`:''}<div class="row-sub">${fmt(r.submitted_at||r.opened_at||r.created_at)}</div>${r.google_review_url?`<a class="text-btn" href="${esc(r.google_review_url)}" target="_blank" rel="noopener">Auf Google öffnen</a>`:''}</article>`).join(''):'<div class="empty">Noch keine Bewertungsaktivität gespeichert.</div>'}`;
    shell(html);
    root.querySelector('[data-open-review]').onclick=async()=>{try{await request('/reviews/',{method:'POST',json:{action:'opened'}});}catch(_){}window.open(data.review_url,'_blank','noopener');};
    root.querySelector('[data-review-submit]').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.currentTarget);try{await request('/reviews/',{method:'POST',json:{action:'submitted',rating:fd.get('rating')||null,review_text:fd.get('review_text')||''}});await renderReviews();}catch(err){e.currentTarget.insertAdjacentHTML('beforebegin',errorBox(err));}};
  }

  async function renderFriends(){
    const data=await request('/club/');const refs=data.referrals||[];
    let html=pageHead('Empfehlungen','Freunde einladen','Eine persönliche Empfehlung direkt per E-Mail senden.');
    html+=`<section class="card"><h2 style="margin-bottom:14px">Freund/in empfehlen</h2><form data-referral><label class="field"><span>E-Mail</span><input name="invited_email" type="email" placeholder="name@example.com" required></label><button class="primary wide">Einladung senden</button></form></section>`;
    html+=`<div class="section-title"><h2>Bisherige Einladungen</h2><small>${refs.length}</small></div>${refs.length?refs.map(r=>`<article class="referral-row"><strong>${esc(r.email)}</strong><div class="row-sub">Code ${esc(r.code)}</div><span class="status ${esc(r.status)}">${esc(r.status)}</span></article>`).join(''):'<div class="empty">Noch keine Empfehlungen.</div>'}`;
    shell(html);root.querySelector('[data-referral]').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.currentTarget);try{await request('/club/',{method:'POST',json:{invited_email:fd.get('invited_email')}});await renderFriends();}catch(err){e.currentTarget.insertAdjacentHTML('beforebegin',errorBox(err));}};
  }

  async function renderWallet(){
    const data=await request('/wallet/');const tx=(data.transactions||[]).filter(x=>x.kind==='credit');
    let html=pageHead('A+ Guthaben','Wallet','Ihr persönliches A+ Guthaben und alle Änderungen transparent im Verlauf.');
    html+=`<section class="card wallet-hero"><small>A+ Guthaben</small><div class="wallet-balance">${money(data.balance_cents)}</div><p>Verfügbares Guthaben</p></section>`;
    html+=`<div class="section-title"><h2>Verlauf</h2><small>${tx.length}</small></div>${tx.length?tx.map(t=>{const amount=Number(t.amount_cents)||0;const plus=t.direction==='credit';return `<article class="wallet-row"><div><strong>${esc(t.description||'Guthaben')}</strong><div class="row-sub">${fmt(t.created_at)}</div></div><div class="wallet-amount ${plus?'plus':'minus'}">${plus?'+':'−'} ${money(Math.abs(amount))}</div></article>`}).join(''):'<div class="empty">Noch keine Guthabenbewegungen.</div>'}`;
    shell(html);
  }

  async function renderRecords(){
    const data=await request('/patient-records/');const records=(data.records||[]).sort((a,b)=>new Date(b.captured_at||b.created_at)-new Date(a.captured_at||a.created_at));
    let html=pageHead('Patientenakte','Ihre Akte','Dokumente und Notizen chronologisch – von Ihnen und der Praxis.');
    html+=`<section class="upload-box"><form data-upload enctype="multipart/form-data"><div class="grid-2"><label class="field"><span>Typ</span><select name="kind">${(data.upload?.kinds||[{value:'document',label:'Dokument'},{value:'photo',label:'Foto'},{value:'note',label:'Notiz'}]).map(k=>`<option value="${esc(k.value)}">${esc(k.label)}</option>`).join('')}</select></label><label class="field"><span>Titel</span><input name="title" placeholder="z. B. Laborbericht"></label></div><label class="field"><span>Datei</span><input name="file" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,.doc,.docx,.xls,.xlsx,.txt,.rtf,.csv"></label><label class="field"><span>Notiz (optional)</span><textarea name="note" placeholder="Zusätzliche Information …"></textarea></label>${!data.health_data_consent?`<label class="consent"><input name="health_data_consent" type="checkbox" value="1" required><span>Ich willige ein, dass diese Gesundheitsdaten zur Behandlung und Dokumentation in meiner Patientenakte verarbeitet werden.</span></label>`:'<input type="hidden" name="health_data_consent" value="1">'}<button class="primary wide">In Akte speichern</button></form></section>`;
    html+=`<div class="section-title"><h2>Verlauf</h2><small>${records.length}</small></div>${records.length?records.map(recordRow).join(''):'<div class="empty">Ihre Patientenakte enthält noch keine Einträge.</div>'}`;
    shell(html);bindRecordActions();
  }

  function recordRow(r){const source=r.customer_uploaded?'Von Ihnen':'Praxis';return `<article class="record-row"><div class="record-row-head"><div><div class="record-source">${source} · ${esc(r.kind_label||r.kind)}</div><strong>${esc(r.title||'Akteneintrag')}</strong></div><small class="row-sub">${fmt(r.captured_at||r.created_at)}</small></div>${r.appointment?`<div class="row-sub">Termin: ${esc(r.appointment.service)} · ${fmt(r.appointment.starts_at)}</div>`:''}${r.note?`<div class="row-sub">${esc(r.note)}</div>`:''}${r.has_file?`<div class="record-actions"><button class="secondary" data-record-file="${esc(r.id)}" data-download="0">Öffnen</button><button class="secondary" data-record-file="${esc(r.id)}" data-download="1">Download</button></div>`:''}</article>`;}

  function bindRecordActions(){
    const form=root.querySelector('[data-upload]');form.onsubmit=async e=>{e.preventDefault();const btn=form.querySelector('button');btn.disabled=true;btn.textContent='Wird gespeichert …';try{const headers=new Headers({'Authorization':`Bearer ${state.token}`});const response=await fetch(`${API}/patient-records/upload/`,{method:'POST',headers,body:new FormData(form)});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||'Upload fehlgeschlagen');await renderRecords();}catch(err){btn.disabled=false;btn.textContent='In Akte speichern';form.insertAdjacentHTML('beforebegin',errorBox(err));}};
    root.querySelectorAll('[data-record-file]').forEach(btn=>btn.onclick=async()=>{btn.disabled=true;try{const url=`${API}/patient-records/${encodeURIComponent(btn.dataset.recordFile)}/file/${btn.dataset.download==='1'?'?download=1':''}`;const response=await fetch(url,{headers:{Authorization:`Bearer ${state.token}`}});if(!response.ok)throw new Error('Datei konnte nicht geöffnet werden.');const blob=await response.blob();const object=URL.createObjectURL(blob);if(btn.dataset.download==='1'){const a=document.createElement('a');a.href=object;a.download='APlus-Dokument';document.body.appendChild(a);a.click();a.remove();}else{window.open(object,'_blank');}setTimeout(()=>URL.revokeObjectURL(object),60000);}catch(err){btn.insertAdjacentHTML('afterend',errorBox(err));}finally{btn.disabled=false;}});
  }

  boot();
})();
