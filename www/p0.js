(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const AUTH_BASE = 'https://esthetic.smarbiz.sbs/accounts';

  function token() {
    return localStorage.getItem('aplus_token') || '';
  }

  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  function p0Error(code) {
    const errors = {
      health_data_consent_required: 'Bitte stimmen Sie der Verarbeitung der hochgeladenen Gesundheitsdaten zu.',
      file_type: 'Dieser Dateityp wird nicht unterstützt.',
      file_empty: 'Die ausgewählte Datei ist leer.',
      file_size: 'Die Datei ist zu groß. Maximal 10 MB.',
      empty_record: 'Bitte wählen Sie eine Datei oder schreiben Sie eine Notiz.',
      invalid_kind: 'Bitte wählen Sie einen gültigen Dokumenttyp.',
      patient_record_service_unavailable: 'Die Patientenakte ist vorübergehend nicht erreichbar. Bitte versuchen Sie es erneut.',
      record_not_found: 'Das Dokument wurde nicht gefunden.'
    };
    return errors[code] || 'Die Anfrage konnte nicht ausgeführt werden.';
  }

  async function p0Api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    const isForm = options.body instanceof FormData;
    if (!isForm) headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) {
      const error = new Error(body.error || 'request_failed');
      error.code = body.error || 'request_failed';
      error.status = response.status;
      throw error;
    }
    return body;
  }

  function enhanceLogin() {
    const card = document.querySelector('.auth-card');
    if (!card || card.querySelector('.p0-auth-actions')) return;
    const legal = card.querySelector('.legal-links');
    if (!legal) return;
    const row = document.createElement('div');
    row.className = 'p0-auth-actions';
    row.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0;';
    row.innerHTML = `
      <a class="btn ghost" href="${AUTH_BASE}/signup/" target="_blank" rel="noopener">Konto erstellen</a>
      <a class="btn ghost" href="${AUTH_BASE}/password/reset/" target="_blank" rel="noopener">Passwort vergessen</a>`;
    legal.parentNode.insertBefore(row, legal);
  }

  function bytes(value) {
    const amount = Number(value) || 0;
    if (amount < 1024) return `${amount} B`;
    if (amount < 1024 * 1024) return `${Math.round(amount / 1024)} KB`;
    return `${(amount / (1024 * 1024)).toFixed(1)} MB`;
  }

  function shortDate(value) {
    if (!value) return '–';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '–';
    return new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(date);
  }

  async function openPatientFile(recordId, download = false) {
    const response = await fetch(`${API_BASE}/patient-records/${encodeURIComponent(recordId)}/file/${download ? '?download=1' : ''}`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    if (!response.ok) throw new Error('record_not_found');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    if (download) link.download = 'A-Plus-Patientendokument';
    else link.target = '_blank';
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }

  function patientRecordMarkup(record) {
    const origin = record.customer_uploaded ? 'Von Ihnen hochgeladen' : 'Von A+ Esthetic bereitgestellt';
    const sourceClass = record.customer_uploaded ? 'customer' : 'clinic';
    const fileActions = record.has_file ? `
      <div class="patient-doc-actions">
        <button type="button" class="btn ghost" data-patient-open="${esc(record.id)}">Öffnen</button>
        <button type="button" class="btn ghost" data-patient-download="${esc(record.id)}">Download</button>
      </div>` : '';
    const archive = record.customer_uploaded ? `<button type="button" class="patient-doc-archive" data-patient-archive="${esc(record.id)}">Aus meiner Ansicht entfernen</button>` : '';
    return `
      <article class="patient-doc-item">
        <div class="patient-doc-icon">${record.kind === 'photo' ? '▧' : record.kind === 'form' ? '✓' : record.kind === 'note' ? '≡' : '▤'}</div>
        <div class="patient-doc-main">
          <div class="patient-doc-meta"><span class="patient-doc-origin ${sourceClass}">${origin}</span><time>${shortDate(record.captured_at || record.created_at)}</time></div>
          <h3>${esc(record.title || 'Dokument')}</h3>
          ${record.appointment ? `<small class="patient-doc-appointment">${esc(record.appointment.service)} · ${shortDate(record.appointment.starts_at)}</small>` : ''}
          ${record.note ? `<p>${esc(record.note)}</p>` : ''}
          ${record.has_file ? `<small class="patient-doc-file">${esc(record.original_name || 'Datei')} · ${bytes(record.file_size)}</small>` : ''}
          ${fileActions}
          ${archive}
        </div>
      </article>`;
  }

  async function loadPatientRecords(card) {
    const target = card.querySelector('#p0-patient-records');
    try {
      const data = await p0Api('/patient-records/');
      card.dataset.healthConsent = data.health_data_consent ? '1' : '0';
      const consent = card.querySelector('#p0-health-consent-wrap');
      if (consent) consent.hidden = Boolean(data.health_data_consent);
      target.innerHTML = data.records.length
        ? data.records.map(patientRecordMarkup).join('')
        : '<div class="patient-doc-empty"><strong>Noch keine geteilten Dokumente</strong><span>Dokumente, die A+ Esthetic für Sie freigibt oder die Sie selbst hochladen, erscheinen hier.</span></div>';

      target.querySelectorAll('[data-patient-open]').forEach(button => button.addEventListener('click', async () => {
        button.disabled = true;
        try { await openPatientFile(button.dataset.patientOpen, false); }
        catch (error) { alert(p0Error(error.message)); }
        finally { button.disabled = false; }
      }));
      target.querySelectorAll('[data-patient-download]').forEach(button => button.addEventListener('click', async () => {
        button.disabled = true;
        try { await openPatientFile(button.dataset.patientDownload, true); }
        catch (error) { alert(p0Error(error.message)); }
        finally { button.disabled = false; }
      }));
      target.querySelectorAll('[data-patient-archive]').forEach(button => button.addEventListener('click', async () => {
        if (!confirm('Dieses eigene Dokument aus Ihrer App-Ansicht entfernen? Es bleibt aus Dokumentationsgründen in der Patientenakte der Praxis erhalten.')) return;
        button.disabled = true;
        try {
          await p0Api(`/patient-records/${button.dataset.patientArchive}/archive/`, { method: 'POST', body: '{}' });
          await loadPatientRecords(card);
        } catch (error) {
          alert(p0Error(error.code));
          button.disabled = false;
        }
      }));
    } catch (error) {
      target.innerHTML = `<div class="patient-doc-empty is-error"><strong>Patientenakte nicht erreichbar</strong><span>${esc(p0Error(error.code))}</span></div>`;
    }
  }

  function addPatientRecordCard(anchor) {
    if (document.getElementById('p0-patient-file')) return;
    const card = document.createElement('section');
    card.className = 'card patient-file-card';
    card.id = 'p0-patient-file';
    card.innerHTML = `
      <div class="patient-file-heading">
        <div><span class="patient-file-kicker">Geschützter Gesundheitsbereich</span><h2>Meine Patientenakte</h2><p class="muted">Eine gemeinsame Akte für Sie und A+ Esthetic. Sie sehen nur Dokumente, die für Ihr Kundenkonto freigegeben wurden, und Ihre eigenen Uploads.</p></div>
        <span class="patient-file-lock">⌾</span>
      </div>
      <div id="p0-patient-records"><p class="empty">Patientenakte wird geladen…</p></div>
      <details class="patient-upload-details">
        <summary>＋ Dokument oder Foto hochladen</summary>
        <form id="p0-patient-upload" class="patient-upload-form">
          <label>Typ<select name="kind"><option value="document">Dokument</option><option value="photo">Foto</option><option value="form">Formular</option><option value="note">Notiz</option><option value="other">Sonstiges</option></select></label>
          <label>Titel <small>optional bei einer Datei</small><input name="title" maxlength="180" placeholder="z. B. Befund, Laborbericht, Foto"></label>
          <label class="patient-file-picker"><span>＋</span><strong>Datei auswählen</strong><small>PDF, Bilder, Office oder Text · max. 10 MB</small><input type="file" name="file" accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt,.rtf,.csv,.heic,.heif"></label>
          <label>Notiz <small>optional</small><textarea name="note" rows="3" maxlength="6000" placeholder="Information für das A+ Team …"></textarea></label>
          <label class="patient-health-consent" id="p0-health-consent-wrap"><input type="checkbox" name="health_data_consent"><span>Ich stimme zu, dass die von mir hochgeladenen Gesundheitsdaten zur Dokumentation und Betreuung in meiner A+ Esthetic Patientenakte verarbeitet werden.</span></label>
          <p class="patient-upload-note">Uploads werden in die gemeinsame Patientenakte der Praxis übernommen. Entfernen aus der App löscht keine medizinisch erforderliche Dokumentation der Praxis.</p>
          <button class="btn primary" type="submit">Sicher hochladen</button>
        </form>
      </details>`;
    anchor.insertAdjacentElement('afterend', card);

    card.querySelector('#p0-patient-upload')?.addEventListener('submit', async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const data = new FormData(form);
      if (card.dataset.healthConsent !== '1' && data.get('health_data_consent') !== 'on') {
        alert(p0Error('health_data_consent_required'));
        return;
      }
      if (data.get('health_data_consent') === 'on') data.set('health_data_consent', '1');
      const file = data.get('file');
      if (file && file.size > 10 * 1024 * 1024) {
        alert(p0Error('file_size'));
        return;
      }
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      button.textContent = 'Wird sicher hochgeladen…';
      try {
        await p0Api('/patient-records/upload/', { method: 'POST', body: data });
        form.reset();
        card.querySelector('.patient-upload-details').open = false;
        await loadPatientRecords(card);
      } catch (error) {
        alert(p0Error(error.code));
      } finally {
        button.disabled = false;
        button.textContent = 'Sicher hochladen';
      }
    });
    loadPatientRecords(card);
  }

  async function enhanceProfile() {
    const profileForm = document.getElementById('profile-form');
    if (!profileForm) return;
    const cards = document.querySelectorAll('.content .card');
    const baseAnchor = cards[cards.length - 1] || profileForm.closest('.card');

    let privacyCard = document.getElementById('p0-privacy-tools');
    if (!privacyCard) {
      privacyCard = document.createElement('section');
      privacyCard.className = 'card';
      privacyCard.id = 'p0-privacy-tools';
      privacyCard.innerHTML = `
        <h2>Geräte & Daten</h2>
        <p class="muted">Aktive Sitzungen verwalten oder eine Datenkopie Ihres Customer-Club-Kontos erstellen.</p>
        <div id="p0-devices"><p class="empty">Geräte werden geladen…</p></div>
        <div class="actions"><button class="btn ghost" type="button" id="p0-export">Datenkopie herunterladen</button></div>`;
      baseAnchor.insertAdjacentElement('afterend', privacyCard);

      try {
        const data = await p0Api('/devices/');
        const target = privacyCard.querySelector('#p0-devices');
        target.innerHTML = data.devices.length ? data.devices.map(device => `
          <div class="row"><div class="row-main"><b>${device.current ? 'Dieses Gerät' : 'Gerät'}</b><small>${esc(device.device_name || 'A+ Esthetic App')} · ${new Date(device.last_seen_at).toLocaleString('de-DE')}</small></div>${device.revoked_at ? '<span class="badge">Abgemeldet</span>' : `<button class="btn ghost" type="button" data-p0-revoke="${device.id}">Abmelden</button>`}</div>`).join('') : '<p class="empty">Keine aktiven Geräte gefunden.</p>';
        target.querySelectorAll('[data-p0-revoke]').forEach(button => button.addEventListener('click', async () => {
          if (!confirm('Diese Gerätesitzung wirklich abmelden?')) return;
          try {
            await p0Api(`/devices/${button.dataset.p0Revoke}/revoke/`, { method: 'POST', body: '{}' });
            if (button.closest('.row')?.querySelector('b')?.textContent === 'Dieses Gerät') {
              localStorage.removeItem('aplus_token'); location.reload(); return;
            }
            button.textContent = 'Abgemeldet'; button.disabled = true;
          } catch (_) { alert('Die Gerätesitzung konnte nicht abgemeldet werden.'); }
        }));
      } catch (_) {
        privacyCard.querySelector('#p0-devices').innerHTML = '<p class="empty">Geräte konnten nicht geladen werden.</p>';
      }

      privacyCard.querySelector('#p0-export')?.addEventListener('click', async event => {
        const button = event.currentTarget;
        button.disabled = true;
        button.textContent = 'Daten werden erstellt…';
        try {
          const response = await fetch(`${API_BASE}/export/`, { headers: { Authorization: `Bearer ${token()}` } });
          if (!response.ok) throw new Error('export_failed');
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url; link.download = 'a-plus-esthetic-daten.json'; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
        } catch (_) { alert('Die Datenkopie konnte nicht erstellt werden.'); }
        finally { button.disabled = false; button.textContent = 'Datenkopie herunterladen'; }
      });
    }

    addPatientRecordCard(privacyCard);
  }

  function enhance() {
    enhanceLogin();
    enhanceProfile();
  }

  const observer = new MutationObserver(enhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', enhance);
  setTimeout(enhance, 0);
})();
