(() => {
  const origin = window.APlusRuntime.origin;
  const escape = value => String(value ?? '').replace(/[&<>'"]/g, ch =>
    ({'&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;'}[ch]));
  const activeRoot = () => document.getElementById('app');
  const photo = '<div class="ma-photo"><img src="./assets/site/clinic-mobile.webp" alt="" fetchpriority="high"></div>';
  const identity = '<div class="ma-identity"><img src="./assets/logo.svg" alt=""><span>A+ ESTHETIC<small>Frankfurt am Main</small></span></div>';

  function layout({heading, description = '', back = '', hero = false, content}) {
    return `<main class="ma-auth${hero ? ' ma-auth-hero' : ''}">${hero ? photo : ''}
      <div class="ma-panel">${identity}${back ? '<button class="ma-back" type="button" data-ma-back>‹ Zurück</button>' : ''}
      <h1 tabindex="-1">${escape(heading)}</h1>${description ? `<p class="ma-description">${escape(description)}</p>` : ''}
      ${content}</div></main>`;
  }

  function field(label, name, attributes, password = false) {
    return `<div class="ma-field"><label for="ma-${name}">${label}</label><div class="ma-input">
      <input id="ma-${name}" name="${name}" ${attributes} aria-describedby="ma-${name}-error">
      ${password ? `<button class="ma-reveal" type="button" data-ma-reveal="${name}" aria-pressed="false" aria-label="Passwort anzeigen">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z"/><circle cx="12" cy="12" r="2.5"/></svg>
      </button>` : ''}</div><small class="ma-field-error" id="ma-${name}-error" hidden></small></div>`;
  }

  const error = (text = '') => `<div class="ma-alert" role="alert" data-ma-error ${text ? '' : 'hidden'}>${escape(text)}</div>`;
  function report(form, text, fieldName) {
    if (fieldName) {
      const input = form.elements.namedItem(fieldName);
      const hint = document.getElementById(`ma-${fieldName}-error`);
      if (input && hint) {
        input.setAttribute('aria-invalid', 'true');
        hint.textContent = text;
        hint.hidden = false;
        input.focus();
        return;
      }
    }
    const alert = form.querySelector('[data-ma-error]');
    alert.textContent = text;
    alert.hidden = !text;
  }

  function bindFields(form) {
    form.addEventListener('click', event => {
      const toggle = event.target.closest('[data-ma-reveal]');
      if (!toggle) return;
      const input = form.elements.namedItem(toggle.dataset.maReveal);
      const shown = input.type === 'password';
      input.type = shown ? 'text' : 'password';
      toggle.setAttribute('aria-pressed', String(shown));
      toggle.setAttribute('aria-label', shown ? 'Passwort ausblenden' : 'Passwort anzeigen');
    });
    form.addEventListener('input', event => {
      const input = event.target;
      input.removeAttribute('aria-invalid');
      const hint = document.getElementById(`ma-${input.name}-error`);
      if (hint) hint.hidden = true;
      const alert = form.querySelector('[data-ma-error]');
      if (alert) alert.hidden = true;
    });
  }

  function submitState(form, busy, pending, label) {
    const button = form.querySelector('button[type="submit"]');
    button.disabled = busy;
    button.textContent = busy ? pending : label;
    form.setAttribute('aria-busy', String(busy));
  }

  function login({message, authenticate, signup}) {
    const host = activeRoot();
    host.innerHTML = layout({
      heading: 'Willkommen zurück',
      description: 'Verwalten Sie Ihre Termine und Ihr A+ Konto.',
      hero: true,
      content: `<form class="ma-form" data-login data-own-submit novalidate>
        ${error(message)}
        ${field('E-Mail-Adresse', 'email', 'type="email" autocomplete="username" autocapitalize="none" inputmode="email" required')}
        ${field('Passwort', 'password', 'type="password" autocomplete="current-password" required', true)}
        <button type="button" class="ma-link ma-forgot" data-forgot-password>Passwort vergessen?</button>
        <button type="submit" class="ma-primary">Anmelden</button>
        <div class="ma-social" data-social-slot></div>
        <p class="ma-signup-link">Neu bei A+? <button class="ma-link" type="button" data-ma-signup>Konto erstellen</button></p>
      </form>`,
    });
    const form = host.querySelector('[data-login]');
    bindFields(form);
    const back = () => {
      const email = form.elements.email.value;
      login({message: '', authenticate, signup});
      activeRoot().querySelector('[name=email]').value = email;
      activeRoot().querySelector('h1').focus();
    };
    form.querySelector('[data-forgot-password]').onclick = () => recovery(back, form.elements.email.value);
    form.querySelector('[data-ma-signup]').onclick = () => signup(back);
    form.onsubmit = async event => {
      event.preventDefault();
      if (form.getAttribute('aria-busy') === 'true') return;
      if (!form.elements.email.validity.valid) return report(form, 'Bitte geben Sie eine gültige E-Mail-Adresse ein.', 'email');
      if (!form.elements.password.value) return report(form, 'Bitte geben Sie Ihr Passwort ein.', 'password');
      submitState(form, true, 'Anmeldung läuft …', 'Anmelden');
      try {
        await authenticate(form.elements.email.value, form.elements.password.value);
      } catch (failure) {
        report(form, failure?.code === 'invalid_credentials'
          ? 'E-Mail-Adresse oder Passwort ist nicht korrekt.'
          : 'Die Anmeldung ist gerade nicht möglich. Bitte versuchen Sie es erneut.');
      } finally {
        if (form.isConnected) submitState(form, false, '', 'Anmelden');
      }
    };
  }

  function recovery(back, email) {
    const host = activeRoot();
    host.innerHTML = layout({
      heading: 'Passwort zurücksetzen', back: true,
      description: 'Geben Sie die E-Mail-Adresse Ihres Kontos ein.',
      content: `<form class="ma-form" data-own-submit novalidate>
        ${error()}${field('E-Mail-Adresse', 'email', 'type="email" autocomplete="email" inputmode="email" required')}
        <button type="submit" class="ma-primary">Link anfordern</button>
      </form>`,
    });
    const form = host.querySelector('form');
    form.elements.email.value = email;
    host.querySelector('[data-ma-back]').onclick = back;
    host.querySelector('h1').focus();
    bindFields(form);
    form.onsubmit = async event => {
      event.preventDefault();
      if (form.getAttribute('aria-busy') === 'true') return;
      const input = form.elements.email;
      if (!input.validity.valid) return report(form, 'Bitte geben Sie eine gültige E-Mail-Adresse ein.', 'email');
      submitState(form, true, 'Link wird angefordert …', 'Link anfordern');
      try {
        const response = await fetch(origin + '/api/mobile/password-recovery/', {
          method: 'POST', credentials: 'omit', cache: 'no-store', aplusSilent: true,
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({email: input.value.trim()}),
        });
        if (!form.isConnected) return;
        if (!response.ok) {
          return report(form, response.status === 429
            ? 'Zu viele Anfragen. Bitte versuchen Sie es später erneut.'
            : 'Der Link konnte gerade nicht angefordert werden. Bitte versuchen Sie es erneut.');
        }
        host.innerHTML = layout({
          heading: 'E-Mail prüfen',
          description: 'Wenn ein Konto zu dieser Adresse besteht, erhalten Sie einen Link zum Zurücksetzen.',
          content: '<button type="button" class="ma-primary" data-ma-back>Zur Anmeldung</button>',
        });
        host.querySelector('[data-ma-back]').onclick = back;
        host.querySelector('h1').focus();
      } catch (_) {
        if (form.isConnected) report(form, 'Verbindung unterbrochen. Bitte versuchen Sie es erneut.');
      } finally {
        if (form.isConnected) submitState(form, false, '', 'Link anfordern');
      }
    };
  }

  window.APlusAuth = {layout, field, error, report, bindFields, submitState, login};
})();
