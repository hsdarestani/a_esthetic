(() => {
  'use strict';

  let scheduled = false;

  function enhanceLayer(layer) {
    if (!layer || layer.hidden) return;

    // Move the fixed overlay to <body>. This avoids transformed/scaled app ancestors
    // turning position:fixed into a clipped local overlay on mobile browsers.
    if (layer.parentElement !== document.body) document.body.appendChild(layer);

    const sheet = layer.querySelector('.a-confirm-sheet');
    if (!sheet || sheet.classList.contains('a-success-sheet') || sheet.dataset.mobileConfirmFixed === '1') return;
    sheet.dataset.mobileConfirmFixed = '1';

    const head = sheet.querySelector('.a-confirm-head');
    const handle = sheet.querySelector('.a-sheet-handle');
    const submit = sheet.querySelector('[data-confirm-book]');
    const change = sheet.querySelector('.a-confirm-change');
    const error = sheet.querySelector('[data-confirm-error]');
    if (!head || !submit) return;

    const scroll = document.createElement('div');
    scroll.className = 'a-confirm-scroll';

    // Everything between the header and the action buttons becomes the real
    // touch-scroll area. Existing listeners stay attached because nodes are moved,
    // not recreated.
    const movable = [...sheet.children].filter(node =>
      node !== handle && node !== head && node !== submit && node !== change && node !== error
    );
    movable.forEach(node => scroll.appendChild(node));

    const actions = document.createElement('div');
    actions.className = 'a-confirm-actions';
    if (error) actions.appendChild(error);
    actions.appendChild(submit);
    if (change) actions.appendChild(change);

    if (head.nextSibling) sheet.insertBefore(scroll, head.nextSibling);
    else sheet.appendChild(scroll);
    sheet.appendChild(actions);

    // Start at the top so the summary is immediately clear, while the primary CTA
    // remains visible in the sticky action area below.
    scroll.scrollTop = 0;

    // The handle now has a useful gesture: a deliberate downward swipe closes the sheet.
    if (handle && window.PointerEvent) {
      let startY = null;
      let delta = 0;
      handle.style.touchAction = 'none';
      handle.addEventListener('pointerdown', event => {
        startY = event.clientY;
        delta = 0;
        handle.setPointerCapture?.(event.pointerId);
      });
      handle.addEventListener('pointermove', event => {
        if (startY == null) return;
        delta = Math.max(0, event.clientY - startY);
        if (delta > 0) sheet.style.transform = `translateY(${Math.min(delta, 140)}px)`;
      });
      const finish = () => {
        if (startY == null) return;
        const shouldClose = delta > 90;
        startY = null;
        delta = 0;
        sheet.style.transform = '';
        if (shouldClose) sheet.querySelector('[data-close-confirm]')?.click();
      };
      handle.addEventListener('pointerup', finish);
      handle.addEventListener('pointercancel', finish);
    }
  }

  function run() {
    document.querySelectorAll('[data-confirm-layer]:not([hidden])').forEach(enhanceLayer);
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      run();
    });
  }

  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['hidden'],
  });

  window.addEventListener('DOMContentLoaded', run);
  setTimeout(run, 0);
})();
