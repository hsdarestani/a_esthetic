(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const photoUrls = new Set();

  const token = () => localStorage.getItem('aplus_token') || '';
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const euro = cents => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format((Number(cents) || 0) / 100);
  const dateOnly = value => value ? new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(`${value}T12:00:00`)) : '–';
  const dateTime = value => value ? new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '–';

  function clearPhotoUrls() {
    photoUrls.forEach(url => URL.revokeObjectURL(url));
    photoUrls.clear();
  }

  function humanError(code) {
    const errors = {
      authentication_required: 'Bitte melden Sie sich erneut an.',
      title_required: 'Bitte geben Sie einen Titel ein.',
      album_not_found: 'Dieses Album wurde nicht gefunden.',
      photo_not_found: 'Dieses Foto wurde nicht gefunden.',
      health_data_consent_required: 'Bitte erteilen Sie zuerst die Einwilligung für private Verlaufsfotos.',
      photo_required: 'Bitte wählen Sie ein Foto aus.',
      unsupported_image_type: 'Bitte verwenden Sie JPEG, PNG, WebP oder HEIC.',
      photo_too_large: 'Das Foto darf maximal 8 MB groß sein.',
      aftercare_task_not_found: 'Diese Nachsorge-Aufgabe wurde nicht gefunden.',
      followup_not_found: 'Dieses Follow-up wurde nicht gefunden.',
      response_required: 'Bitte schreiben Sie eine Rückmeldung oder fordern Sie Kontakt an.',
      beauty_plan_not_found: 'Dieser Beauty Plan wurde nicht gefunden.',
      beauty_plan_step_not_found: 'Dieser Schritt wurde nicht gefunden.',
      invalid_target_date: 'Bitte prüfen Sie das Zieldatum.',
      invalid_due_date: 'Bitte prüfen Sie das Datum des Schritts.',
      invalid_budget: 'Bitte prüfen Sie das Budget.'
    };
    return errors[code] || 'Die Aktion konnte nicht durchgeführt werden.';
  }

  async function p1Api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
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

  function content() {
    return document.querySelector('.shell .content');
  }

  function backMarkup(kicker, title, subtitle) {
    return `<div class="pagehead"><span>${esc(kicker)}</span><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>
      <div class="actions" style="margin-bottom:12px"><button class="btn ghost" type="button" data-p1-back>← Mehr</button></div>`;
  }

  function bindBack() {
    document.querySelector('[data-p1-back]')?.addEventListener('click', () => {
      clearPhotoUrls();
      const more = document.querySelector('.nav [data-route="more"]');
      if (more) more.click();
    });
  }

  function p1Loading(kicker, title, subtitle) {
    const target = content();
    if (!target) return false;
    clearPhotoUrls();
    target.innerHTML = `${backMarkup(kicker, title, subtitle)}<div class="loading">Wird geladen…</div>`;
    bindBack();
    return true;
  }

  function p1Fail(error, retry) {
    const target = content();
    if (!target) return;
    target.innerHTML += `<div class="errorbox">${esc(error.message)}</div><div class="actions"><button class="btn primary" type="button" data-p1-retry>Erneut versuchen</button></div>`;
    target.querySelector('[data-p1-retry]')?.addEventListener('click', retry);
  }

  async function loadProtectedPhotos() {
    const images = [...document.querySelectorAll('img[data-p1-photo]')];
    await Promise.all(images.map(async image => {
      try {
        const response = await fetch(`${API_BASE}/progress/photo/${image.dataset.p1Photo}/`, {
          headers: { Authorization: `Bearer ${token()}` },
        });
        if (!response.ok) throw new Error('photo_failed');
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        photoUrls.add(url);
        image.src = url;
      } catch (_) {
        image.replaceWith(Object.assign(document.createElement('div'), { className: 'empty', textContent: 'Foto nicht verfügbar' }));
      }
    }));
  }

  async function showProgress() {
    if (!p1Loading('Privat & geschützt', 'Fortschritt', 'Vorher-, Nachher- und Verlaufsfotos nur für Ihr Konto.')) return;
    try {
      const data = await p1Api('/progress/');
      const target = content();
      target.innerHTML = `${backMarkup('Privat & geschützt', 'Fortschritt', 'Vorher-, Nachher- und Verlaufsfotos nur für Ihr Konto.')}
        <div class="notice">${esc(data.privacy_note)}</div>
        <section class="card">
          <h2>Einwilligung</h2>
          <p class="muted">Für den Upload privater Verlaufsfotos ist eine ausdrückliche Einwilligung zur Verarbeitung dieser Daten erforderlich.</p>
          ${data.health_data_consent
            ? '<div class="actions"><span class="badge">Einwilligung aktiv</span><button class="btn ghost" type="button" data-p1-consent="0">Einwilligung widerrufen</button></div>'
            : '<div class="actions"><button class="btn primary" type="button" data-p1-consent="1">Einwilligen & Foto-Funktion aktivieren</button></div>'}
        </section>
        <section class="card">
          <h2>Neues Album</h2>
          <form id="p1-album-form" class="form">
            <label>Titel<input name="title" maxlength="160" required placeholder="z. B. Mein Verlauf"></label>
            <label>Notiz<textarea name="description" rows="2" maxlength="3000" placeholder="Optional"></textarea></label>
            <button class="btn primary" type="submit">Album erstellen</button>
          </form>
        </section>
        ${data.albums.length ? data.albums.map(album => `
          <section class="card" data-p1-album="${album.id}">
            <div class="row"><div class="row-main"><h2 style="margin:0">${esc(album.title)}</h2><small>${esc(album.description || 'Privates Album')}</small></div><button class="btn ghost" type="button" data-p1-delete-album="${album.id}">Löschen</button></div>
            <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0">
              ${album.photos.length ? album.photos.map(photo => `<div><div style="aspect-ratio:1/1;border-radius:14px;overflow:hidden;background:#eee"><img data-p1-photo="${photo.id}" alt="${esc(photo.kind_label)}" style="width:100%;height:100%;object-fit:cover"></div><div class="row"><small>${esc(photo.kind_label)} · ${dateTime(photo.taken_at)}</small><button type="button" class="btn ghost" data-p1-delete-photo="${photo.id}">×</button></div></div>`).join('') : '<p class="empty">Noch keine Fotos.</p>'}
            </div>
            ${data.health_data_consent ? `<form class="form" data-p1-upload="${album.id}">
              <label>Art<select name="kind"><option value="before">Vorher</option><option value="progress" selected>Verlauf</option><option value="after">Nachher</option></select></label>
              <label>Foto<input name="photo" type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" required></label>
              <button class="btn primary" type="submit">Foto geschützt hochladen</button>
            </form>` : '<p class="muted">Upload ist erst nach Einwilligung möglich.</p>'}
          </section>`).join('') : '<section class="card"><p class="empty">Noch kein privates Verlaufsalbum.</p></section>'}`;
      bindBack();

      target.querySelector('[data-p1-consent]')?.addEventListener('click', async event => {
        const accepted = event.currentTarget.dataset.p1Consent === '1';
        if (!accepted && !confirm('Einwilligung widerrufen? Vorhandene Fotos bleiben für Sie sichtbar und können weiterhin gelöscht werden; neue Uploads werden blockiert.')) return;
        try {
          await p1Api('/progress/consent/', { method: 'POST', body: JSON.stringify({ accepted }) });
          await showProgress();
        } catch (error) { alert(error.message); }
      });

      target.querySelector('#p1-album-form')?.addEventListener('submit', async event => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        try {
          await p1Api('/progress/', { method: 'POST', body: JSON.stringify({ title: form.get('title'), description: form.get('description') }) });
          await showProgress();
        } catch (error) { alert(error.message); }
      });

      target.querySelectorAll('[data-p1-upload]').forEach(form => form.addEventListener('submit', async event => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        const button = event.currentTarget.querySelector('button');
        button.disabled = true;
        button.textContent = 'Upload…';
        try {
          await p1Api(`/progress/${event.currentTarget.dataset.p1Upload}/upload/`, { method: 'POST', body: formData });
          await showProgress();
        } catch (error) {
          alert(error.message);
          button.disabled = false;
          button.textContent = 'Foto geschützt hochladen';
        }
      }));

      target.querySelectorAll('[data-p1-delete-photo]').forEach(button => button.addEventListener('click', async () => {
        if (!confirm('Dieses private Foto endgültig löschen?')) return;
        try { await p1Api(`/progress/photo/${button.dataset.p1DeletePhoto}/`, { method: 'DELETE' }); await showProgress(); }
        catch (error) { alert(error.message); }
      }));
      target.querySelectorAll('[data-p1-delete-album]').forEach(button => button.addEventListener('click', async () => {
        if (!confirm('Dieses Album und alle enthaltenen Fotos endgültig löschen?')) return;
        try { await p1Api(`/progress/${button.dataset.p1DeleteAlbum}/delete/`, { method: 'DELETE' }); await showProgress(); }
        catch (error) { alert(error.message); }
      }));

      await loadProtectedPhotos();
    } catch (error) { p1Fail(error, showProgress); }
  }

  async function showAftercare() {
    if (!p1Loading('A+ Begleitung', 'Nachsorge & Follow-up', 'Freigegebene Hinweise, Checklisten und direkter Kontakt.')) return;
    try {
      const data = await p1Api('/aftercare/');
      const target = content();
      target.innerHTML = `${backMarkup('A+ Begleitung', 'Nachsorge & Follow-up', 'Freigegebene Hinweise, Checklisten und direkter Kontakt.')}
        <div class="notice">${esc(data.safety_note)}</div>
        ${data.assigned.length ? data.assigned.map(item => `
          <section class="card">
            <div class="row"><div class="row-main"><h2 style="margin:0">${esc(item.title)}</h2><small>${esc(item.service)} · Version ${esc(item.version)}</small></div>${item.completed_at ? '<span class="badge">Erledigt</span>' : ''}</div>
            <p>${esc(item.introduction || '')}</p>${item.approved_by ? `<p class="muted">Freigegeben: ${esc(item.approved_by)}</p>` : ''}
            ${item.tasks.length ? item.tasks.map(task => `<label class="check" style="align-items:flex-start;margin:10px 0"><input type="checkbox" data-p1-aftercare-task="${task.status_id}" ${task.completed ? 'checked' : ''}><span><b>${esc(task.title)}</b><small style="display:block">${esc(task.description || task.task_type_label)}</small>${task.warning_sign ? '<small style="display:block;font-weight:700">Bei Unsicherheit bitte direkt A+ kontaktieren.</small>' : ''}</span></label>`).join('') : '<p class="empty">Keine Aufgaben hinterlegt.</p>'}
          </section>`).join('') : '<section class="card"><p class="empty">Aktuell ist keine Nachsorge-Checkliste zugeordnet.</p></section>'}
        <section class="card"><h2>Follow-up</h2>${data.followups.length ? data.followups.map(item => `
          <div class="separator"></div><div class="row"><div class="row-main"><b>${esc(item.title)}</b><small>${dateTime(item.due_at)} · ${esc(item.status)}</small></div>${item.requires_review ? '<span class="badge">A+ prüft</span>' : ''}</div>
          ${item.questions?.length ? `<ul>${item.questions.map(q => `<li>${esc(typeof q === 'string' ? q : q.text || q.question || JSON.stringify(q))}</li>`).join('')}</ul>` : ''}
          <form class="form" data-p1-followup="${item.id}"><label>Rückmeldung<textarea name="response" rows="2" maxlength="3000">${esc(item.customer_response?.text || '')}</textarea></label><label class="check"><input type="checkbox" name="request_contact" ${item.customer_response?.request_contact ? 'checked' : ''}><span>Bitte A+ Team kontaktieren lassen</span></label><button class="btn primary" type="submit">Rückmeldung senden</button></form>`).join('') : '<p class="empty">Kein offenes Follow-up.</p>'}</section>`;
      bindBack();
      target.querySelectorAll('[data-p1-aftercare-task]').forEach(input => input.addEventListener('change', async () => {
        input.disabled = true;
        try { await p1Api(`/aftercare/task/${input.dataset.p1AftercareTask}/toggle/`, { method: 'POST', body: '{}' }); await showAftercare(); }
        catch (error) { input.checked = !input.checked; input.disabled = false; alert(error.message); }
      }));
      target.querySelectorAll('[data-p1-followup]').forEach(form => form.addEventListener('submit', async event => {
        event.preventDefault();
        const values = new FormData(event.currentTarget);
        try {
          await p1Api(`/aftercare/followup/${event.currentTarget.dataset.p1Followup}/response/`, { method: 'POST', body: JSON.stringify({ response: values.get('response'), request_contact: values.get('request_contact') === 'on' }) });
          await showAftercare();
        } catch (error) { alert(error.message); }
      }));
    } catch (error) { p1Fail(error, showAftercare); }
  }

  async function showBeautyPlans() {
    if (!p1Loading('Persönliche Organisation', 'Beauty Plan', 'Ziele, Journeys, Budget und eigene Schritte.')) return;
    try {
      const data = await p1Api('/beauty-plans/');
      const target = content();
      target.innerHTML = `${backMarkup('Persönliche Organisation', 'Beauty Plan', 'Ziele, Journeys, Budget und eigene Schritte.')}
        <div class="notice">${esc(data.safety_note)}</div>
        <section class="card"><h2>Neuen Plan erstellen</h2><form id="p1-plan-form" class="form">
          <label>Titel<input name="title" maxlength="180" required placeholder="z. B. Summer Routine"></label>
          <label>Journey<select name="journey_type">${data.journeys.map(j => `<option value="${esc(j.value)}">${esc(j.label)}</option>`).join('')}</select></label>
          <label>Ziel<textarea name="goal" rows="2" maxlength="5000" placeholder="Ihr persönliches organisatorisches Ziel"></textarea></label>
          <label>Zieldatum<input name="target_date" type="date"></label>
          <label>Monatsbudget (€)<input name="monthly_budget" type="number" min="0" step="0.01" inputmode="decimal"></label>
          <button class="btn primary" type="submit">Beauty Plan erstellen</button>
        </form></section>
        ${data.plans.filter(plan => plan.status !== 'archived').length ? data.plans.filter(plan => plan.status !== 'archived').map(plan => `
          <section class="card">
            <div class="row"><div class="row-main"><h2 style="margin:0">${esc(plan.title)}</h2><small>${esc(plan.journey_label)}${plan.target_date ? ` · Ziel ${dateOnly(plan.target_date)}` : ''}</small></div><span class="badge">${plan.progress_percent}%</span></div>
            ${plan.goal ? `<p>${esc(plan.goal)}</p>` : ''}<p class="muted">Monatsbudget: ${euro(plan.monthly_budget_cents)}</p>
            ${plan.steps.length ? plan.steps.map(step => `<label class="check" style="align-items:flex-start;margin:10px 0"><input type="checkbox" data-p1-plan-step="${step.id}" ${step.completed ? 'checked' : ''}><span><b>${esc(step.title)}</b><small style="display:block">${esc(step.step_type_label)}${step.due_on ? ` · ${dateOnly(step.due_on)}` : ''}${step.estimated_cost_cents ? ` · ${euro(step.estimated_cost_cents)}` : ''}</small>${step.description ? `<small style="display:block">${esc(step.description)}</small>` : ''}</span></label>`).join('') : '<p class="empty">Noch keine Schritte.</p>'}
            <div class="separator"></div><form class="form" data-p1-add-step="${plan.id}"><label>Neuer Schritt<input name="title" maxlength="180" required placeholder="Eigener organisatorischer Schritt"></label><label>Typ<select name="step_type">${data.step_types.map(t => `<option value="${esc(t.value)}">${esc(t.label)}</option>`).join('')}</select></label><label>Fällig am<input name="due_on" type="date"></label><label>Geschätzte Kosten (€)<input name="cost" type="number" min="0" step="0.01"></label><button class="btn ghost" type="submit">Schritt hinzufügen</button></form>
            <div class="actions"><button class="btn ghost" type="button" data-p1-archive-plan="${plan.id}">Plan archivieren</button></div>
          </section>`).join('') : '<section class="card"><p class="empty">Noch kein Beauty Plan.</p></section>'}`;
      bindBack();
      target.querySelector('#p1-plan-form')?.addEventListener('submit', async event => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const monthly = Math.round((Number(form.get('monthly_budget')) || 0) * 100);
        try {
          await p1Api('/beauty-plans/', { method: 'POST', body: JSON.stringify({ title: form.get('title'), journey_type: form.get('journey_type'), goal: form.get('goal'), target_date: form.get('target_date') || null, monthly_budget_cents: monthly }) });
          await showBeautyPlans();
        } catch (error) { alert(error.message); }
      });
      target.querySelectorAll('[data-p1-add-step]').forEach(form => form.addEventListener('submit', async event => {
        event.preventDefault();
        const values = new FormData(event.currentTarget);
        try {
          await p1Api(`/beauty-plans/${event.currentTarget.dataset.p1AddStep}/steps/`, { method: 'POST', body: JSON.stringify({ title: values.get('title'), step_type: values.get('step_type'), due_on: values.get('due_on') || null, estimated_cost_cents: Math.round((Number(values.get('cost')) || 0) * 100) }) });
          await showBeautyPlans();
        } catch (error) { alert(error.message); }
      }));
      target.querySelectorAll('[data-p1-plan-step]').forEach(input => input.addEventListener('change', async () => {
        input.disabled = true;
        try { await p1Api(`/beauty-plans/steps/${input.dataset.p1PlanStep}/toggle/`, { method: 'POST', body: '{}' }); await showBeautyPlans(); }
        catch (error) { input.checked = !input.checked; input.disabled = false; alert(error.message); }
      }));
      target.querySelectorAll('[data-p1-archive-plan]').forEach(button => button.addEventListener('click', async () => {
        if (!confirm('Diesen Beauty Plan archivieren?')) return;
        try { await p1Api(`/beauty-plans/${button.dataset.p1ArchivePlan}/archive/`, { method: 'POST', body: '{}' }); await showBeautyPlans(); }
        catch (error) { alert(error.message); }
      }));
    } catch (error) { p1Fail(error, showBeautyPlans); }
  }

  function enhanceMore() {
    const heading = [...document.querySelectorAll('.pagehead h1')].find(node => node.textContent.trim() === 'Mehr');
    if (!heading) return;
    const grid = heading.closest('.content')?.querySelector('.more-grid');
    if (!grid || grid.querySelector('[data-p1-route]')) return;
    const items = [
      ['progress', '◫ Fortschritt'],
      ['aftercare', '✓ Nachsorge'],
      ['plans', '✦ Beauty Plan'],
    ];
    items.forEach(([route, label]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.p1Route = route;
      button.textContent = label;
      grid.appendChild(button);
    });
    grid.querySelector('[data-p1-route="progress"]')?.addEventListener('click', showProgress);
    grid.querySelector('[data-p1-route="aftercare"]')?.addEventListener('click', showAftercare);
    grid.querySelector('[data-p1-route="plans"]')?.addEventListener('click', showBeautyPlans);
  }

  const observer = new MutationObserver(enhanceMore);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', enhanceMore);
  setTimeout(enhanceMore, 0);
})();
