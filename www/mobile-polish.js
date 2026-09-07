(() => {
  'use strict';

  function markPlatform() {
    let platform = '';
    try { platform = window.Capacitor?.getPlatform?.() || ''; } catch (_) {}
    if (!platform && /Android/i.test(navigator.userAgent) && window.Capacitor) platform = 'android';
    if (platform) document.documentElement.classList.add(`aplus-${platform}`);
  }

  function cleanLogoutOverlay(target) {
    if (!target?.closest?.('[data-logout]')) return;
    setTimeout(() => {
      document.querySelectorAll('.settings-overlay').forEach(node => node.remove());
    }, 0);
  }

  function enhanceRecords() {
    const root = document.getElementById('app');
    const form = root?.querySelector('[data-upload]');
    if (!form) return;

    const box = form.closest('.upload-box');
    if (!box || box.dataset.polished === '1') return;
    box.dataset.polished = '1';
    box.classList.add('record-composer');

    const pageHead = root.querySelector('.page-head');
    pageHead?.classList.add('records-page-head');

    const head = document.createElement('div');
    head.className = 'record-composer-head';
    head.innerHTML = `
      <div class="record-composer-mark" aria-hidden="true">+</div>
      <div class="record-composer-copy">
        <span>Neuer Eintrag</span>
        <strong>Zur Patientenakte hinzufügen</strong>
        <small>Dokument, Foto oder persönliche Notiz sicher ablegen.</small>
      </div>`;
    box.prepend(head);

    const fileInput = form.querySelector('input[type="file"]');
    if (fileInput) {
      const label = fileInput.closest('.field');
      if (label) {
        label.classList.add('record-file-field');
        const labelText = label.querySelector(':scope > span');
        if (labelText) labelText.textContent = 'Datei';

        const picker = document.createElement('div');
        picker.className = 'record-file-picker';
        picker.innerHTML = `
          <div class="record-file-icon" aria-hidden="true">↑</div>
          <div class="record-file-copy">
            <strong>Datei auswählen</strong>
            <span data-file-label>PDF, Bild oder Dokument</span>
          </div>
          <div class="record-file-plus" aria-hidden="true">+</div>`;
        fileInput.replaceWith(picker);
        picker.appendChild(fileInput);

        const fileLabel = picker.querySelector('[data-file-label]');
        fileInput.addEventListener('change', () => {
          if (fileLabel) fileLabel.textContent = fileInput.files?.[0]?.name || 'PDF, Bild oder Dokument';
        });
      }
    }

    const historyTitle = [...root.querySelectorAll('.section-title')]
      .find(node => node.querySelector('h2')?.textContent?.trim() === 'Verlauf');
    historyTitle?.classList.add('records-history-title');

    const empty = historyTitle?.nextElementSibling;
    if (empty?.classList.contains('empty')) {
      empty.classList.add('records-empty');
      empty.innerHTML = `
        <div class="records-empty-icon" aria-hidden="true">▤</div>
        <strong>Noch keine Einträge</strong>
        <span>Dokumente und Notizen aus der Praxis oder von Ihnen erscheinen hier chronologisch.</span>`;
    }

    root.querySelectorAll('.record-row').forEach(row => {
      if (row.dataset.polished === '1') return;
      row.dataset.polished = '1';
      row.classList.add('record-polished');

      const source = row.querySelector('.record-source');
      const sourceText = source?.textContent?.trim() || '';
      const [originRaw, kindRaw] = sourceText.split('·').map(v => v.trim());
      if (source) {
        source.innerHTML = `<span class="record-origin-badge"></span><span class="record-kind-badge"></span>`;
        source.querySelector('.record-origin-badge').textContent = originRaw || 'Akte';
        source.querySelector('.record-kind-badge').textContent = kindRaw || 'Eintrag';
      }

      let icon = '▤';
      const kind = (kindRaw || '').toLowerCase();
      if (kind.includes('foto')) icon = '◌';
      if (kind.includes('notiz')) icon = '✎';

      const children = [...row.childNodes];
      const body = document.createElement('div');
      body.className = 'record-row-body';
      children.forEach(child => body.appendChild(child));

      const mark = document.createElement('div');
      mark.className = 'record-type-icon';
      mark.setAttribute('aria-hidden', 'true');
      mark.textContent = icon;
      row.append(mark, body);
    });
  }

  let scheduled = false;
  function scheduleEnhance() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      enhanceRecords();
    });
  }

  markPlatform();
  document.addEventListener('click', e => cleanLogoutOverlay(e.target), true);

  const root = document.getElementById('app');
  if (root) new MutationObserver(scheduleEnhance).observe(root, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', scheduleEnhance, { once: true });
  window.addEventListener('pageshow', scheduleEnhance);
  setTimeout(scheduleEnhance, 0);
})();
