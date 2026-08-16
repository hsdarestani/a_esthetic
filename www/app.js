(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const LEGAL_BASE = 'https://esthetic.smarbiz.sbs';
  const root = document.getElementById('app');
  const state = {
    token: localStorage.getItem('aplus_token') || '',
    route: 'home',
  };

  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  const dateTime = (value) => {
    if (!value) return '–';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '–' : new Intl.DateTimeFormat('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
    }).format(date);
  };

  const dateOnly = (value) => {
    if (!value) return '–';
    const date = new Date(`${value}T12:00:00`);
    return Number.isNaN(date.getTime()) ? '–' : new Intl.DateTimeFormat('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric'
    }).format(date);
  };

  const euro = (cents) => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format((Number(cents) || 0) / 100);

  async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (response.status === 401) {
      logout(false);
      throw new Error('Bitte melden Sie sich erneut an.');
    }
    if (!response.ok || body.ok === false) {
      throw new Error(errorText(body.error));
    }
    return body;
  }

  function errorText(code) {
    const map = {
      invalid_credentials: 'E-Mail/Benutzername oder Passwort ist nicht korrekt.',
      authentication_required: 'Bitte melden Sie sich erneut an.',
      valid_email_required: 'Bitte geben Sie eine gültige E-Mail-Adresse ein.',
      service_not_found: 'Diese Terminart ist nicht mehr verfügbar.',
      invalid_start_time: 'Bitte wählen Sie Datum und Uhrzeit.',
      start_time_too_soon: 'Bitte wählen Sie einen Termin mindestens eine Stunde in der Zukunft.',
      staff_not_found: 'Der gewählte Ansprechpartner ist nicht verfügbar.',
      time_not_available: 'Diese Zeit ist leider nicht mehr verfügbar.',
      reward_not_found: 'Dieser Reward ist nicht verfügbar.',
      not_enough_coins: 'Sie haben nicht genügend A+ Coins.',
      reward_unavailable: 'Dieser Reward ist aktuell vergriffen.',
      reminder_not_found: 'Erinnerung nicht gefunden.',
      message_required: 'Bitte geben Sie eine Nachricht ein.',
      message_too_long: 'Die Nachricht ist zu lang.'
    };
    return map[code] || 'Etwas ist schiefgelaufen. Bitte versuchen Sie es erneut.';
  }

  function setToken(token) {
    state.token = token || '';
    if (state.token) localStorage.setItem('aplus_token', state.token);
    else localStorage.removeItem('aplus_token');
  }

  function logout(render = true) {
    setToken('');
    state.route = 'home';
    if (render) showLogin();
  }

  function showLogin(message = '') {
    root.innerHTML = `
      <main class="auth">
        <section class="auth-card">
          <div class="brandrow"><div class="brandmark">A+</div><div><b>A+ ESTHETIC</b><small>CUSTOMER CLUB</small></div></div>
          <h1>Willkommen zurück</h1>
          <p class="muted">Membership, Wallet, Rewards, Termine und Club-Vorteile.</p>
          ${message ? `<div class="errorbox">${esc(message)}</div>` : ''}
          <form id="login-form" class="form">
            <label>E-Mail oder Benutzername<input class="input" name="username" autocomplete="username" required></label>
            <label>Passwort<input class="input" name="password" type="password" autocomplete="current-password" required></label>
            <button class="btn primary" type="submit">Anmelden</button>
          </form>
          <div class="legal-links">
            <a href="${LEGAL_BASE}/datenschutz/" target="_blank" rel="noopener">Datenschutz</a>
            <a href="${LEGAL_BASE}/nutzungsbedingungen/" target="_blank" rel="noopener">Nutzungsbedingungen</a>
            <a href="${LEGAL_BASE}/support/" target="_blank" rel="noopener">Support</a>
            <a href="${LEGAL_BASE}/konto-loeschen/" target="_blank" rel="noopener">Konto löschen</a>
          </div>
        </section>
      </main>`;

    document.getElementById('login-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const button = event.currentTarget.querySelector('button');
      button.disabled = true;
      button.textContent = 'Anmeldung…';
      try {
        const data = await api('/login/', {
          method: 'POST',
          body: JSON.stringify({ username: form.get('username'), password: form.get('password') })
        });
        setToken(data.token);
        state.route = 'home';
        await renderRoute();
      } catch (error) {
        showLogin(error.message);
      }
    });
  }

  function topbar() {
    return `<header class="topbar"><div class="topbar-row"><div class="topbrand"><div class="brandmark">A+</div><div><b>A+ ESTHETIC</b><small>CUSTOMER CLUB</small></div></div><button class="iconbtn" data-refresh aria-label="Aktualisieren">↻</button></div></header>`;
  }

  function nav(active) {
    const items = [
      ['home', '⌂', 'Home'], ['club', '◇', 'Club'], ['booking', '◷', 'Termine'], ['wallet', '◈', 'Wallet'], ['more', '•••', 'Mehr']
    ];
    return `<nav class="nav">${items.map(([route, icon, label]) => `<button data-route="${route}" class="${active === route ? 'active' : ''}"><span>${icon}</span><span>${label}</span></button>`).join('')}</nav>`;
  }

  function shell(content, active = state.route) {
    root.innerHTML = `<div class="shell">${topbar()}<main class="content">${content}</main>${nav(['reminders','messages','profile'].includes(active) ? 'more' : active)}</div>`;
    bindShell();
  }

  function bindShell() {
    root.querySelectorAll('[data-route]').forEach((button) => button.addEventListener('click', () => navigate(button.dataset.route)));
    root.querySelector('[data-refresh]')?.addEventListener('click', () => renderRoute(true));
  }

  async function navigate(route) {
    if (!route || route === state.route || document.body.classList.contains('route-transitioning')) return;
    state.route = route;
    document.body.classList.add('route-transitioning');
    root.querySelectorAll('.nav [data-route]').forEach(button => {
      button.classList.toggle('active', button.dataset.route === route);
    });
    try {
      await renderRoute();
    } finally {
      requestAnimationFrame(() => document.body.classList.remove('route-transitioning'));
    }
  }

  function loading(title = 'A+ Esthetic') {
    shell(`<div class="pagehead"><span>A+ Customer Club</span><h1>${esc(title)}</h1></div><div class="loading">Wird geladen…</div>`, state.route);
  }

  function fail(error) {
    shell(`<div class="pagehead"><span>A+ Customer Club</span><h1>Verbindung</h1></div><div class="errorbox">${esc(error.message)}</div><div class="actions"><button class="btn primary" data-retry>Erneut versuchen</button></div>`, state.route);
    root.querySelector('[data-retry]')?.addEventListener('click', () => renderRoute(true));
  }

  async function renderRoute() {
    if (!state.token) return showLogin();
    try {
      if (state.route === 'home') return await renderHome();
      if (state.route === 'club') return await renderClub();
      if (state.route === 'booking') return await renderBooking();
      if (state.route === 'wallet') return await renderWallet();
      if (state.route === 'reminders') return await renderReminders();
      if (state.route === 'messages') return await renderMessages();
      if (state.route === 'profile') return await renderProfile();
      return renderMore();
    } catch (error) {
      if (state.token) fail(error);
    }
  }

  async function renderHome() {
    const data = await api('/dashboard/');
    const member = data.member;
    shell(`
      <div class="pagehead"><span>A+ Customer Club</span><h1>Hallo ${esc(member.name.split(' ')[0] || member.name)}</h1><p>Ihre Club-Übersicht für heute.</p></div>
      <section class="hero"><small>${esc(member.tier)}</small><h2>${esc(member.name)}</h2><p class="member-no">${esc(member.member_number)}</p><div class="actions"><span class="badge">${esc(member.member_status)}</span></div></section>
      <div class="stats"><div class="stat"><b>${Number(member.coins) || 0}</b><small>A+ Coins</small></div><div class="stat"><b>${euro(member.credit_cents)}</b><small>Credit</small></div><div class="stat"><b>${data.packages.length}</b><small>Pakete</small></div><div class="stat"><b>${data.reminders.length}</b><small>Erinnerungen</small></div></div>
      <section class="card"><h2>Nächster Termin</h2>${data.next_appointment ? `<div class="row"><div class="row-main"><b>${esc(data.next_appointment.title)}</b><small>${dateTime(data.next_appointment.starts_at)}</small></div><span class="badge">${esc(data.next_appointment.status)}</span></div>` : '<p class="empty">Noch kein Termin geplant.</p>'}<div class="actions"><button class="btn primary" data-route="booking">Termin anfragen</button></div></section>
      <section class="card"><h2>Erinnerungen</h2>${data.reminders.length ? data.reminders.map(item => `<div class="row"><div class="row-main"><b>${esc(item.title)}</b><small>${dateTime(item.scheduled_for)}</small></div></div>`).join('') : '<p class="empty">Keine aktiven Erinnerungen.</p>'}<div class="actions"><button class="btn ghost" data-route="reminders">Alle anzeigen</button></div></section>
    `, 'home');
  }

  async function renderClub() {
    const data = await api('/club/');
    shell(`
      <div class="pagehead"><span>Membership</span><h1>Customer Club</h1><p>Ihre Vorteile, Aktionen und Empfehlungen.</p></div>
      <section class="hero"><small>${esc(data.member.tier)}</small><h2>${esc(data.member.name)}</h2><p class="member-no">${esc(data.member.member_number)}</p><div class="actions"><span class="badge">${Number(data.member.coins) || 0} Coins</span><span class="badge">${euro(data.member.credit_cents)}</span></div></section>
      <section class="card"><h2>Aktuelles</h2>${data.campaigns.length ? data.campaigns.map(c => `<div class="row"><div class="row-main"><b>${esc(c.name)}</b><small>${esc(c.message)}</small></div></div>`).join('') : '<p class="empty">Keine aktuelle Aktion.</p>'}</section>
      <section class="card"><h2>Gift Cards</h2>${data.giftcards.length ? data.giftcards.map(c => `<div class="row"><div class="row-main"><b>${esc(c.code)}</b><small>${esc(c.status)}</small></div><span class="money">${euro(c.balance_cents)}</span></div>`).join('') : '<p class="empty">Keine Gift Card.</p>'}</section>
      <section class="card"><h2>Freund/in einladen</h2><form id="referral-form" class="form"><label>E-Mail<input name="invited_email" type="email" required placeholder="name@example.com"></label><button class="btn primary">Einladung speichern</button></form><div class="separator"></div>${data.referrals.length ? data.referrals.map(r => `<div class="row"><div class="row-main"><b>${esc(r.email)}</b><small>${esc(r.code)} · ${esc(r.status)}</small></div><span class="badge">${Number(r.reward_coins) || 0} Coins</span></div>`).join('') : '<p class="empty">Noch keine Empfehlungen.</p>'}</section>
    `, 'club');
    document.getElementById('referral-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      try {
        await api('/club/', { method: 'POST', body: JSON.stringify({ invited_email: form.get('invited_email') }) });
        await renderClub();
      } catch (error) { alert(error.message); }
    });
  }

  async function renderBooking() {
    const data = await api('/booking/');
    shell(`
      <div class="pagehead"><span>Organisation</span><h1>Termine</h1><p>Terminart auswählen und anschließend bequem eine freie Zeit wählen.</p></div>
      <section class="card booking-request-card">
        <h2>Neue Anfrage</h2>
        <form id="booking-form" class="form">
          <label>Terminart
            <select name="service_id" required>
              <option value="">Bitte wählen</option>
              ${data.services.map(s => `<option value="${s.id}">${esc(s.name)} · ${s.duration_minutes} Min.</option>`).join('')}
            </select>
          </label>
          <div class="booking-picker-wrap">
            <span>Wunschtermin</span>
            <input type="hidden" name="starts_at" required>
            <div data-booking-picker></div>
            <small class="booking-modern-note">Der passende Ansprechpartner aus dem A+ Team wird automatisch für Sie eingeplant.</small>
          </div>
          <button class="btn primary" type="submit" disabled>Terminanfrage senden</button>
        </form>
      </section>
      <section class="card"><h2>Ihre Termine</h2>${data.appointments.length ? data.appointments.map(a => `<div class="row"><div class="row-main"><b>${esc(a.service)}</b><small>${dateTime(a.starts_at)}</small></div><span class="badge">${esc(a.status)}</span></div>`).join('') : '<p class="empty">Noch keine Termine.</p>'}</section>
    `, 'booking');
    document.getElementById('booking-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const startsAt = String(form.get('starts_at') || '');
      if (!startsAt) {
        alert('Bitte wählen Sie eine freie Zeit.');
        return;
      }
      const payload = { service_id: Number(form.get('service_id')), starts_at: startsAt };
      const button = event.currentTarget.querySelector('button[type="submit"]');
      button.disabled = true;
      button.textContent = 'Wird gesendet…';
      try {
        await api('/booking/', { method: 'POST', body: JSON.stringify(payload) });
        alert('Terminanfrage wurde gespeichert.');
        await renderBooking();
      } catch (error) {
        alert(error.message);
        button.disabled = false;
        button.textContent = 'Terminanfrage senden';
      }
    });
  }

  async function renderWallet() {
    const data = await api('/wallet/');
    shell(`
      <div class="pagehead"><span>Vorteile</span><h1>Wallet & Rewards</h1><p>Ihr A+ Credit und Ihre Club-Coins.</p></div>
      <div class="grid2"><section class="hero"><small>A+ CREDIT</small><h2>${euro(data.balance_cents)}</h2><p>Ihr persönliches Club-Guthaben.</p></section><section class="hero"><small>A+ COINS</small><h2>${Number(data.coin_balance) || 0}</h2><p>Für ausgewählte Club-Rewards.</p></section></div>
      <section class="card"><h2>Rewards</h2>${data.rewards.length ? data.rewards.map(r => `<div class="row"><div class="row-main"><b>${esc(r.name)}</b><small>${esc(r.description || 'A+ Customer Club Reward')}</small></div><button class="btn ghost" data-reward="${r.id}" ${data.coin_balance < r.coin_cost ? 'disabled' : ''}>${r.coin_cost} Coins</button></div>`).join('') : '<p class="empty">Aktuell keine Rewards.</p>'}</section>
      <section class="card"><h2>Pakete</h2>${data.packages.length ? data.packages.map(p => `<div class="row"><div class="row-main"><b>${esc(p.name)}</b><small>Gültig bis ${dateOnly(p.expires_at)}</small></div><span class="badge">${p.remaining_sessions} offen</span></div>`).join('') : '<p class="empty">Keine aktiven Pakete.</p>'}</section>
      <section class="card"><h2>Transaktionen</h2>${data.transactions.length ? data.transactions.map(t => `<div class="row"><div class="row-main"><b>${esc(t.description)}</b><small>${dateTime(t.created_at)}</small></div><span class="money">${t.kind === 'coin' ? `${t.coin_amount} Coins` : euro(t.amount_cents)}</span></div>`).join('') : '<p class="empty">Noch keine Transaktionen.</p>'}</section>
    `, 'wallet');
    root.querySelectorAll('[data-reward]').forEach(button => button.addEventListener('click', async () => {
      if (!confirm('Diesen Reward mit A+ Coins reservieren?')) return;
      try {
        await api(`/wallet/reward/${button.dataset.reward}/`, { method: 'POST', body: '{}' });
        await renderWallet();
      } catch (error) { alert(error.message); }
    }));
  }

  async function renderReminders() {
    const data = await api('/reminders/');
    shell(`<div class="pagehead"><span>Aktuell</span><h1>Erinnerungen</h1><p>Termine und Customer-Club Hinweise.</p></div><section class="card">${data.reminders.length ? data.reminders.map(r => `<div class="row"><div class="row-main"><b>${esc(r.title)}</b><small>${esc(r.body)} · ${dateTime(r.scheduled_for)}</small></div><button class="btn ghost" data-reminder="${r.id}">${r.status === 'scheduled' ? 'Ausblenden' : 'Aktivieren'}</button></div>`).join('') : '<p class="empty">Keine Erinnerungen.</p>'}</section>`, 'reminders');
    root.querySelectorAll('[data-reminder]').forEach(button => button.addEventListener('click', async () => {
      try {
        await api('/reminders/', { method: 'POST', body: JSON.stringify({ id: Number(button.dataset.reminder) }) });
        await renderReminders();
      } catch (error) { alert(error.message); }
    }));
  }

  async function renderMessages() {
    const data = await api('/messages/');
    shell(`
      <div class="pagehead"><span>Kontakt</span><h1>Nachrichten</h1><p>Direkter organisatorischer Kontakt mit dem A+ Esthetic Team.</p></div>
      <div class="notice">Bitte nutzen Sie diesen Chat nur für Customer-Club, Termin-, Reward- und organisatorische Fragen.</div>
      <section class="card"><div class="messages">${data.messages.length ? data.messages.map(m => `<div class="bubble ${m.mine ? 'mine' : ''}"><small>${esc(m.sender)} · ${dateTime(m.created_at)}</small><p>${esc(m.body)}</p></div>`).join('') : '<p class="empty">Noch keine Nachrichten.</p>'}</div><form id="message-form" class="form"><label>Nachricht<textarea name="body" rows="3" maxlength="3000" required placeholder="Ihre Nachricht an A+ Esthetic"></textarea></label><button class="btn primary">Senden</button></form></section>
    `, 'messages');
    document.getElementById('message-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      try {
        await api('/messages/', { method: 'POST', body: JSON.stringify({ body: form.get('body') }) });
        await renderMessages();
      } catch (error) { alert(error.message); }
    });
  }

  async function renderProfile() {
    const data = await api('/profile/');
    const p = data.profile;
    shell(`
      <div class="pagehead"><span>Konto</span><h1>Profil</h1><p>Kontaktdaten und Club-Einstellungen.</p></div>
      <section class="card"><h2>${esc(p.name)}</h2><p class="muted">${esc(p.email)}</p><form id="profile-form" class="form"><label>Telefon<input name="phone" value="${esc(p.phone || '')}" autocomplete="tel"></label><label class="check"><input type="checkbox" name="marketing_consent" ${p.marketing_consent ? 'checked' : ''}><span>Personalisierte Informationen und Club-Angebote erhalten</span></label><button class="btn primary">Speichern</button></form></section>
      <section class="card"><h2>Datenschutz & Konto</h2><div class="more-grid"><a href="${LEGAL_BASE}/datenschutz/" target="_blank" rel="noopener">Datenschutz</a><a href="${LEGAL_BASE}/support/" target="_blank" rel="noopener">Support</a><a href="${LEGAL_BASE}/nutzungsbedingungen/" target="_blank" rel="noopener">Bedingungen</a><a href="${LEGAL_BASE}/impressum/" target="_blank" rel="noopener">Impressum</a></div><div class="separator"></div><button class="btn danger" id="delete-account">Kontolöschung anfordern</button></section>
    `, 'profile');
    document.getElementById('profile-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      try {
        await api('/profile/', { method: 'POST', body: JSON.stringify({ phone: form.get('phone'), marketing_consent: form.get('marketing_consent') === 'on' }) });
        alert('Einstellungen gespeichert.');
      } catch (error) { alert(error.message); }
    });
    document.getElementById('delete-account')?.addEventListener('click', async () => {
      if (!confirm('Möchten Sie die Löschung Ihres Customer-Club-Kontos anfordern?')) return;
      try {
        await api('/account-deletion/', { method: 'POST', body: '{}' });
        alert('Ihre Löschanfrage wurde gespeichert.');
      } catch (error) { alert(error.message); }
    });
  }

  function renderMore() {
    shell(`
      <div class="pagehead"><span>A+ Esthetic</span><h1>Mehr</h1><p>Kommunikation, Einstellungen und Hilfe.</p></div>
      <section class="card"><div class="more-grid"><button data-route="messages">✉ Nachrichten</button><button data-route="reminders">◉ Erinnerungen</button><button data-route="profile">⚙ Profil</button><a href="${LEGAL_BASE}/support/" target="_blank" rel="noopener">? Support</a></div></section>
      <section class="card"><h2>Rechtliches</h2><div class="more-grid"><a href="${LEGAL_BASE}/datenschutz/" target="_blank" rel="noopener">Datenschutz</a><a href="${LEGAL_BASE}/nutzungsbedingungen/" target="_blank" rel="noopener">Bedingungen</a><a href="${LEGAL_BASE}/konto-loeschen/" target="_blank" rel="noopener">Konto löschen</a><a href="${LEGAL_BASE}/impressum/" target="_blank" rel="noopener">Impressum</a></div></section>
      <button class="btn ghost" id="logout" style="width:100%">Abmelden</button>
    `, 'more');
    document.getElementById('logout')?.addEventListener('click', () => logout());
  }

  async function boot() {
    if (!state.token) return showLogin();
    try {
      await api('/me/');
      await renderRoute();
    } catch (error) {
      if (!state.token) return;
      fail(error);
    }
  }

  boot();
})();
