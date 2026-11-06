(() => {
  'use strict';

  const APP_ORIGIN = 'https://app.a-esthetic.de';
  const API = `${APP_ORIGIN}/api/mobile`;
  const TOKEN_KEY = 'aplus_token';
  const PUSH_TOKEN_KEY = 'aplus_push_token';
  let listenersBound = false;
  let registering = false;
  let lastRegistrationAttempt = 0;
  let lastAuthToken = localStorage.getItem(TOKEN_KEY) || '';
  let iosRegistrationResolver = null;

  function finishIosRegistration(ok) {
    const resolve = iosRegistrationResolver;
    iosRegistrationResolver = null;
    if (resolve) resolve(Boolean(ok));
  }

  function platform() {
    const value = window.Capacitor?.getPlatform?.() || '';
    return value === 'ios' || value === 'android' ? value : '';
  }

  function plugin() {
    return window.Capacitor?.Plugins?.PushNotifications || null;
  }

  async function deviceRequest(method, pushToken, authToken = localStorage.getItem(TOKEN_KEY) || '') {
    if (!authToken || !pushToken) return;
    const response = await fetch(`${API}/notifications/devices/`, {
      method,
      cache: 'no-store',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        token: pushToken,
        platform: platform() || undefined,
        app_version: '1.0',
      }),
    });
    if (!response.ok) {
      throw new Error(`push_device_http_${response.status}`);
    }
  }

  async function saveDevice(pushToken) {
    if (!pushToken || !platform()) return;
    localStorage.setItem(PUSH_TOKEN_KEY, pushToken);
    await deviceRequest('POST', pushToken);
  }

  function routeForDeeplink(value) {
    const key = String(value || '').trim().toLowerCase();
    return ({
      home: 'appointments',
      booking: 'appointments',
      appointments: 'appointments',
      wallet: 'points',
      points: 'points',
      admin_booking: '__admin_booking__',
      doctor_calendar: '__admin_booking__',
      booking_admin: '__admin_booking__',
      review: 'reviews',
      reviews: 'reviews',
      club: 'friends',
      referral: 'friends',
      friends: 'friends',
      wallet: 'wallet',
      profile: 'records',
      patient: 'records',
      records: 'records',
    })[key] || 'appointments';
  }

  function openNotification(event) {
    const incoming = event?.notification?.data || {};
    // iOS APNs may wrap custom fields inside a nested data object.
    const data = incoming?.data && typeof incoming.data === 'object'
      ? { ...incoming.data, ...incoming } : incoming;
    const deeplink = data.deeplink || data.route || '';
    if (deeplink === 'admin_patient') {
      const patientId = String(data.patient_customer_id || '').trim();
      if (/^[1-9][0-9]{0,11}$/.test(patientId)) {
        window.APlusAdminMode?.open?.({ patientId });
      }
      return;
    }
    const target = routeForDeeplink(deeplink);
    if (target === '__admin_booking__') {
      if (window.APlusAdminMode?.open) window.APlusAdminMode.open();
      return;
    }
    const button = document.querySelector(`[data-route="${target}"]`);
    if (button) button.click();
  }

  async function bindAndRegister() {
    const authToken = localStorage.getItem(TOKEN_KEY) || '';
    const native = plugin();
    if (!authToken || !native || !platform() || registering) return;
    // MutationObserver, focus and SSO may all trigger within the same second.
    if (Date.now() - lastRegistrationAttempt < 30000) return;
    lastRegistrationAttempt = Date.now();
    lastAuthToken = authToken;
    registering = true;
    try {
      if (!listenersBound) {
        listenersBound = true;
        native.addListener('registration', event => {
          saveDevice(event?.value || '')
            .then(() => finishIosRegistration(true))
            .catch(() => finishIosRegistration(false));
        });
        native.addListener('registrationError', () => { lastRegistrationAttempt = 0; finishIosRegistration(false); });
        native.addListener('pushNotificationActionPerformed', openNotification);
      }
      const permission = await native.checkPermissions();
      let receive = permission?.receive;
      if (receive === 'prompt') {
        receive = (await native.requestPermissions())?.receive;
      }
      if (receive === 'granted') await native.register();
      else finishIosRegistration(false);
    } catch (_) {
      lastRegistrationAttempt = 0;
      finishIosRegistration(false);
      // Push must never block the patient app UI.
    } finally {
      registering = false;
    }
  }

  async function registerForAdmin() {
    // Android already works; only iOS must wait for APNs and server delivery
    // before cross-origin navigation destroys the Capacitor callback context.
    if (platform() !== 'ios') return reconcileAuth();
    const authToken = localStorage.getItem(TOKEN_KEY) || '';
    if (!authToken || !plugin()) return false;

    const cached = localStorage.getItem(PUSH_TOKEN_KEY) || '';
    if (cached) {
      try {
        await deviceRequest('POST', cached, authToken);
        bindAndRegister().catch(() => {});
        return true;
      } catch (_) {
        // A failed replay is not proof of an APNs registration; try a fresh one.
      }
    }

    return new Promise(resolve => {
      let completed = false;
      let timer;
      const settle = ok => {
        if (completed) return;
        completed = true;
        clearTimeout(timer);
        if (iosRegistrationResolver === settle) iosRegistrationResolver = null;
        resolve(Boolean(ok));
      };
      iosRegistrationResolver = settle;
      timer = setTimeout(() => settle(false), 6500);
      bindAndRegister().catch(() => settle(false));
    });
  }

  async function reconcileAuth() {
    const current = localStorage.getItem(TOKEN_KEY) || '';
    if (!current && lastAuthToken) {
      const pushToken = localStorage.getItem(PUSH_TOKEN_KEY) || '';
      if (pushToken) {
        try { await deviceRequest('DELETE', pushToken, lastAuthToken); } catch (_) {}
      }
      localStorage.removeItem(PUSH_TOKEN_KEY);
      lastAuthToken = '';
      return;
    }
    if (current) {
      lastAuthToken = current;
      await bindAndRegister();
    }
  }

  const observer = new MutationObserver(() => { reconcileAuth().catch(() => {}); });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', () => { reconcileAuth().catch(() => {}); });
  window.addEventListener('focus', () => { reconcileAuth().catch(() => {}); });
  window.addEventListener('storage', event => {
    if (event.key === TOKEN_KEY) reconcileAuth().catch(() => {});
  });
  setTimeout(() => { reconcileAuth().catch(() => {}); }, 0);

  window.APlusNativePush = {
    register: () => registerForAdmin(),
  };
})();
