(() => {
  'use strict';

  const APP_ORIGIN = 'https://app.a-esthetic.de';
  const API = `${APP_ORIGIN}/api/mobile`;
  const LEGAL = {
    privacy: `${APP_ORIGIN}/datenschutz/`,
    terms: `${APP_ORIGIN}/nutzungsbedingungen/`,
    imprint: `${APP_ORIGIN}/impressum/`,
    deletion: `${APP_ORIGIN}/konto-loeschen/`,
  };
  const CONTACT = {
    phone: '+496971417012',
    phoneLabel: '069 71417012',
    mobile: '+491729907936',
    mobileLabel: '+49 172 9907936',
    whatsapp: '+491729907936',
    instagram: 'https://www.instagram.com/aplus.esthetic/',
    directions: 'https://www.google.com/maps/dir/?api=1&destination=Stiftstra%C3%9Fe%2014%2C%2060313%20Frankfurt%20am%20Main',
  };
  const routes = [
    ['dashboard', '⌂', 'Startseite'],
    ['appointments', '◫', 'Reservieren'],
    ['records', '▤', 'Akte'],
    ['points', '◆', 'Punkte'],
    ['friends', '↗', 'Freunde'],
  ];
  const NAV_ICONS = {
    dashboard:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10.5 12 4l8 6.5v8a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5v-8Z"/><path d="M9 20v-6h6v6"/></svg>',
    appointments:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="14.5" rx="3"/><path d="M8 3.5v4M16 3.5v4M4 10h16"/><path d="M8 14h8M8 17h5"/></svg>',
    records:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3.5h7l4 4V20H7a2 2 0 0 1-2-2V5.5a2 2 0 0 1 2-2Z"/><path d="M14 3.5v4h4M8.5 12h6M8.5 15.5h6"/></svg>',
    points:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 19 7v10l-7 3.5L5 17V7l7-3.5Z"/><path d="m8.5 12 2.2 2.2 4.8-4.8"/></svg>',
    friends:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3"/><path d="M3.5 19c.4-3.2 2.2-4.9 5.5-4.9s5.1 1.7 5.5 4.9M16 7.5h4.5M18.25 5.25v4.5M15 13.5c2.4.35 3.8 1.8 4.1 4.1"/></svg>',
    settings:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19 13.7a7.3 7.3 0 0 0 .05-3.4l1.8-1.4-1.8-3.1-2.25.9a7.5 7.5 0 0 0-3-1.7L13.5 2h-3L10.2 5a7.5 7.5 0 0 0-3 1.7l-2.25-.9-1.8 3.1 1.8 1.4a7.3 7.3 0 0 0 .05 3.4l-1.85 1.4 1.8 3.1 2.3-.9a7.5 7.5 0 0 0 2.95 1.7l.3 3h3l.3-3a7.5 7.5 0 0 0 2.95-1.7l2.3.9 1.8-3.1-1.85-1.4Z"/></svg>',
    phone:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4 10 8.4 8.2 10.2a14.2 14.2 0 0 0 5.6 5.6L15.6 14l4.4 3c.5.3.7.9.45 1.45-.65 1.45-2 2.45-3.6 2.45C9.2 20.9 3.1 14.8 3.1 7.15c0-1.6 1-2.95 2.45-3.6A1.2 1.2 0 0 1 7 4Z"/></svg>',
    instagram:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r=".8" fill="currentColor" stroke="none"/></svg>',
    directions:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s6-5.2 6-11a6 6 0 1 0-12 0c0 5.8 6 11 6 11Z"/><circle cx="12" cy="10" r="2.2"/></svg>'
  };
  const navIcon = key => NAV_ICONS[key] || '';
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
    let response = await fetch(`${API}${path}`, {...options,headers,cache:'no-store'});
    if (response.status===401 && state.token && !options._authRetried) {
      await new Promise(resolve => setTimeout(resolve, 700));
      response = await fetch(`${API}${path}`, {...options,headers,cache:'no-store'});
    }
    if (response.status===401) {
      logout(false);
      showLogin('Ihre Sitzung ist abgelaufen. Bitte einmal erneut anmelden.');
      const authError = new Error('authentication_required');
      authError.code = 'authentication_required';
      throw authError;
    }
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
      <header class="core-header premium-brand-header">
        <div class="core-brand" aria-label="A+ Esthetic">
          <span class="core-brand-emblem"><img src="./assets/logo.svg" alt="A+ Esthetic"></span>
          <span class="core-brand-name"><b>A+ ESTHETIC</b></span>
        </div>
        <button class="core-icon-btn premium-brand-settings" data-settings aria-label="Einstellungen"><span class="header-icon">${NAV_ICONS.settings}</span></button>
      </header>
      <main class="core-main">${content}</main>
      <nav class="core-nav" aria-label="Hauptnavigation">${routes.map(([key,,label])=>`<button class="nav-btn ${state.route===key?'is-active':''}" data-route="${key}" aria-label="${label}"><span class="nav-icon">${navIcon(key)}</span><span class="nav-label">${label}</span></button>`).join('')}</nav>
    </div>`;
    root.querySelectorAll('[data-route]').forEach(btn=>btn.addEventListener('click',()=>go(btn.dataset.route)));
    root.querySelector('[data-settings]')?.addEventListener('click',()=>showSettings(email));
  }


  function showSettings(email){
    document.querySelectorAll('.settings-overlay').forEach(n=>n.remove());
    const node=document.createElement('div');node.className='settings-overlay';
    node.innerHTML=`<div class="settings-card"><div class="settings-head"><h2>Einstellungen & Recht</h2><button class="core-icon-btn" data-close>×</button></div>
      <div class="settings-user"><strong>${esc(state.me?.member?.name||'A+ Kunde')}</strong><span>${esc(email)}</span></div>
      <a class="settings-link" href="${LEGAL.privacy}">Datenschutz <span>›</span></a>
      <a class="settings-link" href="${LEGAL.terms}">Nutzungsbedingungen <span>›</span></a>
      <a class="settings-link" href="${LEGAL.imprint}">Impressum <span>›</span></a>
      <details class="settings-more"><summary>Weitere Kontoeinstellungen</summary><a class="settings-link" href="${LEGAL.deletion}">Konto löschen <span>›</span></a></details>
      <button class="danger wide" data-logout style="margin-top:18px">Abmelden</button></div>`;
    document.body.appendChild(node);
    const close=()=>{node.classList.add('is-closing');setTimeout(()=>node.remove(),120);};
    node.addEventListener('click',e=>{if(e.target===node)close();});node.querySelector('[data-close]').onclick=close;
    node.querySelector('[data-logout]').onclick=()=>{node.remove();requestAnimationFrame(()=>logout());};
  }

  function logout(render=true){document.querySelectorAll('.settings-overlay').forEach(n=>n.remove());localStorage.removeItem('aplus_token');state.token='';state.me=null;state.cache={};if(render)showLogin();}

  function showContactPicker(){
    document.querySelectorAll('.contact-overlay').forEach(node=>node.remove());
    const node=document.createElement('div');
    node.className='contact-overlay';
    node.innerHTML=`<div class="contact-card">
      <div class="contact-head"><div><span>KONTAKT</span><h2>Wie möchtest du anrufen?</h2></div><button type="button" class="core-icon-btn" data-contact-close>×</button></div>
      <a class="contact-choice" href="tel:${CONTACT.phone}"><span>${NAV_ICONS.phone}</span><div><strong>Praxis</strong><small>${CONTACT.phoneLabel}</small></div><b>›</b></a>
      <a class="contact-choice" href="tel:${CONTACT.mobile}"><span>${NAV_ICONS.phone}</span><div><strong>Mobil</strong><small>${CONTACT.mobileLabel}</small></div><b>›</b></a>
    </div>`;
    document.body.appendChild(node);
    const close=()=>node.remove();
    node.addEventListener('click',event=>{if(event.target===node)close();});
    node.querySelector('[data-contact-close]')?.addEventListener('click',close);
  }

  function showLogin(message=''){
    // A production login must never prefill a stored test account.
    localStorage.removeItem('aplus_login_email');
    root.innerHTML=`<div class="login-shell login-shell-auth"><form class="login-card" data-login><div class="login-logo"><img class="login-brand-logo" src="./assets/logo.svg" alt="A+ Esthetic"></div><div class="login-kicker">A+ ESTHETIC</div><h1>Anmelden</h1><p>Termine, Patientenakte und A+ Punkte an einem Ort.</p>${message?`<div class="notice error">${esc(message)}</div>`:''}<label class="field"><span>E-Mail</span><input name="email" type="email" autocomplete="off" autocapitalize="none" spellcheck="false" required></label><label class="field"><span>Passwort</span><input name="password" type="password" autocomplete="current-password" required></label><a class="login-password-reset" data-forgot-password href="${APP_ORIGIN}/accounts/password/reset/">Passwort vergessen?</a><button class="primary wide" type="submit">Anmelden</button></form></div>`;
    root.querySelector('[data-forgot-password]')?.addEventListener('click',async event=>{
      const browser=window.Capacitor?.Plugins?.Browser;
      if (!browser?.open) return;
      event.preventDefault();
      try { await browser.open({url:event.currentTarget.href}); }
      catch (_) { window.location.assign(event.currentTarget.href); }
    });
    root.querySelector('[data-login]').addEventListener('submit',async e=>{e.preventDefault();const btn=e.currentTarget.querySelector('button');btn.disabled=true;btn.textContent='Anmeldung …';try{const fd=new FormData(e.currentTarget);const data=await request('/login/',{method:'POST',json:{email:fd.get('email'),password:fd.get('password')}});state.token=data.token;localStorage.setItem('aplus_token',state.token);await boot();}catch(err){showLogin(err.code==='invalid_credentials'?'E-Mail oder Passwort ist nicht korrekt.':err.message);}});
  }

  function showReconnect(message='Verbindung wird wiederhergestellt …'){
    root.innerHTML=`<div class="login-shell login-shell-auth"><section class="login-card"><div class="login-logo"><img class="login-brand-logo" src="./assets/logo.svg" alt="A+ Esthetic"></div><h1>Willkommen zurück</h1><p>${esc(message)}</p><div class="spinner"></div><button class="secondary wide" type="button" data-reconnect>Erneut verbinden</button></section></div>`;
    root.querySelector('[data-reconnect]')?.addEventListener('click',boot);
  }
  async function boot(){if(!state.token)return showLogin();try{state.me=await request('/me/');if(state.me?.account?.locked){window.APlusOnboarding?.start?.();return;}go('dashboard');}catch(err){if(err?.code==='profile_completion_required'){window.APlusOnboarding?.start?.();return;}if(state.token)showReconnect('Die Verbindung ist gerade nicht verfügbar. Ihre Anmeldung bleibt gespeichert.');}}
  async function go(route){if(route==='reviews'){state.route='points';shell(loader());try{await renderReviews();}catch(err){shell(errorBox(err));}return;}if(!routes.some(r=>r[0]===route))route='dashboard';state.route=route;shell(loader());try{if(route==='dashboard')await renderDashboard();if(route==='appointments')await renderAppointments();if(route==='records')await renderRecords();if(route==='points')await renderPoints();if(route==='friends')await renderFriends();}catch(err){shell(`${pageHead('A+ Esthetic','Fehler')} ${errorBox(err)}`);}}

  async function renderDashboard(){
    const [dash,booking]=await Promise.all([request('/dashboard/'),request('/booking/')]);
    const all=Array.isArray(booking.appointments)?booking.appointments:[];
    const upcoming=all.filter(a=>!isPast(a)&&String(a.status_code||a.status||'').toLowerCase()!=='cancelled').sort((a,b)=>new Date(a.starts_at)-new Date(b.starts_at));
    const next=upcoming[0];
    const contact=dash.contact||{};
    const banners=dash.campaigns||[];
    const heroImage='./assets/site/hero.svg';
    const points=Number(dash.points??dash.member?.coins??0).toLocaleString('de-DE');

    let html=`<section class="approved-home-hero ${heroImage?'has-image':''}" ${heroImage?`style="--approved-hero-image:url('${esc(heroImage)}')"`:''}>
      <div class="approved-home-copy">
        <span class="approved-kicker">WILLKOMMEN</span>
        <h1>Willkommen,<br>${esc(firstName())}.</h1>
        <p>Schön, dass du da bist.<br>Schönheit, die sich nach dir richtet.</p>
      </div>
      <div class="approved-home-image" aria-hidden="true"></div>
    </section>`;

    if(next){
      const d=dateBits(next.starts_at);
      html+=`<section class="approved-next-card">
        <div class="approved-next-label">NÄCHSTER TERMIN</div>
        <div class="approved-next-main">
          <div class="approved-date"><strong>${d.day}</strong><span>${d.month}</span></div>
          <div class="approved-next-copy"><strong>${esc(next.service||'Behandlung')}</strong><span>${d.time} Uhr · ${esc(next.staff||'A+ Esthetic')}</span></div>
          <button type="button" data-dash-book aria-label="Termin öffnen">›</button>
        </div>
      </section>`;
    }else{
      html+=`<section class="approved-next-card is-empty">
        <div class="approved-next-label">NÄCHSTER TERMIN</div>
        <div class="approved-next-main">
          <div class="approved-next-copy"><strong>Noch kein Termin geplant</strong><span>Wunschbehandlung und Zeit direkt auswählen.</span></div>
          <button type="button" data-dash-book aria-label="Termin reservieren">›</button>
        </div>
      </section>`;
    }

    html+=`<section class="approved-quick-actions">
      <button type="button" data-dash-book><span>${NAV_ICONS.appointments}</span><b>Reservieren</b></button>
      <button type="button" data-dash-call><span>${NAV_ICONS.phone}</span><b>Anrufen</b></button>
      <a href="${esc(contact.instagram_url||CONTACT.instagram)}" target="_blank" rel="noopener"><span>${NAV_ICONS.instagram}</span><b>Instagram</b></a>
      <a href="${CONTACT.directions}" target="_blank" rel="noopener"><span>${NAV_ICONS.directions}</span><b>Anfahrt</b></a>
    </section>`;

    html+=`<section class="approved-points-preview" data-dash-points>
      <div><span>A+ PUNKTE</span><strong>${points}</strong></div>
      <p>Punkte sammeln.<br>Vorteile später freischalten.</p><b>›</b>
    </section>`;

    if(banners.length){
      html+=`<div class="approved-section-head"><h2>Angebote</h2><span>${banners.length}</span></div>
      <div class="approved-campaign-stack">${banners.map(b=>`<article class="approved-campaign" style="--approved-campaign-image:url('${esc(b.image_url||'./assets/site/clinic.jpg')}')">
        <div class="approved-campaign-copy"><span>ANGEBOT</span><h3>${esc(b.title)}</h3>${b.text?`<p>${esc(b.text)}</p>`:''}${b.cta_url?`<a href="${esc(b.cta_url)}" target="_blank" rel="noopener">${esc(b.cta_label||'Mehr erfahren')} <b>›</b></a>`:''}</div>
      </article>`).join('')}</div>`;
    }

    shell(html);
    root.querySelectorAll('[data-dash-book]').forEach(button=>button.addEventListener('click',()=>go('appointments')));
    root.querySelector('[data-dash-call]')?.addEventListener('click',showContactPicker);
    root.querySelector('[data-dash-points]')?.addEventListener('click',()=>go('points'));
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
    const balance=Number(wallet.coin_balance||0);
    const nextMilestone=Math.max(1000,Math.ceil((balance+1)/1000)*1000);
    const remaining=Math.max(0,nextMilestone-balance);
    const progress=Math.min(100,(balance/nextMilestone)*100);

    let html=`<section class="approved-points-hero">
      <span>A+ PUNKTE</span>
      <div class="approved-points-balance"><strong>${balance.toLocaleString('de-DE')}</strong><p>Deine Punkte</p><em>Schönheit<br>lohnt sich.</em></div>
      <small>Noch ${remaining.toLocaleString('de-DE')} Punkte bis zu deinem nächsten Vorteil</small>
      <div class="approved-progress"><i style="width:${progress}%"></i></div><b>${balance.toLocaleString('de-DE')} / ${nextMilestone.toLocaleString('de-DE')}</b>
    </section>`;
    html+=`<section class="approved-benefits"><div class="approved-page-head compact"><h1>Deine Vorteile</h1><p>Sammle Punkte und freue dich auf exklusive Vorteile und besondere Erlebnisse.</p></div>
      <button data-review-route><span>☆</span><div><strong>Google Bewertung</strong><small>+${Number(reviews.verified_review_points||250)} Punkte nach Verifizierung</small></div><b>›</b></button>
      <button data-friends-route><span>◇</span><div><strong>Freunde einladen</strong><small>Punkte nach erfolgreicher Empfehlung</small></div><b>›</b></button>
      <div class="approved-benefit-row"><span>✦</span><div><strong>Exklusive Vorteile</strong><small>Früherer Zugang zu Aktionen</small></div><b>›</b></div>
      ${card.member_number?`<button data-show-member-qr><span>▣</span><div><strong>Digitale Mitgliedskarte</strong><small>${esc(card.member_number)}</small></div><b>›</b></button>`:''}
    </section>`;
    if(card.member_number){
      html+=`<section class="approved-member-card" data-member-qr-slot hidden><img data-member-qr alt="Persönlicher QR-Code"><div data-wallet-notice hidden></div>${pass.providers?.apple?.configured?'<button class="secondary" data-wallet-provider="apple">Zu Apple Wallet</button>':''}</section>`;
    }
    html+=`<section class="approved-quote">“ Schönheit ist die beste<br>Form der Selbstliebe. ”</section>`;
    html+=`<div class="approved-section-head"><h2>Punkteverlauf</h2><span>${(wallet.transactions||[]).filter(x=>x.kind==='coin').length}</span></div>${pointRows(wallet.transactions)}`;
    if(verified.length)html+=`<div class="notice success">${verified.length} Google-Bewertung${verified.length===1?'':'en'} verifiziert.</div>`;
    shell(html);
    root.querySelector('[data-review-route]')?.addEventListener('click',()=>go('reviews'));
    root.querySelector('[data-friends-route]')?.addEventListener('click',()=>go('friends'));
    const qrBtn=root.querySelector('[data-show-member-qr]');
    if(qrBtn)qrBtn.onclick=async()=>{
      const slot=root.querySelector('[data-member-qr-slot]');slot.hidden=false;
      const img=slot.querySelector('[data-member-qr]');
      if(img.dataset.loaded)return;
      try{
        const resp=await fetch(`${API}/wallet-pass/qr/`,{headers:{Authorization:`Bearer ${state.token}`}});
        if(!resp.ok)throw new Error();
        img.src=URL.createObjectURL(await resp.blob());img.dataset.loaded='1';
      }catch(_){slot.innerHTML='<div class="notice error">QR-Code konnte nicht geladen werden.</div>';}
    };
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
    let html=pageHead('EMPFEHLUNGEN','Freunde einladen',`300 Punkte für Sie nach der ersten Buchung Ihrer Empfehlung.`);
    html+=`<section class="card referral-premium"><h2>Persönlich einladen</h2><p>Die eingeladene Person erhält nach erfolgreicher Registrierung mit Ihrem Code 300 Punkte. Ihre 300 Punkte werden nach der ersten Buchung gutgeschrieben.</p><form data-referral><label class="field"><span>E-Mail</span><input name="invited_email" type="email" placeholder="name@example.com" required></label><button class="primary wide">Einladung senden</button></form></section>`;
    html+=`<div class="section-title"><h2>Bisherige Einladungen</h2><small>${refs.length}</small></div>${refs.length?refs.map(r=>`<article class="referral-row"><strong>${esc(r.email)}</strong><div class="row-sub">${esc(r.code)}</div><span class="status ${esc(r.status)}">${esc(r.status)}</span>${r.status==='rewarded'?`<div class="point-earned">+${Number(r.reward_points||0)} Punkte</div>`:''}</article>`).join(''):'<div class="empty">Noch keine Empfehlungen.</div>'}`;
    shell(html);root.querySelector('[data-referral]').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.currentTarget);try{const result=await request('/club/',{method:'POST',json:{invited_email:fd.get('invited_email')}});await renderFriends();if(result.points_awarded)alert(`+${result.points_awarded} Punkte`);}catch(err){e.currentTarget.insertAdjacentHTML('beforebegin',errorBox(err));}};
  }

  async function renderRecords(){
    const data=await request('/patient-records/');
    const records=(data.records||[]).sort((a,b)=>new Date(b.captured_at||b.created_at)-new Date(a.captured_at||a.created_at));
    let html=`<section class="approved-page-head"><h1>Meine Akte</h1><p>Deine Dokumente, Fotos und Notizen.<br>Sicher. Persönlich. Jederzeit verfügbar.</p></section>`;
    if(state.recordsFlash){html+=`<div class="notice success" role="status">${esc(state.recordsFlash)}</div>`;state.recordsFlash=null;}
    html+=`<section class="approved-upload-card">
      <form data-upload enctype="multipart/form-data">
        <label class="approved-upload-zone">
          <input name="file" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,.doc,.docx,.xls,.xlsx,.txt,.rtf,.csv">
          <span class="approved-upload-icon">↥</span>
          <strong>Neuer Akteneintrag</strong>
          <p>Datei, Foto oder Notiz hier ablegen<br>oder auswählen.</p>
          <b>Datei auswählen</b>
          <small>Fotos, PDF oder Dokumente</small>
        </label>
        <div class="approved-upload-files" data-upload-preview-list aria-live="polite"></div>
        <button type="button" class="approved-photo-button" data-native-photo>Foto aufnehmen</button>
        <label class="approved-note-field"><span>Notiz <small>optional</small></span><textarea name="note" placeholder="Zusätzliche Information …"></textarea></label>
        ${!data.health_data_consent?`<label class="approved-consent"><input name="health_data_consent" type="checkbox" value="1" required><span>Ich willige ein, dass diese Gesundheitsdaten zur Behandlung und Dokumentation verarbeitet werden.</span></label>`:'<input type="hidden" name="health_data_consent" value="1">'}
        <div class="approved-upload-message" data-upload-message role="status" aria-live="polite" hidden></div>
        <button type="submit" class="approved-save-record">In Akte speichern</button>
      </form>
    </section>`;
    html+=`<div class="approved-record-filters">
      <button class="is-active" data-record-filter="all">Alle</button>
      <button data-record-filter="image">Bilder</button>
      <button data-record-filter="document">Dokumente</button>
      <button data-record-filter="note">Notizen</button>
    </div>`;
    html+=`<div class="approved-section-head records-head"><h2>Zuletzt gespeichert</h2><span>${records.length}</span></div>
      <section class="approved-record-timeline">${records.length?records.map(recordRow).join(''):'<div class="empty">Ihre Patientenakte enthält noch keine Einträge.</div>'}</section>`;
    shell(html);
    bindRecordActions();
    root.querySelectorAll('[data-record-filter]').forEach(button=>button.addEventListener('click',()=>{
      const filter=button.dataset.recordFilter;
      root.querySelectorAll('[data-record-filter]').forEach(item=>item.classList.toggle('is-active',item===button));
      root.querySelectorAll('[data-record-kind]').forEach(row=>{
        const kind=String(row.dataset.recordKind||'').toLowerCase();
        const imageKinds=['photo','image','bild'];
        const documentKinds=['document','form','other'];
        const visible=filter==='all'
          || (filter==='image' && imageKinds.some(value=>kind.includes(value)))
          || (filter==='document' && documentKinds.some(value=>kind.includes(value)))
          || (filter==='note' && kind.includes('note'));
        row.hidden=!visible;
      });
    }));
  }


  function recordRow(r){
    const source=r.customer_uploaded?'Von Ihnen':'Praxis';
    const kind=String(r.kind||'document').toLowerCase();
    const icon=kind.includes('image')||kind.includes('photo')?'◉':kind.includes('note')?'✎':'▤';
    return `<article class="approved-record-row" data-record-kind="${esc(kind)}">
      <span class="approved-record-dot"></span><span class="approved-record-icon">${icon}</span>
      <div class="approved-record-copy"><strong>${esc(r.title||'Akteneintrag')}</strong><span>${fmt(r.captured_at||r.created_at)} · ${esc(r.kind_label||source)}</span>${r.note?`<small>${esc(r.note)}</small>`:''}</div>
      ${r.has_file?`<div class="approved-record-actions"><button data-record-file="${esc(r.id)}" data-record-url="${esc(r.open_url||'')}" data-download="0">Öffnen</button><button data-record-file="${esc(r.id)}" data-record-url="${esc(r.download_url||'')}" data-download="1" aria-label="Download">↓</button></div>`:''}
    </article>`;
  }


  async function nativePhotoToInput(input){
    if(!input) return;
    const camera=window.Capacitor?.Plugins?.Camera;
    if(!camera?.getPhoto){input.click();return null;}
    const photo=await camera.getPhoto({quality:84,resultType:'base64',source:'CAMERA',direction:'REAR',correctOrientation:true,saveToGallery:false,allowEditing:false,width:2048});
    if(!photo?.base64String)return;
    const format=String(photo.format||'jpeg').toLowerCase();
    const mime=format.includes('png')?'image/png':format.includes('heic')||format.includes('heif')?'image/heic':'image/jpeg';
    const ext=mime==='image/png'?'png':mime==='image/heic'?'heic':'jpg';
    const binary=atob(String(photo.base64String).replace(/\s/g,''));
    const bytes=new Uint8Array(binary.length);
    for(let i=0;i<binary.length;i+=1)bytes[i]=binary.charCodeAt(i);
    const file=new File([bytes],`APlus-${Date.now()}.${ext}`,{type:mime});
    return file;
  }

  async function openRecordUrl(url){
    if(!url) return false;
    const browser=window.Capacitor?.Plugins?.Browser;
    if(browser?.open){await browser.open({url});return true;}
    const opened=window.open(url,'_blank','noopener');
    if(opened)return true;
    location.href=url;
    return true;
  }

  function bindRecordActions(){
    const form=root.querySelector('[data-upload]');
    if(!form)return;
    const fileInput=form.querySelector('input[type=file]');
    const list=form.querySelector('[data-upload-preview-list]');
    const message=form.querySelector('[data-upload-message]');
    const noteInput=form.querySelector('textarea[name=note]');
    const saveButton=form.querySelector('button[type=submit]');
    const photoButton=form.querySelector('[data-native-photo]');
    const entries=[];
    let counter=0;
    let isSaving=false;
    let savedNoteId='';
    let savedNoteText='';
    const allowedExtensions=new Set(['pdf','jpg','jpeg','png','webp','heic','heif','doc','docx','xls','xlsx','txt','rtf','csv']);
    const maxFileBytes=10*1024*1024;

    const displayError=error=>{
      const translations={
        file_type:'Dieser Dateityp ist nicht erlaubt.',
        file_size:'Eine Datei überschreitet die zulässige Größe von 10 MB.',
        file_empty:'Die Datei ist leer.',
        empty_record:'Bitte wählen Sie eine Datei oder schreiben Sie eine Notiz.',
        patient_record_service_unavailable:'Der Aktenservice ist momentan nicht erreichbar. Ihre Auswahl bleibt erhalten.',
        identity_service_unavailable:'Die Anmeldung konnte nicht geprüft werden. Bitte versuchen Sie es erneut.',
        health_data_consent_required:'Bitte stimmen Sie der Datenverarbeitung zu.',
        authentication_required:'Bitte melden Sie sich erneut an.'
      };
      const code=String(error?.code||error?.message||'');
      return translations[code]||error?.message||'Speichern fehlgeschlagen. Bitte erneut versuchen.';
    };
    const showMessage=(text,success=false)=>{
      message.hidden=!text;
      message.textContent=text||'';
      message.className='approved-upload-message'+(success?' is-success':' is-error');
    };
    const releaseEntry=entry=>{
      if(entry.previewUrl){URL.revokeObjectURL(entry.previewUrl);entry.previewUrl='';}
    };
    const drawEntries=()=>{
      list.replaceChildren();
      for(const entry of entries){
        const row=document.createElement('article');
        row.className='approved-file-preview approved-upload-file';
        const isImage=String(entry.file.type||'').startsWith('image/');
        if(isImage){
          const image=document.createElement('img');
          image.alt='';
          if(!entry.previewUrl)entry.previewUrl=URL.createObjectURL(entry.file);
          image.src=entry.previewUrl;
          row.appendChild(image);
        }else{
          const icon=document.createElement('span');
          icon.className='approved-file-preview-icon';
          icon.textContent='▤';
          row.appendChild(icon);
        }
        const details=document.createElement('div');
        const name=document.createElement('strong');
        name.textContent=entry.file.name||'Dokument';
        const meta=document.createElement('small');
        const size=Math.max(1,Math.round(entry.file.size/1024));
        meta.textContent=size+' KB · '+(entry.recordId?'Gespeichert, wird überprüft':'Bereit zum Speichern');
        details.append(name,meta);
        row.appendChild(details);
        if(!entry.recordId){
          const remove=document.createElement('button');
          remove.type='button';
          remove.className='approved-upload-remove';
          remove.dataset.removeEntry=String(entry.id);
          remove.disabled=isSaving;
          remove.setAttribute('aria-label','Datei entfernen: '+entry.file.name);
          remove.textContent='×';
          row.appendChild(remove);
        }
        list.appendChild(row);
      }
    };
    const addFiles=files=>{
      if(isSaving)return;
      let skipped=0;
      for(const file of files){
        if(!file)continue;
        const ext=String(file.name||'').split('.').pop().toLowerCase();
        if(!allowedExtensions.has(ext)||file.size<=0||file.size>maxFileBytes||entries.length>=10){
          skipped+=1;continue;
        }
        const duplicate=entries.some(item=>item.file.name===file.name&&item.file.size===file.size&&item.file.lastModified===file.lastModified);
        if(duplicate)continue;
        entries.push({id:++counter,file,recordId:'',previewUrl:''});
      }
      drawEntries();
      if(skipped)showMessage('Bis zu 10 Dateien mit jeweils maximal 10 MB in einem unterstützten Format auswählen.');
      else showMessage('');
    };
    fileInput?.addEventListener('change',()=>{
      addFiles(Array.from(fileInput.files||[]));
      fileInput.value='';
    });
    list.addEventListener('click',event=>{
      const button=event.target.closest('[data-remove-entry]');
      if(!button||isSaving)return;
      const index=entries.findIndex(item=>String(item.id)===button.dataset.removeEntry);
      if(index<0)return;
      releaseEntry(entries[index]);
      entries.splice(index,1);
      drawEntries();
      showMessage('');
    });
    photoButton?.addEventListener('click',async()=>{
      if(isSaving)return;
      try{
        const file=await nativePhotoToInput(fileInput);
        if(file)addFiles([file]);
      }catch(error){showMessage('Kamera konnte nicht geöffnet werden. Bitte erneut versuchen.');}
    });
    noteInput?.addEventListener('input',()=>{
      if(noteInput.value.trim()!==savedNoteText){savedNoteId='';}
    });

    const sendEntry=async (file,note)=>{
      const body=new FormData();
      const consent=form.querySelector('[name=health_data_consent]');
      body.append('health_data_consent',consent?.type==='checkbox'?(consent.checked?'1':'0'):(consent?.value||'1'));
      if(file)body.append('file',file,file.name);
      if(note)body.append('note',note);
      const result=await request('/patient-records/upload/',{method:'POST',body});
      if(!result?.record_id)throw new Error('Der Server hat keine Speicherbestätigung gesendet.');
      return String(result.record_id);
    };

    form.addEventListener('submit',async event=>{
      event.preventDefault();
      if(isSaving)return;
      const consent=form.querySelector('[name=health_data_consent]');
      if(consent?.type==='checkbox'&&!consent.checked){
        showMessage('Bitte stimmen Sie der Datenverarbeitung zu.');
        consent.focus();return;
      }
      const note=noteInput.value.trim();
      if(!entries.length&&!note){
        showMessage('Bitte wählen Sie eine Datei oder schreiben Sie eine Notiz.');
        return;
      }
      isSaving=true;
      saveButton.disabled=true;
      fileInput.disabled=true;
      photoButton.disabled=true;
      noteInput.readOnly=true;
      showMessage('');
      try{
        const unsaved=entries.filter(item=>!item.recordId);
        let index=0;
        for(const item of unsaved){
          saveButton.textContent='Datei '+(++index)+' von '+unsaved.length+' speichern …';
          item.recordId=await sendEntry(item.file,'');
          drawEntries();
        }
        if(note&&(!savedNoteId||savedNoteText!==note)){
          saveButton.textContent='Notiz speichern …';
          savedNoteId=await sendEntry(null,note);
          savedNoteText=note;
        }
        saveButton.textContent='Speicherung überprüfen …';
        const response=await request('/patient-records/');
        const received=new Set((response.records||[]).map(item=>String(item.id)));
        const expected=entries.map(item=>item.recordId).concat(savedNoteId?[savedNoteId]:[]);
        if(!expected.every(id=>received.has(id))){
          throw new Error('Die Speicherung wurde angenommen, ist aber noch nicht in der Akte sichtbar. Bitte erneut überprüfen.');
        }
        entries.forEach(releaseEntry);
        state.recordsFlash=expected.length+' '+(expected.length===1?'Eintrag wurde':'Einträge wurden')+' erfolgreich gespeichert.';
        await renderRecords();
      }catch(error){
        showMessage(displayError(error));
        drawEntries();
      }finally{
        isSaving=false;
        if(saveButton.isConnected){
          saveButton.disabled=false;
          saveButton.textContent='In Akte speichern';
          fileInput.disabled=false;
          photoButton.disabled=false;
          noteInput.readOnly=false;
        }
      }
    });

    root.querySelectorAll('[data-record-file]').forEach(btn=>btn.onclick=async()=>{
      btn.disabled=true;
      try{
        if(btn.dataset.recordUrl){await openRecordUrl(btn.dataset.recordUrl);return;}
        const url=API+'/patient-records/'+encodeURIComponent(btn.dataset.recordFile)+'/file/'+(btn.dataset.download==='1'?'?download=1':'');
        const response=await fetch(url,{headers:{Authorization:'Bearer '+state.token}});
        if(!response.ok)throw new Error('Datei konnte nicht geöffnet werden.');
        const blob=await response.blob();
        const object=URL.createObjectURL(blob);
        if(btn.dataset.download==='1'){
          const a=document.createElement('a');a.href=object;a.download='APlus-Dokument';document.body.appendChild(a);a.click();a.remove();
        }else{window.open(object,'_blank');}
        setTimeout(()=>URL.revokeObjectURL(object),60000);
      }catch(error){btn.insertAdjacentHTML('afterend',errorBox(error));}
      finally{btn.disabled=false;}
    });
  }

  boot();
})();
