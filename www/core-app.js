(() => {
  'use strict';

  const API = 'https://esthetic.smarbiz.sbs/api/mobile';
  const LEGAL = {
    privacy: 'https://esthetic.smarbiz.sbs/datenschutz/',
    terms: 'https://esthetic.smarbiz.sbs/nutzungsbedingungen/',
    imprint: 'https://esthetic.smarbiz.sbs/impressum/',
    deletion: 'https://esthetic.smarbiz.sbs/konto-loeschen/',
  };
  const CONTACT = {
    phone: '+496971417012',
    phoneLabel: '069 71417012',
    whatsapp: '+491729907936',
    instagram: 'https://www.instagram.com/aplus.esthetic/',
  };
  const routes = [
    ['dashboard', '⌂', 'Dashboard'],
    ['appointments', '◫', 'Reservieren'],
    ['records', '▤', 'Akte'],
    ['points', '◆', 'Punkte'],
    ['friends', '↗', 'Freunde'],
  ];
  const state = { route: 'dashboard', token: localStorage.getItem('aplus_token') || '', me: null, cache: {} };
  const root = document.getElementById('app');

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const fmt = value => value ? new Intl.DateTimeFormat('de-DE',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : '—';
  const dateBits = value => { const d=new Date(value); return {day:d.toLocaleDateString('de-DE',{day:'2-digit'}),month:d.toLocaleDateString('de-DE',{month:'short'}),full:d.toLocaleDateString('de-DE',{weekday:'short',day:'2-digit',month:'2-digit'}),time:d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}; };
  const isPast = a => new Date(a.starts_at).getTime() < Date.now() || ['cancelled','completed','done'].includes(String(a.status_code||a.status||'').toLowerCase());
  const firstName = () => String(state.me?.member?.name || 'A+ Member').trim().split(/\s+/)[0] || 'A+ Member';

  async function request(path, options={}) {
    const headers = new Headers(options.headers || {});
    if (state.token) headers.set('Authorization', `Bearer ${state.token}`);
    if (options.json !== undefined) { headers.set('Content-Type','application/json'); options.body=JSON.stringify(options.json); }
    const response = await fetch(`${API}${path}`, {...options,headers,cache:'no-store'});
    if (response.status===401) { logout(false); throw new Error('authentication_required'); }
    const type=response.headers.get('content-type')||'';
    const data=type.includes('application/json')?await response.json():await response.text();
    if(!response.ok||data?.ok===false){const error=new Error(data?.message||data?.error||`HTTP ${response.status}`);error.code=data?.error;throw error;}
    return data;
  }

  function loader(){return '<div class="loader"><div><div class="spinner"></div>Laden …</div></div>';}
  function errorBox(err){return `<div class="notice error">${esc(err?.message||'Etwas ist schiefgelaufen. Bitte erneut versuchen.')}</div>`;}
  function pageHead(kicker,title,subtitle=''){return `<div class="page-head"><div class="eyebrow">${esc(kicker)}</div><h1>${esc(title)}</h1>${subtitle?`<p>${esc(subtitle)}</p>`:''}</div>`;}

  function shell(content){
    const email=state.me?.profile?.email||'';
    root.innerHTML=`<div class="core-shell">
      <header class="core-header"><span class="core-header-spacer"></span><div class="core-brand"><img src="./assets/logo.svg" alt="A+ Esthetic"><span>${state.route==='dashboard'?'PATIENT APP':'A+ ESTHETIC'}</span></div><button class="core-icon-btn" data-settings aria-label="Einstellungen">⚙</button></header>
      <main class="core-main">${content}</main>
      <nav class="core-nav">${routes.map(([key,icon,label])=>`<button class="nav-btn ${state.route===key?'is-active':''}" data-route="${key}"><span>${icon}</span><span>${label}</span></button>`).join('')}</nav>
    </div>`;
    root.querySelectorAll('[data-route]').forEach(btn=>btn.addEventListener('click',()=>go(btn.dataset.route)));
    root.querySelector('[data-settings]')?.addEventListener('click',()=>showSettings(email));
  }

  function showSettings(email){
    document.querySelectorAll('.settings-overlay').forEach(n=>n.remove());
    const node=document.createElement('div');node.className='settings-overlay';
    node.innerHTML=`<div class="settings-card"><div class="settings-head"><h2>Einstellungen & Recht</h2><button class="core-icon-btn" data-close>×</button></div>
      <div class="settings-user"><strong>${esc(state.me?.member?.name||'A+ Kunde')}</strong><span>${esc(email)}</span></div>
      <a class="settings-link" href="${LEGAL.privacy}" target="_blank" rel="noopener">Datenschutz <span>›</span></a>
      <a class="settings-link" href="${LEGAL.terms}" target="_blank" rel="noopener">Nutzungsbedingungen <span>›</span></a>
      <a class="settings-link" href="${LEGAL.imprint}" target="_blank" rel="noopener">Impressum <span>›</span></a>
      <a class="settings-link" href="${LEGAL.deletion}" target="_blank" rel="noopener">Konto löschen <span>›</span></a>
      <button class="danger wide" data-logout style="margin-top:18px">Abmelden</button></div>`;
    document.body.appendChild(node);
    const close=()=>{node.classList.add('is-closing');setTimeout(()=>node.remove(),120);};
    node.addEventListener('click',e=>{if(e.target===node)close();});node.querySelector('[data-close]').onclick=close;
    node.querySelector('[data-logout]').onclick=()=>{node.remove();requestAnimationFrame(()=>logout());};
  }

  function logout(render=true){document.querySelectorAll('.settings-overlay').forEach(n=>n.remove());localStorage.removeItem('aplus_token');state.token='';state.me=null;state.cache={};if(render)showLogin();}

  function showLogin(message=''){
    root.innerHTML=`<div class="login-shell"><form class="login-card" data-login><div class="login-logo"><img class="login-brand-logo" src="./assets/logo.svg" alt="A+ Esthetic"><span>PATIENT APP</span></div><h1>Anmelden</h1><p>Termine, Patientenakte und A+ Punkte an einem Ort.</p>${message?`<div class="notice error">${esc(message)}</div>`:''}<label class="field"><span>E-Mail</span><input name="email" type="email" autocomplete="username" required></label><label class="field"><span>Passwort</span><input name="password" type="password" autocomplete="current-password" required></label><button class="primary wide" type="submit">Anmelden</button></form></div>`;
    root.querySelector('[data-login]').addEventListener('submit',async e=>{e.preventDefault();const btn=e.currentTarget.querySelector('button');btn.disabled=true;btn.textContent='Anmeldung …';try{const fd=new FormData(e.currentTarget);const data=await request('/login/',{method:'POST',json:{email:fd.get('email'),password:fd.get('password')}});state.token=data.token;localStorage.setItem('aplus_token',state.token);await boot();}catch(err){showLogin(err.code==='invalid_credentials'?'E-Mail oder Passwort ist nicht korrekt.':err.message);}});
  }

  async function boot(){if(!state.token)return showLogin();try{state.me=await request('/me/');go('dashboard');}catch(err){if(state.token)showLogin(err.message);}}
  async function go(route){if(route==='reviews'){state.route='points';shell(loader());try{await renderReviews();}catch(err){shell(errorBox(err));}return;}if(!routes.some(r=>r[0]===route))route='dashboard';state.route=route;shell(loader());try{if(route==='dashboard')await renderDashboard();if(route==='appointments')await renderAppointments();if(route==='records')await renderRecords();if(route==='points')await renderPoints();if(route==='friends')await renderFriends();}catch(err){shell(`${pageHead('A+ Esthetic','Fehler')} ${errorBox(err)}`);}}

  async function renderDashboard(){
    const [dash,booking]=await Promise.all([request('/dashboard/'),request('/booking/')]);
    const all=Array.isArray(booking.appointments)?booking.appointments:[];
    const upcoming=all.filter(a=>!isPast(a)&&String(a.status_code||a.status||'').toLowerCase()!=='cancelled').sort((a,b)=>new Date(a.starts_at)-new Date(b.starts_at));
    const previous=all.filter(a=>isPast(a)&&String(a.status_code||a.status||'').toLowerCase()!=='cancelled').sort((a,b)=>new Date(b.starts_at)-new Date(a.starts_at));
    const next=upcoming[0],last=previous[0];
    const contact=dash.contact||{};
    const banners=dash.campaigns||[];
    let html=`<section class="dash-hero"><div class="dash-hero-glow"></div><img src="./assets/logo.svg" alt="A+ Esthetic"><div><span>WILLKOMMEN</span><h1>Hallo, ${esc(firstName())}.</h1><p>Alles Wichtige rund um Ihre Termine und A+ Punkte.</p></div></section>`;
    html+=`<section class="dash-visit-grid"><article><span>LETZTER BESUCH</span><strong>${last?fmt(last.starts_at):'Noch keiner'}</strong><small>${last?esc(last.service||'Behandlung'):'Wir freuen uns auf Sie.'}</small></article><article class="is-next"><span>NÄCHSTER TERMIN</span><strong>${next?fmt(next.starts_at):'Noch offen'}</strong><small>${next?esc(next.service||'Behandlung'):'Jetzt Termin reservieren'}</small></article></section>`;
    html+=`<div class="dash-actions"><button class="dash-action is-primary" data-dash-book><b>Reservieren</b><span>Termin auswählen ›</span></button><a class="dash-action" href="tel:${esc(contact.phone||CONTACT.phone)}"><b>Anrufen</b><span>${esc(contact.phone_label||CONTACT.phoneLabel)}</span></a><a class="dash-action" href="${esc(contact.instagram_url||CONTACT.instagram)}" target="_blank" rel="noopener"><b>Instagram</b><span>@aplus.esthetic ↗</span></a></div>`;
    html+=`<section class="dash-points"><div><span>A+ PUNKTE</span><strong>${Number(dash.points??dash.member?.coins??0).toLocaleString('de-DE')}</strong><small>Punkte sammeln. Vorteile später freischalten.</small></div><button data-dash-points>Details ›</button></section>`;
    if(banners.length){html+=`<div class="section-title"><h2>Special Offers</h2><small>${banners.length}</small></div><div class="campaign-stack">${banners.map(b=>`<article class="campaign-card" ${b.image_url?`style="--campaign-image:url('${esc(b.image_url)}')"`:''}><div class="campaign-shade"></div><div class="campaign-copy"><span>SPECIAL OFFER</span><h3>${esc(b.title)}</h3>${b.text?`<p>${esc(b.text)}</p>`:''}${b.cta_url?`<a href="${esc(b.cta_url)}" target="_blank" rel="noopener">${esc(b.cta_label||'Mehr erfahren')} ›</a>`:''}</div></article>`).join('')}</div>`;}
    shell(html);root.querySelector('[data-dash-book]').onclick=()=>go('appointments');root.querySelector('[data-dash-points]').onclick=()=>go('points');
  }

  async function renderAppointments(){
    const data=await request('/booking/');const all=data.appointments||[];const upcoming=all.filter(a=>!isPast(a)).sort((a,b)=>new Date(a.starts_at)-new Date(b.starts_at));
    let html=pageHead('RESERVIERUNG','Termin reservieren','Behandlung, Behandler und Wunschzeit direkt auswählen.');
    if(upcoming[0]){const d=dateBits(upcoming[0].starts_at);html+=`<section class="card appointment-feature"><div class="eyebrow">Nächster Termin</div><div class="appointment-time">${d.full} · ${d.time}</div><div class="appointment-meta">${esc(upcoming[0].service)} · ${esc(upcoming[0].staff||'')}</div></section>`;}
    html+=`<section class="booking-request-card book-embedded-canonical"><form id="booking-form" data-booking></form></section>`;
    shell(html);
  }

  function pointRows(items){const tx=(items||[]).filter(x=>x.kind==='coin');if(!tx.length)return '<div class="empty">Noch keine Punktebewegungen.</div>';return tx.map(t=>{const incoming=t.direction==='in';const amount=Math.abs(Number(t.coin_amount)||0);return `<article class="point-row"><div class="point-mark ${incoming?'is-in':'is-out'}">${incoming?'+':'−'}</div><div><strong>${esc(t.description||'A+ Punkte')}</strong><span>${fmt(t.created_at)}</span></div><b>${incoming?'+':'−'}${amount}</b></article>`;}).join('');}

  async function renderPoints(){
    const [wallet,reviews,pass]=await Promise.all([request('/wallet/'),request('/reviews/'),request('/wallet-pass/').catch(()=>({}))]);
    const verified=(reviews.activities||[]).filter(x=>x.status==='verified');
    const card=pass.card||{};
    let html=pageHead('A+ PUNKTE','Ihre Punkte','Punkte durch Aktivitäten sammeln. Einlösen kommt in der nächsten Ausbaustufe.');
    html+=`<section class="points-hero"><span>AKTUELLER STAND</span><strong>${Number(wallet.coin_balance||0).toLocaleString('de-DE')}</strong><small>A+ Punkte</small></section>`;
    html+=`<section class="point-task-grid"><button data-review-route><b>★ Google Bewertung</b><span>+${Number(reviews.verified_review_points||250)} Punkte nach Verifizierung</span></button><button data-friends-route><b>↗ Freunde einladen</b><span>Punkte automatisch nach erfolgreicher Einladung</span></button></section>`;
    if(card.member_number){html+=`<section class="points-card"><div><img src="./assets/logo.svg" alt="A+"><span>DIGITALE MITGLIEDSKARTE</span><strong>${esc(card.name||state.me?.member?.name||'')}</strong><small>${esc(card.member_number)}</small></div><div class="points-card-actions"><button class="secondary" data-show-member-qr>QR anzeigen</button>${pass.providers?.apple?.configured?'<button class="secondary" data-wallet-provider="apple">Zu Apple Wallet</button>':''}</div><div class="member-qr-slot" data-member-qr-slot hidden><img data-member-qr alt="Persönlicher QR-Code"><div data-wallet-notice hidden></div></div></section>`;}
    html+=`<div class="section-title"><h2>Punkteverlauf</h2><small>${(wallet.transactions||[]).filter(x=>x.kind==='coin').length}</small></div>${pointRows(wallet.transactions)}`;
    if(verified.length)html+=`<div class="notice success">${verified.length} Google-Bewertung${verified.length===1?'':'en'} verifiziert.</div>`;
    shell(html);root.querySelector('[data-review-route]').onclick=()=>go('reviews');root.querySelector('[data-friends-route]').onclick=()=>go('friends');
    const qrBtn=root.querySelector('[data-show-member-qr]');if(qrBtn)qrBtn.onclick=async()=>{const slot=root.querySelector('[data-member-qr-slot]');slot.hidden=false;const img=slot.querySelector('[data-member-qr]');if(img.dataset.loaded)return;try{const r=await fetch(`${API}/wallet-pass/qr/`,{headers:{Authorization:`Bearer ${state.token}`}});if(!r.ok)throw new Error();img.src=URL.createObjectURL(await r.blob());img.dataset.loaded='1';}catch(_){slot.innerHTML='<div class="notice error">QR-Code konnte nicht geladen werden.</div>';}};
  }

  async function renderReviews(){
    const data=await request('/reviews/');const items=data.activities||[];
    let html=pageHead('PUNKTE SAMMELN','Google Bewertung',`Nach erfolgreicher Verifizierung erhalten Sie ${Number(data.verified_review_points||250)} Punkte.`);
    html+=`<section class="review-cta"><div class="eyebrow">Google</div><h2>Erfahrung teilen</h2><p class="row-sub">Punkte werden erst gutgeschrieben, nachdem die Bewertung tatsächlich geprüft und verifiziert wurde.</p><button class="primary wide" data-open-review>Bei Google bewerten</button></section>`;
    html+=`<section class="card"><h2 style="margin-bottom:14px">Bewertung zur Prüfung melden</h2><form data-review-submit><label class="field"><span>Sterne (optional)</span><select name="rating"><option value="">Nicht angeben</option>${[5,4,3,2,1].map(n=>`<option value="${n}">${'★'.repeat(n)}</option>`).join('')}</select></label><button class="secondary wide">Zur Verifizierung einreichen</button></form></section>`;
    html+=`<div class="section-title"><h2>Status</h2><small>${items.length}</small></div>${items.length?items.map(r=>`<article class="review-row"><div class="review-row-head"><strong>${r.rating?`${'★'.repeat(r.rating)}`:'Google Bewertung'}</strong><span class="status ${r.status}">${esc(r.status_label)}</span></div><div class="row-sub">${fmt(r.submitted_at||r.opened_at||r.created_at)}</div>${r.points_awarded?`<div class="point-earned">+${r.points_value} Punkte</div>`:''}</article>`).join(''):'<div class="empty">Noch keine Bewertung eingereicht.</div>'}`;
    shell(html);root.querySelector('[data-open-review]').onclick=async()=>{try{await request('/reviews/',{method:'POST',json:{action:'opened'}});}catch(_){}window.open(data.review_url,'_blank','noopener');};root.querySelector('[data-review-submit]').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.currentTarget);try{await request('/reviews/',{method:'POST',json:{action:'submitted',rating:fd.get('rating')||null}});await renderReviews();}catch(err){e.currentTarget.insertAdjacentHTML('beforebegin',errorBox(err));}};
  }

  async function renderFriends(){
    const data=await request('/club/');const refs=data.referrals||[];
    let html=pageHead('EMPFEHLUNGEN','Freunde einladen',`Erfolgreiche Einladung: +${Number(data.referral_points||300)} Punkte.`);
    html+=`<section class="card referral-premium"><h2>Persönlich einladen</h2><p>Einladung per E-Mail senden. Pro E-Mail kann nur einmal Punkte gesammelt werden.</p><form data-referral><label class="field"><span>E-Mail</span><input name="invited_email" type="email" placeholder="name@example.com" required></label><button class="primary wide">Einladung senden</button></form></section>`;
    html+=`<div class="section-title"><h2>Bisherige Einladungen</h2><small>${refs.length}</small></div>${refs.length?refs.map(r=>`<article class="referral-row"><strong>${esc(r.email)}</strong><div class="row-sub">${esc(r.code)}</div><span class="status ${esc(r.status)}">${esc(r.status)}</span>${r.status==='rewarded'?`<div class="point-earned">+${Number(r.reward_points||0)} Punkte</div>`:''}</article>`).join(''):'<div class="empty">Noch keine Empfehlungen.</div>'}`;
    shell(html);root.querySelector('[data-referral]').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.currentTarget);try{const result=await request('/club/',{method:'POST',json:{invited_email:fd.get('invited_email')}});await renderFriends();if(result.points_awarded)alert(`+${result.points_awarded} Punkte`);}catch(err){e.currentTarget.insertAdjacentHTML('beforebegin',errorBox(err));}};
  }

  async function renderRecords(){
    const data=await request('/patient-records/');const records=(data.records||[]).sort((a,b)=>new Date(b.captured_at||b.created_at)-new Date(a.captured_at||a.created_at));
    let html=pageHead('PATIENTENAKTE','Ihre Akte','Dokumente und Notizen chronologisch – von Ihnen und der Praxis.');
    html+=`<section class="upload-box"><form data-upload enctype="multipart/form-data"><div class="grid-2"><label class="field"><span>Typ</span><select name="kind">${(data.upload?.kinds||[{value:'document',label:'Dokument'},{value:'photo',label:'Foto'},{value:'note',label:'Notiz'}]).map(k=>`<option value="${esc(k.value)}">${esc(k.label)}</option>`).join('')}</select></label><label class="field"><span>Titel</span><input name="title" placeholder="z. B. Laborbericht"></label></div><label class="field"><span>Datei</span><input name="file" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,.doc,.docx,.xls,.xlsx,.txt,.rtf,.csv"></label><div class="native-photo-row"><button type="button" class="secondary" data-native-photo>Foto aufnehmen</button><small>Öffnet auf iPhone/Android die native Kamera stabil.</small></div><label class="field"><span>Notiz (optional)</span><textarea name="note"></textarea></label>${!data.health_data_consent?`<label class="consent"><input name="health_data_consent" type="checkbox" value="1" required><span>Ich willige ein, dass diese Gesundheitsdaten zur Behandlung und Dokumentation verarbeitet werden.</span></label>`:'<input type="hidden" name="health_data_consent" value="1">'}<button class="primary wide">In Akte speichern</button></form></section>`;
    html+=`<div class="section-title"><h2>Verlauf</h2><small>${records.length}</small></div>${records.length?records.map(recordRow).join(''):'<div class="empty">Ihre Patientenakte enthält noch keine Einträge.</div>'}`;
    shell(html);bindRecordActions();
  }

  function recordRow(r){const source=r.customer_uploaded?'Von Ihnen':'Praxis';return `<article class="record-row"><div class="record-row-head"><div><div class="record-source">${source} · ${esc(r.kind_label||r.kind)}</div><strong>${esc(r.title||'Akteneintrag')}</strong></div><small class="row-sub">${fmt(r.captured_at||r.created_at)}</small></div>${r.note?`<div class="row-sub">${esc(r.note)}</div>`:''}${r.has_file?`<div class="record-actions"><button class="secondary" data-record-file="${esc(r.id)}" data-download="0">Öffnen</button><button class="secondary" data-record-file="${esc(r.id)}" data-download="1">Download</button></div>`:''}</article>`;}

  async function nativePhotoToInput(input){const camera=window.Capacitor?.Plugins?.Camera;if(!camera?.getPhoto){input.click();return;}const photo=await camera.getPhoto({quality:88,resultType:'uri',source:'CAMERA',direction:'REAR',correctOrientation:true,presentationStyle:'fullscreen'});if(!photo?.webPath)return;const response=await fetch(photo.webPath);const blob=await response.blob();const file=new File([blob],`APlus-Foto-${Date.now()}.jpg`,{type:blob.type||'image/jpeg'});const dt=new DataTransfer();dt.items.add(file);input.files=dt.files;input.dispatchEvent(new Event('change',{bubbles:true}));}
  function bindRecordActions(){
    const form=root.querySelector('[data-upload]');if(!form)return;const fileInput=form.querySelector('input[type=file]');root.querySelector('[data-native-photo]')?.addEventListener('click',async()=>{try{await nativePhotoToInput(fileInput);}catch(err){form.insertAdjacentHTML('beforebegin',errorBox(new Error('Kamera konnte nicht geöffnet werden.')));}});
    form.onsubmit=async e=>{e.preventDefault();const btn=form.querySelector('button[type=submit]');btn.disabled=true;btn.textContent='Wird gespeichert …';try{const headers=new Headers({'Authorization':`Bearer ${state.token}`});const response=await fetch(`${API}/patient-records/upload/`,{method:'POST',headers,body:new FormData(form)});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||'Upload fehlgeschlagen');await renderRecords();}catch(err){btn.disabled=false;btn.textContent='In Akte speichern';form.insertAdjacentHTML('beforebegin',errorBox(err));}};
    root.querySelectorAll('[data-record-file]').forEach(btn=>btn.onclick=async()=>{btn.disabled=true;try{const url=`${API}/patient-records/${encodeURIComponent(btn.dataset.recordFile)}/file/${btn.dataset.download==='1'?'?download=1':''}`;const response=await fetch(url,{headers:{Authorization:`Bearer ${state.token}`}});if(!response.ok)throw new Error('Datei konnte nicht geöffnet werden.');const blob=await response.blob();const object=URL.createObjectURL(blob);if(btn.dataset.download==='1'){const a=document.createElement('a');a.href=object;a.download='APlus-Dokument';document.body.appendChild(a);a.click();a.remove();}else{window.open(object,'_blank');}setTimeout(()=>URL.revokeObjectURL(object),60000);}catch(err){btn.insertAdjacentHTML('afterend',errorBox(err));}finally{btn.disabled=false;}});
  }

  boot();
})();
