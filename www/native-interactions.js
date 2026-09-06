(() => {
  'use strict';

  const API = 'https://esthetic.smarbiz.sbs/api/mobile';
  const token = () => localStorage.getItem('aplus_token') || '';
  let previewUrl = '';

  function authHeaders(extra = {}) {
    return { ...extra, ...(token() ? { Authorization: `Bearer ${token()}` } : {}) };
  }

  function showInlineNotice(button, text) {
    const old = button.parentElement?.querySelector?.('[data-native-action-error]');
    old?.remove();
    const node = document.createElement('div');
    node.dataset.nativeActionError = '1';
    node.className = 'notice error';
    node.textContent = text;
    button.parentElement?.appendChild(node);
  }

  function closePreview(overlay) {
    overlay?.remove();
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = '';
    }
  }

  function previewShell(title = 'Dokument') {
    const overlay = document.createElement('div');
    overlay.className = 'record-preview-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.innerHTML = `<section class="record-preview-card">
      <header class="record-preview-head"><strong>${String(title).replace(/[&<>"']/g, '')}</strong><button type="button" class="record-preview-close" aria-label="Schließen">×</button></header>
      <div class="record-preview-body"><div class="record-preview-loading">Dokument wird geladen …</div></div>
    </section>`;
    document.body.appendChild(overlay);
    overlay.querySelector('.record-preview-close').onclick = () => closePreview(overlay);
    overlay.addEventListener('click', event => { if (event.target === overlay) closePreview(overlay); });
    return overlay;
  }

  async function openRecord(button) {
    const recordId = button.dataset.recordFile || '';
    if (!recordId || !token()) return;
    const overlay = previewShell('Patientenakte');
    button.disabled = true;
    try {
      const response = await fetch(`${API}/patient-records/${encodeURIComponent(recordId)}/file/`, {
        headers: authHeaders(), cache: 'no-store',
      });
      if (!response.ok) throw new Error('file_open_failed');
      const blob = await response.blob();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = URL.createObjectURL(blob);
      const type = (blob.type || response.headers.get('content-type') || '').toLowerCase();
      const body = overlay.querySelector('.record-preview-body');
      if (type.startsWith('image/')) {
        body.innerHTML = `<img alt="Patientendokument">`;
        body.querySelector('img').src = previewUrl;
      } else if (type.includes('pdf')) {
        body.innerHTML = `<iframe title="Patientendokument"></iframe>`;
        body.querySelector('iframe').src = previewUrl;
      } else {
        body.innerHTML = `<div class="record-preview-fallback">Für diesen Dateityp ist keine Vorschau verfügbar.<br><a class="secondary" download="APlus-Dokument">Datei herunterladen</a></div>`;
        body.querySelector('a').href = previewUrl;
      }
    } catch (_) {
      closePreview(overlay);
      showInlineNotice(button, 'Datei konnte nicht geöffnet werden.');
    } finally {
      button.disabled = false;
    }
  }

  async function openGoogleReview(button) {
    // Open synchronously while the click still carries a user gesture. This avoids
    // WKWebView/Safari blocking the Google page after the async history write.
    let popup = null;
    try { popup = window.open('about:blank', '_blank'); } catch (_) {}
    button.disabled = true;
    try {
      const headers = authHeaders({ 'Content-Type': 'application/json' });
      const historyWrite = fetch(`${API}/reviews/`, {
        method: 'POST', headers, body: JSON.stringify({ action: 'opened' }), cache: 'no-store',
      }).catch(() => null);
      const response = await fetch(`${API}/reviews/`, { headers: authHeaders(), cache: 'no-store' });
      if (!response.ok) throw new Error('review_url_failed');
      const data = await response.json();
      const url = String(data.review_url || '');
      if (!/^https:\/\//i.test(url)) throw new Error('review_url_missing');
      await historyWrite;
      if (popup && !popup.closed) {
        popup.location.replace(url);
      } else {
        const a = document.createElement('a');
        a.href = url; a.target = '_blank'; a.rel = 'noopener';
        document.body.appendChild(a); a.click(); a.remove();
      }
    } catch (_) {
      try { popup?.close(); } catch (_) {}
      showInlineNotice(button, 'Google Bewertung konnte gerade nicht geöffnet werden.');
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener('click', event => {
    const review = event.target?.closest?.('[data-open-review]');
    if (review) {
      event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation();
      openGoogleReview(review);
      return;
    }
    const file = event.target?.closest?.('[data-record-file][data-download="0"]');
    if (file) {
      event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation();
      openRecord(file);
    }
  }, true);

  window.addEventListener('pagehide', () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  });
})();
