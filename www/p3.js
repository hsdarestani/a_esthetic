(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const token = () => localStorage.getItem('aplus_token') || '';
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const dateTime = value => value ? new Intl.DateTimeFormat('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
  }).format(new Date(value)) : '–';

  function humanError(code) {
    const errors = {
      authentication_required: 'Bitte melden Sie sich erneut an.',
      challenge_not_active: 'Diese Challenge ist aktuell nicht verfügbar.',
      challenge_not_joined: 'Bitte starten Sie die Challenge zuerst.',
      progress_already_recorded_today: 'Ihr heutiger Fortschritt wurde bereits gespeichert.',
      quiz_not_found: 'Dieses Quiz ist nicht verfügbar.',
      quiz_has_no_questions: 'Dieses Quiz ist noch nicht vollständig freigegeben.',
      quiz_answers_incomplete: 'Bitte beantworten Sie alle Fragen.',
      invalid_quiz_answer: 'Bitte prüfen Sie Ihre Antworten.',
      event_not_found: 'Dieses Event wurde nicht gefunden.',
      event_not_open: 'Für dieses Event ist keine neue Anmeldung mehr möglich.',
      event_guest_not_allowed: 'Für dieses Event ist keine Begleitperson vorgesehen.',
      event_registration_not_found: 'Keine passende Event-Anmeldung gefunden.',
      event_registration_cannot_cancel: 'Diese Anmeldung kann nicht mehr storniert werden.',
      event_already_started: 'Das Event hat bereits begonnen.',
      invalid_concierge_type: 'Bitte wählen Sie eine gültige Concierge-Anfrage.',
      concierge_title_required: 'Bitte geben Sie einen kurzen Titel ein.',
      concierge_details_required: 'Bitte beschreiben Sie kurz, wobei wir helfen können.',
      conversation_subject_required: 'Bitte geben Sie einen Betreff ein.',
      conversation_not_found: 'Diese Unterhaltung wurde nicht gefunden.',
      conversation_closed: 'Diese Unterhaltung ist bereits geschlossen.',
      message_required: 'Bitte schreiben Sie eine Nachricht.',
      message_too_long: 'Die Nachricht ist zu lang.'
    };
    return errors[code] || 'Die Aktion konnte nicht durchgeführt werden.';
  }

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) {
      const error = new Error(humanError(body.error));
      error.code = body.error;
      error.status = response.status;
      throw error;
    }
    return body;
  }

  function content() { return document.querySelector('.shell .content'); }

  function backMarkup(kicker, title, subtitle) {
    return `<div class="pagehead"><span>${esc(kicker)}</span><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>
      <div class="actions" style="margin-bottom:12px"><button class="btn ghost" type="button" data-p3-back>← Mehr</button></div>`;
  }

  function bindBack() {
    document.querySelector('[data-p3-back]')?.addEventListener('click', () => {
      const more = document.querySelector('.nav [data-route="more"]');
      if (more) more.click();
    });
  }

  function loading(kicker, title, subtitle) {
    const target = content();
    if (!target) return false;
    target.innerHTML = `${backMarkup(kicker, title, subtitle)}<div class="loading">Wird geladen…</div>`;
    bindBack();
    return true;
  }

  function fail(error, retry) {
    const target = content();
    if (!target) return;
    target.innerHTML += `<div class="errorbox">${esc(error.message)}</div><div class="actions"><button class="btn primary" type="button" data-p3-retry>Erneut versuchen</button></div>`;
    target.querySelector('[data-p3-retry]')?.addEventListener('click', retry);
  }

  async function showGamification() {
    if (!loading('A+ Community', 'Challenges & Achievements', 'Motivation für Pflege, Lernen und Community.')) return;
    try {
      const data = await api('/gamification/');
      const target = content();
      target.innerHTML = `${backMarkup('A+ Community', 'Challenges & Achievements', 'Motivation für Pflege, Lernen und Community.')}
        <section class="card" style="background:linear-gradient(135deg,#17212a,#2d3d47);color:#fff;border:none">
          <small style="color:#e8c594;letter-spacing:.1em">A+ COINS</small>
          <h2 style="font-size:34px;color:#fff;margin:6px 0">${Number(data.coin_balance) || 0}</h2>
          <p style="margin:0;opacity:.75">Durch freigegebene Lern- und Community-Aktivitäten.</p>
        </section>
        <div class="notice">${esc(data.safety_note)}</div>
        <section class="card"><h2>Aktive Challenges</h2>
          ${data.challenges.length ? data.challenges.map(challenge => {
            const p = challenge.participation;
            const percent = p ? Math.min(100, Math.round((p.progress / challenge.target_count) * 100)) : 0;
            return `<div style="padding:14px 0;border-bottom:1px solid rgba(0,0,0,.08)">
              <div class="row"><div class="row-main"><b>${esc(challenge.title)}</b><small>${esc(challenge.type_label)} · bis ${dateTime(challenge.ends_at)}</small></div><span class="badge">+${challenge.reward_coins} Coins</span></div>
              ${challenge.description ? `<p>${esc(challenge.description)}</p>` : ''}
              ${challenge.badge ? `<small>${esc(challenge.badge.icon)} Achievement: ${esc(challenge.badge.name)}</small>` : ''}
              ${p ? `<div style="margin:12px 0"><div style="height:7px;background:rgba(0,0,0,.08);border-radius:10px;overflow:hidden"><div style="height:100%;width:${percent}%;background:#b38a54"></div></div><small>${p.progress} / ${challenge.target_count}</small></div>` : ''}
              <div class="actions">
                ${!p ? `<button class="btn primary" type="button" data-p3-join="${challenge.id}">Challenge starten</button>` : p.completed ? '<span class="badge">✓ Abgeschlossen</span>' : `<button class="btn primary" type="button" data-p3-progress="${challenge.id}" ${p.can_progress_today ? '' : 'disabled'}>${p.can_progress_today ? 'Heutigen Fortschritt speichern' : 'Heute bereits gespeichert'}</button>`}
              </div>
            </div>`;
          }).join('') : '<p class="empty">Aktuell sind keine Challenges freigeschaltet.</p>'}
        </section>
        <section class="card"><h2>Achievements</h2>
          ${data.badges.length ? `<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px">${data.badges.map(badge => `<div style="padding:14px;border:1px solid rgba(0,0,0,.08);border-radius:16px"><div style="font-size:28px">${esc(badge.icon)}</div><b>${esc(badge.name)}</b><small style="display:block">${esc(badge.description)}</small></div>`).join('')}</div>` : '<p class="empty">Noch keine Achievements – Ihre ersten erscheinen hier.</p>'}
        </section>
        <section class="card"><h2>Quiz & Wissen</h2>
          ${data.quizzes.length ? data.quizzes.map(quiz => `<div style="padding:14px 0;border-bottom:1px solid rgba(0,0,0,.08)">
            <div class="row"><div class="row-main"><b>${esc(quiz.title)}</b><small>Bestehen ab ${quiz.passing_percent}% · +${quiz.reward_coins} Coins</small></div>${quiz.attempt?.completed ? `<span class="badge">${quiz.attempt.passed ? '✓ Bestanden' : quiz.attempt.percent + '%'}</span>` : ''}</div>
            ${quiz.description ? `<p>${esc(quiz.description)}</p>` : ''}
            ${quiz.attempt?.completed ? `<p class="muted">Ergebnis: ${quiz.attempt.score}/${quiz.attempt.total_questions} · ${quiz.attempt.percent}%</p>` : `<form class="form" data-p3-quiz="${quiz.id}">${quiz.questions.map((question, qIndex) => `<fieldset style="border:0;padding:8px 0;margin:0"><b>${qIndex + 1}. ${esc(question.question)}</b>${question.options.map((option, index) => `<label class="check"><input type="radio" name="q-${qIndex}" value="${index}" required><span>${esc(option)}</span></label>`).join('')}</fieldset>`).join('')}<button class="btn primary" type="submit">Quiz abschließen</button></form>`}
          </div>`).join('') : '<p class="empty">Noch kein freigegebenes Quiz.</p>'}
        </section>`;
      bindBack();
      target.querySelectorAll('[data-p3-join]').forEach(button => button.addEventListener('click', async () => {
        button.disabled = true;
        try { await api(`/gamification/challenges/${button.dataset.p3Join}/join/`, { method: 'POST', body: '{}' }); await showGamification(); }
        catch (error) { alert(error.message); button.disabled = false; }
      }));
      target.querySelectorAll('[data-p3-progress]').forEach(button => button.addEventListener('click', async () => {
        button.disabled = true;
        try { const result = await api(`/gamification/challenges/${button.dataset.p3Progress}/progress/`, { method: 'POST', body: '{}' }); if (result.coins_awarded) alert(`+${result.coins_awarded} A+ Coins`); await showGamification(); }
        catch (error) { alert(error.message); button.disabled = false; }
      }));
      target.querySelectorAll('[data-p3-quiz]').forEach(form => form.addEventListener('submit', async event => {
        event.preventDefault();
        const answers = [...form.querySelectorAll('fieldset')].map((fieldset, index) => Number(new FormData(form).get(`q-${index}`)));
        const button = form.querySelector('button[type="submit"]');
        button.disabled = true;
        try {
          const result = await api(`/gamification/quizzes/${form.dataset.p3Quiz}/submit/`, { method: 'POST', body: JSON.stringify({ answers }) });
          alert(`${result.result.passed ? 'Bestanden' : 'Ergebnis'}: ${result.result.percent}%${result.result.coins_awarded ? ` · +${result.result.coins_awarded} Coins` : ''}`);
          await showGamification();
        } catch (error) { alert(error.message); button.disabled = false; }
      }));
    } catch (error) { fail(error, showGamification); }
  }

  async function downloadEventCalendar(eventId) {
    const response = await fetch(`${API_BASE}/events/${eventId}/calendar/`, { headers: { Authorization: `Bearer ${token()}` } });
    if (!response.ok) throw new Error('Kalendereintrag konnte nicht erstellt werden.');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `aesthetic-event-${eventId}.ics`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function showEvents() {
    if (!loading('A+ Community', 'Events', 'Entdecken, anmelden und Wartelisten automatisch nutzen.')) return;
    try {
      const data = await api('/events/');
      const target = content();
      target.innerHTML = `${backMarkup('A+ Community', 'Events', 'Entdecken, anmelden und Wartelisten automatisch nutzen.')}
        <div class="notice">${esc(data.note)}</div>
        ${data.events.length ? data.events.map(event => {
          const r = event.registration;
          return `<section class="card">
            <div class="row"><div class="row-main"><h2 style="margin:0">${esc(event.title)}</h2><small>${dateTime(event.starts_at)} · ${esc(event.location || 'A+ Esthetic')}</small></div><span class="badge">${event.remaining_seats} frei</span></div>
            ${event.description ? `<p>${esc(event.description)}</p>` : ''}
            ${r && r.status !== 'cancelled' ? `<div class="notice">${esc(r.status_label)}${r.guest_name ? ` · mit ${esc(r.guest_name)}` : ''}</div><div class="actions">${r.status === 'registered' ? `<button class="btn primary" type="button" data-p3-calendar="${event.id}">Zum Kalender</button>` : ''}${['registered','waitlist'].includes(r.status) ? `<button class="btn ghost" type="button" data-p3-event-cancel="${event.id}">Anmeldung stornieren</button>` : ''}</div>` : `<form class="form" data-p3-event-register="${event.id}">${event.allow_guest ? '<label>Begleitperson (optional)<input name="guest_name" maxlength="120" placeholder="Name der Begleitperson"></label>' : ''}<button class="btn primary" type="submit">Anmelden</button></form>`}
          </section>`;
        }).join('') : '<div class="card"><p class="empty">Aktuell sind keine kommenden Events veröffentlicht.</p></div>'}`;
      bindBack();
      target.querySelectorAll('[data-p3-event-register]').forEach(form => form.addEventListener('submit', async event => {
        event.preventDefault();
        const data = new FormData(form);
        const button = form.querySelector('button');
        button.disabled = true;
        try {
          const result = await api(`/events/${form.dataset.p3EventRegister}/register/`, { method: 'POST', body: JSON.stringify({ guest_name: data.get('guest_name') || '' }) });
          alert(result.registration.status === 'waitlist' ? 'Event ist voll – Sie stehen auf der Warteliste.' : 'Ihre Event-Anmeldung ist bestätigt.');
          await showEvents();
        } catch (error) { alert(error.message); button.disabled = false; }
      }));
      target.querySelectorAll('[data-p3-event-cancel]').forEach(button => button.addEventListener('click', async () => {
        if (!confirm('Event-Anmeldung wirklich stornieren?')) return;
        button.disabled = true;
        try { await api(`/events/${button.dataset.p3EventCancel}/cancel/`, { method: 'POST', body: '{}' }); await showEvents(); }
        catch (error) { alert(error.message); button.disabled = false; }
      }));
      target.querySelectorAll('[data-p3-calendar]').forEach(button => button.addEventListener('click', async () => {
        try { await downloadEventCalendar(button.dataset.p3Calendar); } catch (error) { alert(error.message); }
      }));
    } catch (error) { fail(error, showEvents); }
  }

  async function showConversation(threadId) {
    if (!loading('A+ Support', 'Unterhaltung', 'Direkter Kontakt mit dem A+ Team.')) return;
    try {
      const data = await api(`/conversations/${threadId}/`);
      const target = content();
      target.innerHTML = `${backMarkup('A+ Support', data.thread.subject, 'Direkter Kontakt mit dem A+ Team.')}
        <div class="notice">Dieser Bereich ist nicht für akute Notfälle geeignet.</div>
        <section class="card">
          <div style="display:flex;flex-direction:column;gap:10px">${data.messages.length ? data.messages.map(message => `<div style="align-self:${message.mine ? 'flex-end' : 'flex-start'};max-width:86%;padding:11px 13px;border-radius:16px;background:${message.mine ? '#17212a' : 'rgba(0,0,0,.06)'};color:${message.mine ? '#fff' : 'inherit'}"><div>${esc(message.body)}</div><small style="opacity:.65">${esc(message.sender)} · ${dateTime(message.created_at)}</small></div>`).join('') : '<p class="empty">Noch keine Nachrichten.</p>'}</div>
        </section>
        ${data.thread.status === 'open' ? `<section class="card"><form class="form" data-p3-reply><label>Nachricht<textarea name="body" rows="4" maxlength="5000" required></textarea></label><div class="actions"><button class="btn primary" type="submit">Senden</button><button class="btn ghost" type="button" data-p3-close-thread>Unterhaltung schließen</button></div></form></section>` : '<div class="notice">Diese Unterhaltung ist geschlossen.</div>'}`;
      bindBack();
      target.querySelector('[data-p3-back]')?.addEventListener('click', showConcierge, { once: true });
      target.querySelector('[data-p3-reply]')?.addEventListener('submit', async event => {
        event.preventDefault();
        const body = new FormData(event.currentTarget).get('body');
        const button = event.currentTarget.querySelector('button[type="submit"]');
        button.disabled = true;
        try { await api(`/conversations/${threadId}/`, { method: 'POST', body: JSON.stringify({ body }) }); await showConversation(threadId); }
        catch (error) { alert(error.message); button.disabled = false; }
      });
      target.querySelector('[data-p3-close-thread]')?.addEventListener('click', async () => {
        if (!confirm('Unterhaltung schließen?')) return;
        try { await api(`/conversations/${threadId}/close/`, { method: 'POST', body: '{}' }); await showConversation(threadId); }
        catch (error) { alert(error.message); }
      });
    } catch (error) { fail(error, () => showConversation(threadId)); }
  }

  async function showConcierge() {
    if (!loading('A+ Support', 'Concierge & Nachrichten', 'Organisatorische Wünsche und sichere Kommunikation.')) return;
    try {
      const [concierge, conversations] = await Promise.all([api('/concierge/'), api('/conversations/')]);
      const target = content();
      target.innerHTML = `${backMarkup('A+ Support', 'Concierge & Nachrichten', 'Organisatorische Wünsche und sichere Kommunikation.')}
        <div class="notice">${esc(concierge.note)} ${esc(conversations.note)}</div>
        <section class="card"><h2>Concierge-Anfrage</h2><form class="form" data-p3-concierge-form>
          <label>Wunsch<select name="request_type">${concierge.types.map(type => `<option value="${esc(type.value)}">${esc(type.label)}</option>`).join('')}</select></label>
          <label>Titel<input name="title" maxlength="180" required placeholder="Wobei können wir helfen?"></label>
          <label>Details<textarea name="details" rows="4" maxlength="5000" required></textarea></label>
          <button class="btn primary" type="submit">Anfrage senden</button>
        </form></section>
        <section class="card"><h2>Meine Concierge-Anfragen</h2>${concierge.requests.length ? concierge.requests.map(item => `<div class="row" style="padding:10px 0"><div class="row-main"><b>${esc(item.title)}</b><small>${esc(item.request_type_label)} · ${esc(item.status_label)} · ${dateTime(item.updated_at)}</small></div>${item.thread_id ? `<button class="btn ghost" type="button" data-p3-open-thread="${item.thread_id}">Nachrichten</button>` : ''}</div>`).join('') : '<p class="empty">Noch keine Concierge-Anfrage.</p>'}</section>
        <section class="card"><h2>Neue allgemeine Nachricht</h2><form class="form" data-p3-conversation-form><label>Betreff<input name="subject" maxlength="180" required></label><label>Nachricht<textarea name="body" rows="3" maxlength="5000" required></textarea></label><button class="btn primary" type="submit">Unterhaltung starten</button></form></section>
        <section class="card"><h2>Unterhaltungen</h2>${conversations.threads.length ? conversations.threads.map(thread => `<button class="row" style="width:100%;text-align:left;border:0;background:transparent;padding:11px 0" type="button" data-p3-open-thread="${thread.id}"><div class="row-main"><b>${esc(thread.subject)}</b><small>${thread.last_message ? esc(thread.last_message.body.slice(0, 90)) : 'Noch keine Nachricht'} · ${dateTime(thread.updated_at)}</small></div><span class="badge">${thread.status === 'open' ? 'Offen' : 'Geschlossen'}</span></button>`).join('') : '<p class="empty">Noch keine Unterhaltung.</p>'}</section>`;
      bindBack();
      target.querySelector('[data-p3-concierge-form]')?.addEventListener('submit', async event => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(event.currentTarget).entries());
        const button = event.currentTarget.querySelector('button');
        button.disabled = true;
        try { const result = await api('/concierge/', { method: 'POST', body: JSON.stringify(data) }); await showConversation(result.thread_id); }
        catch (error) { alert(error.message); button.disabled = false; }
      });
      target.querySelector('[data-p3-conversation-form]')?.addEventListener('submit', async event => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(event.currentTarget).entries());
        const button = event.currentTarget.querySelector('button');
        button.disabled = true;
        try { const result = await api('/conversations/', { method: 'POST', body: JSON.stringify(data) }); await showConversation(result.thread_id); }
        catch (error) { alert(error.message); button.disabled = false; }
      });
      target.querySelectorAll('[data-p3-open-thread]').forEach(button => button.addEventListener('click', () => showConversation(button.dataset.p3OpenThread)));
    } catch (error) { fail(error, showConcierge); }
  }

  function enhanceMore() {
    const heading = [...document.querySelectorAll('.pagehead h1')].find(node => node.textContent.trim() === 'Mehr');
    if (!heading) return;
    const grid = heading.closest('.content')?.querySelector('.more-grid');
    if (!grid || grid.querySelector('[data-p3-route]')) return;
    const items = [
      ['gamification', '✦ Challenges'],
      ['events', '◆ Events'],
      ['concierge', '◎ Concierge'],
    ];
    items.forEach(([route, label]) => {
      const button = document.createElement('button');
      button.className = 'more-item';
      button.type = 'button';
      button.dataset.p3Route = route;
      button.textContent = label;
      grid.appendChild(button);
    });
    grid.querySelector('[data-p3-route="gamification"]')?.addEventListener('click', showGamification);
    grid.querySelector('[data-p3-route="events"]')?.addEventListener('click', showEvents);
    grid.querySelector('[data-p3-route="concierge"]')?.addEventListener('click', showConcierge);
  }

  const observer = new MutationObserver(enhanceMore);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', enhanceMore);
})();
