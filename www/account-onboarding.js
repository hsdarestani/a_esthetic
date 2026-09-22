(() => {
  'use strict';

  const API = 'https://esthetic.smarbiz.sbs/api/mobile';
  let cachedConfig = null;
  const root = () => document.getElementById('app');
  const token = () => localStorage.getItem('aplus_token') || '';
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));

  async function api(path, options={}) {
    const headers = new Headers(options.headers || {});
    if (token()) headers.set('Authorization', 'Bearer ' + token());
    if (options.json !== undefined) {
      headers.set('Content-Type', 'application/json');
      options.body = JSON.stringify(options.json);
    }
    const response = await fetch(API + path, {...options, headers, cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data?.ok === false) {
      const error = new Error(data?.message || data?.error || ('HTTP ' + response.status));
      error.code = data?.error || '';
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  function errorText(error) {
    const map = {
      invalid_phone:'Bitte geben Sie eine gültige Telefonnummer mit Ländervorwahl ein.',
      invalid_salutation:'Bitte wählen Sie Herr, Frau oder Divers.',
      name_required:'Vorname und Nachname sind erforderlich.',
      email_in_use:'Für diese E-Mail-Adresse besteht bereits ein Konto.',
      invalid_referral_code:'Der Empfehlungscode ist nicht gültig.',
      referral_code_used:'Dieser Empfehlungscode wurde bereits verwendet.',
      cannot_refer_yourself:'Der eigene Empfehlungscode kann nicht verwendet werden.',
      invalid_code:'Der Bestätigungscode ist nicht korrekt.',
      verification_expired:'Der Bestätigungscode ist abgelaufen. Bitte fordern Sie einen neuen an.',
      too_many_attempts:'Zu viele Versuche. Bitte fordern Sie einen neuen Code an.',
      sms_not_configured:'SMS-Bestätigung ist serverseitig noch nicht konfiguriert.',
      mail_relay_not_configured:'Der E-Mail-Versand ist momentan nicht verfügbar.',
      mail_relay_unavailable:'Der E-Mail-Versand ist momentan nicht erreichbar.',
      social_session_required:'Die Social-Anmeldung konnte nicht abgeschlossen werden.',
      invalid_google_token:'Google-Anmeldung konnte nicht verifiziert werden.',
      invalid_apple_token:'Apple-Anmeldung konnte nicht verifiziert werden.',
      social_email_missing:'Für diese Anmeldung wurde keine E-Mail-Adresse bereitgestellt.',
      social_account_conflict:'Dieses Konto kann nicht automatisch mit der Social-Anmeldung verknüpft werden.'
    };
    return map[error?.code] || error?.message || 'Bitte versuchen Sie es erneut.';
  }

  function logo() {
    return '<div class="login-logo"><img class="login-brand-logo" src="./assets/logo.svg" alt="A+ Esthetic"></div>';
  }

  function field(label, control) {
    return '<label class="field"><span>' + label + '</span>' + control + '</label>';
  }

  async function showSignup(message='') {
    const host = root();
    if (!host) return;
    host.innerHTML =
      '<div class="login-shell"><form class="login-card signup-card" data-signup>' +
      logo() +
      '<div class="eyebrow">NEUES KONTO</div><h1>Registrieren</h1>' +
      (message ? '<div class="notice error">' + esc(message) + '</div>' : '') +
      field('Anrede','<select name="salutation" required><option value="" selected disabled>Bitte wählen</option><option value="herr">Herr</option><option value="frau">Frau</option><option value="divers">Divers</option></select>') +
      '<div class="grid-2">' +
      field('Vorname','<input name="first_name" autocomplete="given-name" required>') +
      field('Nachname','<input name="last_name" autocomplete="family-name" required>') +
      '</div>' +
      field('E-Mail','<input name="email" type="email" autocomplete="email" required>') +
      field('Telefon','<input name="phone" type="tel" autocomplete="tel" placeholder="+49 …" required>') +
      field('Empfehlungscode <small>optional</small>','<input name="referral_code" autocomplete="off" placeholder="APLUS-…">') +
      field('Passwort','<input name="password" type="password" minlength="12" autocomplete="new-password" required>') +
      field('Passwort bestätigen','<input name="password2" type="password" minlength="12" autocomplete="new-password" required>') +
      '<button class="primary wide" type="submit">Konto erstellen</button>' +
      '<button class="text-btn wide" type="button" data-login-back>Schon ein Konto? Anmelden</button>' +
      '</form></div>';

    host.querySelector('[data-login-back]').addEventListener('click', () => location.reload());
    host.querySelector('[data-signup]').addEventListener('submit', async event => {
      event.preventDefault();
      const fd = new FormData(event.currentTarget);
      if (fd.get('password') !== fd.get('password2')) {
        return showSignup('Die Passwörter stimmen nicht überein.');
      }
      const submit = event.currentTarget.querySelector('button[type=submit]');
      submit.disabled = true;
      submit.textContent = 'Konto wird erstellt …';
      try {
        const result = await api('/signup/', {
          method:'POST',
          json:{
            salutation:fd.get('salutation'),
            first_name:fd.get('first_name'),
            last_name:fd.get('last_name'),
            email:fd.get('email'),
            phone:fd.get('phone'),
            referral_code:fd.get('referral_code') || '',
            password:fd.get('password')
          }
        });
        localStorage.setItem('aplus_token', result.token);
        const note = result.sms_error === 'sms_not_configured'
          ? 'Das Konto wurde erstellt. Die SMS-Funktion ist serverseitig noch nicht aktiviert.'
          : '';
        await showOnboarding(note);
      } catch (error) {
        await showSignup(errorText(error));
      }
    });
  }

  function verificationCard(kind, done, value) {
    if (done) {
      return '<article class="verify-card is-done"><strong>' +
        (kind === 'email' ? 'E-Mail bestätigt ✓' : 'Telefon bestätigt ✓') +
        '</strong><span>' + esc(value || '') + '</span></article>';
    }
    const formAttr = kind === 'email' ? 'data-email-confirm' : 'data-sms-confirm';
    const resendAttr = kind === 'email' ? 'data-resend-email' : 'data-resend-sms';
    return '<article class="verify-card"><strong>' +
      (kind === 'email' ? 'E-Mail bestätigen' : 'Telefon bestätigen') +
      '</strong><span>' + esc(value || '') + '</span>' +
      '<form ' + formAttr + '><input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="6-stelliger Code" required><button type="submit">Bestätigen</button></form>' +
      '<button class="text-btn" type="button" ' + resendAttr + '>Code erneut senden</button></article>';
  }

  async function showOnboarding(message='') {
    let data;
    try {
      data = await api('/onboarding/');
    } catch (_) {
      localStorage.removeItem('aplus_token');
      location.reload();
      return;
    }
    const profile = data.profile || {};
    const account = data.account || {};
    if (account.profile_complete) {
      location.reload();
      return;
    }

    const host = root();
    if (!host) return;
    host.innerHTML =
      '<div class="login-shell"><section class="login-card onboarding-card">' +
      logo() +
      '<div class="eyebrow">KONTO ABSCHLIESSEN</div><h1>Fast fertig</h1>' +
      '<p>Bitte vervollständigen und bestätigen Sie Ihr Profil. Danach werden alle Funktionen freigeschaltet.</p>' +
      (message ? '<div class="notice">' + esc(message) + '</div>' : '') +
      '<form data-profile-completion>' +
      field('Anrede','<select name="salutation" required><option value="herr"' + (profile.salutation === 'herr' ? ' selected' : '') + '>Herr</option><option value="frau"' + (profile.salutation === 'frau' ? ' selected' : '') + '>Frau</option><option value="divers"' + (profile.salutation === 'divers' ? ' selected' : '') + '>Divers</option></select>') +
      '<div class="grid-2">' +
      field('Vorname','<input name="first_name" value="' + esc(profile.first_name || '') + '" required>') +
      field('Nachname','<input name="last_name" value="' + esc(profile.last_name || '') + '" required>') +
      '</div>' +
      field('Telefon','<input name="phone" type="tel" value="' + esc(profile.phone || '') + '" required>') +
      (profile.referral_code ? '' : field('Empfehlungscode <small>optional</small>','<input name="referral_code" placeholder="APLUS-…">')) +
      '<button class="secondary wide" type="submit">Profil speichern</button></form>' +
      '<div class="verification-grid">' +
      verificationCard('email', Boolean(account.email_verified), profile.email) +
      verificationCard('sms', Boolean(account.phone_verified), profile.phone) +
      '</div>' +
      '<p class="onboarding-bonus">Mit einem gültigen Empfehlungscode erhalten Sie nach vollständiger Bestätigung automatisch 300 A+ Punkte.</p>' +
      '<button class="text-btn wide" type="button" data-onboarding-logout>Abmelden</button>' +
      '</section></div>';

    host.querySelector('[data-profile-completion]').addEventListener('submit', async event => {
      event.preventDefault();
      const fd = new FormData(event.currentTarget);
      try {
        const result = await api('/onboarding/', {
          method:'POST',
          json:{
            salutation:fd.get('salutation'),
            first_name:fd.get('first_name'),
            last_name:fd.get('last_name'),
            phone:fd.get('phone'),
            referral_code:fd.get('referral_code') || ''
          }
        });
        if (result.account?.profile_complete) return location.reload();
        await showOnboarding('Profil wurde gespeichert.');
      } catch (error) {
        await showOnboarding(errorText(error));
      }
    });

    host.querySelector('[data-email-confirm]')?.addEventListener('submit', async event => {
      event.preventDefault();
      const code = new FormData(event.currentTarget).get('code');
      try {
        const result = await api('/verification/email/confirm/', {method:'POST',json:{code}});
        if (result.account?.profile_complete) return location.reload();
        await showOnboarding('E-Mail wurde bestätigt.');
      } catch (error) {
        await showOnboarding(errorText(error));
      }
    });

    host.querySelector('[data-sms-confirm]')?.addEventListener('submit', async event => {
      event.preventDefault();
      const code = new FormData(event.currentTarget).get('code');
      try {
        const result = await api('/verification/sms/confirm/', {method:'POST',json:{code}});
        if (result.account?.profile_complete) return location.reload();
        await showOnboarding('Telefonnummer wurde bestätigt.');
      } catch (error) {
        await showOnboarding(errorText(error));
      }
    });

    host.querySelector('[data-resend-email]')?.addEventListener('click', async () => {
      try {
        await api('/verification/email/request/', {method:'POST'});
        await showOnboarding('Eine neue Bestätigungs-E-Mail wurde versendet.');
      } catch (error) {
        await showOnboarding(errorText(error));
      }
    });

    host.querySelector('[data-resend-sms]')?.addEventListener('click', async () => {
      try {
        await api('/verification/sms/request/', {method:'POST'});
        await showOnboarding('Eine neue SMS wurde versendet.');
      } catch (error) {
        await showOnboarding(errorText(error));
      }
    });

    host.querySelector('[data-onboarding-logout]')?.addEventListener('click', () => {
      localStorage.removeItem('aplus_token');
      location.reload();
    });
  }

  async function getAuthConfig() {
    if (cachedConfig) return cachedConfig;
    try {
      cachedConfig = await api('/auth/config/');
    } catch (_) {
      cachedConfig = {google:false, apple:false};
    }
    return cachedConfig;
  }

  function waitForGlobal(test, timeout=8000) {
    const started = Date.now();
    return new Promise((resolve, reject) => {
      const tick = () => {
        const value = test();
        if (value) return resolve(value);
        if (Date.now() - started >= timeout) return reject(new Error('provider_library_timeout'));
        setTimeout(tick, 80);
      };
      tick();
    });
  }

  async function completeSocialLogin(provider, credential, user={}) {
    const result = await api('/social-token/', {
      method:'POST',
      json:{provider, credential, user}
    });
    localStorage.setItem('aplus_token', result.token);
    if (result.account?.profile_complete) return location.reload();
    await showOnboarding();
  }

  async function renderGoogleButton(config, host) {
    if (!config.google || !config.google_client_id || !host) return;
    try {
      await waitForGlobal(() => window.google?.accounts?.id);
      window.google.accounts.id.initialize({
        client_id: config.google_client_id,
        callback: async response => {
          try {
            await completeSocialLogin('google', response.credential);
          } catch (error) {
            await showSignup(errorText(error));
          }
        },
        auto_select: false
      });
      const width = Math.max(240, Math.floor(host.getBoundingClientRect().width || 340));
      window.google.accounts.id.renderButton(host, {
        type:'standard',
        theme:'outline',
        size:'large',
        text:'signin_with',
        shape:'rectangular',
        logo_alignment:'left',
        width,
        locale:'de'
      });
    } catch (_) {
      host.innerHTML = '';
    }
  }

  async function renderAppleButton(config, host) {
    if (!config.apple || !config.apple_client_id || !host) return;
    try {
      await waitForGlobal(() => window.AppleID?.auth);
      const state = (window.crypto?.randomUUID?.() || (String(Date.now()) + Math.random()))
        .replace(/[^a-zA-Z0-9._-]/g, '');
      sessionStorage.setItem('aplus_apple_state', state);
      window.AppleID.auth.init({
        clientId: config.apple_client_id,
        scope: 'name email',
        redirectURI: 'https://esthetic.smarbiz.sbs/accounts/apple/login/callback/',
        state,
        usePopup: true
      });
      if (!window.__aplusAppleListenerBound) {
        window.__aplusAppleListenerBound = true;
        document.addEventListener('AppleIDSignInOnSuccess', async event => {
          const payload = event.detail?.data || event.detail || {};
          const authorization = payload.authorization || {};
          const expectedState = sessionStorage.getItem('aplus_apple_state') || '';
          if (expectedState && authorization.state && authorization.state !== expectedState) return;
          try {
            await completeSocialLogin('apple', authorization.id_token, payload.user || {});
          } catch (error) {
            await showSignup(errorText(error));
          }
        });
      }
    } catch (_) {
      host.innerHTML = '';
    }
  }

  async function enhanceLogin() {
    const form = document.querySelector('[data-login]');
    if (!form || form.dataset.accountEnhanced === '1') return;
    form.dataset.accountEnhanced = '1';
    form.querySelector('.login-logo span')?.remove();

    const submit = form.querySelector('button[type=submit]');
    if (submit) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'secondary wide login-signup';
      button.textContent = 'Konto erstellen';
      button.addEventListener('click', () => showSignup());
      submit.insertAdjacentElement('afterend', button);
    }

    const config = await getAuthConfig();
    if ((config.google || config.apple) && !form.querySelector('[data-social-login]')) {
      const wrapper = document.createElement('div');
      wrapper.dataset.socialLogin = '1';
      wrapper.innerHTML =
        '<div class="login-divider"><span>oder</span></div>' +
        '<div class="official-social-grid">' +
          (config.google ? '<div class="official-google" data-google-signin></div>' : '') +
          (config.apple ? '<div class="official-apple" id="appleid-signin" data-apple-signin data-color="black" data-border="true" data-type="sign-in" data-mode="center-align"></div>' : '') +
        '</div>';
      form.appendChild(wrapper);
      await Promise.allSettled([
        renderGoogleButton(config, wrapper.querySelector('[data-google-signin]')),
        renderAppleButton(config, wrapper.querySelector('[data-apple-signin]'))
      ]);
    }
  }

  async function finishSocial() {
    const params = new URLSearchParams(location.search);
    if (params.get('social') !== '1') return;
    try {
      const result = await api('/social-session/');
      localStorage.setItem('aplus_token', result.token);
      history.replaceState(null, '', location.pathname);
      location.reload();
    } catch (_) {
      history.replaceState(null, '', location.pathname);
      localStorage.removeItem('aplus_token');
    }
  }

  function hideSplash() {
    const splash = document.getElementById('brand-splash');
    if (!splash) return;
    window.setTimeout(() => splash.classList.add('is-hidden'), 850);
  }

  window.APlusOnboarding = {
    start: showOnboarding,
    signup: showSignup,
    enhanceLogin
  };

  new MutationObserver(() => enhanceLogin()).observe(document.documentElement, {childList:true,subtree:true});
  document.addEventListener('DOMContentLoaded', () => {
    enhanceLogin();
    finishSocial();
    hideSplash();
  }, {once:true});
  window.addEventListener('pageshow', hideSplash);
  setTimeout(() => {
    enhanceLogin();
    finishSocial();
    hideSplash();
  }, 0);
})();
