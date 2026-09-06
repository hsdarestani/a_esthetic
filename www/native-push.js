(() => {
  'use strict';

  const API = 'https://esthetic.smarbiz.sbs/api/mobile';
  const TOKEN_KEY = 'aplus_token';
  const PUSH_TOKEN_KEY = 'aplus_push_token';
  let listenersBound = false;
  let registering = false;
  let lastAuthToken = localStorage.getItem(TOKEN_KEY) || '';

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
    if (!response.ok && response.status !== 401) {
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
    const deeplink = event?.notification?.data?.deeplink || event?.notification?.data?.route || '';
    const target = routeForDeeplink(deeplink);
    const button = document.querySelector(`[data-route="${target}"]`);
    if (button) button.click();
  }

  async function bindAndRegister() {
    const authToken = localStorage.getItem(TOKEN_KEY) || '';
    const native = plugin();
    if (!authToken || !native || !platform() || registering) return;
    lastAuthToken = authToken;
    registering = true;
    try {
      if (!listenersBound) {
        listenersBound = true;
        native.addListener('registration', event => {
          saveDevice(event?.value || '').catch(() => {});
        });
        native.addListener('registrationError', () => {});
        native.addListener('pushNotificationActionPerformed', openNotification);
      }
      const permission = await native.checkPermissions();
      let receive = permission?.receive;
      if (receive === 'prompt') {
        receive = (await native.requestPermissions())?.receive;
      }
      if (receive === 'granted') await native.register();
    } catch (_) {
      // Push must never block the patient app UI.
    } finally {
      registering = false;
    }
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
})();
