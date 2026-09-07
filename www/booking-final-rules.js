(() => {
  'use strict';

  let selectedServiceName = '';
  const noReturningQuestion = name => {
    const value = String(name || '').toLowerCase();
    return (value.includes('botox') && (value.includes('bestand') || value.includes('bestan'))) || value.includes('kontrolltermin') || value.includes('kontroll termin');
  };

  function serviceNameFromButton(button) {
    return button?.querySelector('strong')?.textContent?.trim() || '';
  }

  function removeMoneyAndConditionalFields() {
    document.querySelectorAll('.book-treatment-card .book-meta').forEach(meta => {
      [...meta.children].slice(1).forEach(node => node.remove());
    });
    if (!noReturningQuestion(selectedServiceName)) return;
    document.querySelectorAll('[data-confirm-form] label').forEach(label => {
      const text = (label.textContent || '').toLowerCase();
      const hasReturningField = label.querySelector('[name="returning_customer"], [name="returning"], [name="been_before"]');
      if (hasReturningField || text.includes('schon einmal') || text.includes('bereits bei uns') || text.includes('vorher bei uns')) {
        label.remove();
      }
    });
    document.querySelectorAll('[name="returning_customer"], [name="returning"], [name="been_before"]').forEach(input => input.closest('label,div')?.remove());
  }

  document.addEventListener('click', event => {
    const button = event.target?.closest?.('[data-service-id]');
    if (!button) return;
    selectedServiceName = serviceNameFromButton(button);
    requestAnimationFrame(removeMoneyAndConditionalFields);
  }, true);

  const observer = new MutationObserver(removeMoneyAndConditionalFields);
  observer.observe(document.documentElement, {childList:true, subtree:true});
  window.addEventListener('DOMContentLoaded', removeMoneyAndConditionalFields);
  setTimeout(removeMoneyAndConditionalFields, 0);
})();
