(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  let pushListenersBound = false;
  let adminKnown = null;

  const token = () => localStorage.getItem('aplus_token') || '';
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const dateTime = value => {
    if (!value) return '–';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '–' : new Intl.DateTimeFormat('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
    }).format(date);
  };

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) {
      const error = new Error(body.error || `http_${response.status}`);
      error.code = body.error;
      error.status = response.status;
      throw error;
    }
    return body;
  }

  function content() {
    return document.querySelector('.shell .content');
  }

  function backButton() {
    return '<div class="actions" style="margin-bottom:12px"><button class="btn ghost" type="button" data-ops-back>← Mehr</button></div>';
  }

  function bindBack() {
    document.querySelector('[data-ops-back]')?.addEventListener('click', () => {
      document.querySelector('.nav [data-route="more"]')?.click();
    });
  }

  async function refreshBell() {
    if (!token()) return;
    const bell = document.querySelector('[data-ops-notifications]');
    if (!bell) return;
    try {
      const data = await api('/notifications/');
      const count = Number(data.unread_count) || 0;
      bell.innerHTML = count ? `♢<span class="ops-count">${count > 99 ? '99+' : count}</span>` : '♢';
      bell.setAttribute('aria-label', count ? `${count} ungelesene Benachrichtigungen` : 'Benachrichtigungen');
    } catch (_) {}
  }

  async function showNotifications() {
    const target = content();
    if (!target) return;
    target.innerHTML = `${backButton()}<div class="pagehead"><span>Aktuell</span><h1>Benachrichtigungen</h1><p>Push-Mitteilungen und Hinweise aus Ihrem A+ Konto.</p></div><div class="loading">Wird geladen…</div>`;
    bindBack();
    try {
      const data = await api('/notifications/');
      target.innerHTML = `${backButton()}
        <div class="pagehead"><span>Aktuell</span><h1>Benachrichtigungen</h1><p>Push-Mitteilungen und Hinweise aus Ihrem A+ Konto.</p></div>
        <section class="card">
          <div class="row"><div class="row-main"><b>${data.unread_count} ungelesen</b><small>Push: Android ${data.push.android ? 'aktiv' : 'nicht konfiguriert'} · iOS ${data.push.ios ? 'aktiv' : 'nicht konfiguriert'}</small></div>${data.unread_count ? '<button class="btn ghost" type="button" data-ops-read-all>Alle gelesen</button>' : ''}</div>
        </section>
        <section class="card ops-notification-list">
          ${data.notifications.length ? data.notifications.map(item => `<button type="button" class="row ops-notification-row ${item.read ? '' : 'ops-unread'}" data-ops-read="${item.id}" data-deeplink="${esc(item.deeplink || '')}"><div class="row-main"><b>${esc(item.title)}</b><small>${esc(item.body || '')}</small><small>${dateTime(item.created_at)}</small></div>${item.read ? '' : '<span class="badge">Neu</span>'}</button>`).join('') : '<p class="empty">Noch keine Benachrichtigungen.</p>'}
        </section>`;
      bindBack();
      target.querySelector('[data-ops-read-all]')?.addEventListener('click', async () => {
        await api('/notifications/read-all/', { method: 'POST', body: '{}' });
        await showNotifications();
        refreshBell();
      });
      target.querySelectorAll('[data-ops-read]').forEach(button => button.addEventListener('click', async () => {
        try { await api(`/notifications/${button.dataset.opsRead}/read/`, { method: 'POST', body: '{}' }); } catch (_) {}
        const route = button.dataset.deeplink;
        if (route && ['home','club','booking','wallet','more','messages','reminders','profile'].includes(route)) {
          document.querySelector(`.nav [data-route="${route}"]`)?.click();
        } else {
          await showNotifications();
        }
        refreshBell();
      }));
    } catch (error) {
      target.innerHTML += `<div class="errorbox">${esc(error.message)}</div>`;
    }
  }

  function rewardStatusLabel(status) {
    return ({pending:'Offen', processing:'In Bearbeitung', fulfilled:'Erfüllt', cancelled:'Storniert'})[status] || status;
  }

  async function enhanceWalletRedemptions() {
    const heading = [...document.querySelectorAll('.pagehead h1')].find(node => node.textContent.trim() === 'Wallet & Rewards');
    const target = heading?.closest('.content');
    if (!target || target.querySelector('[data-ops-redemptions]')) return;
    try {
      const data = await api('/reward-redemptions/');
      if (!data.redemptions.length) return;
      const section = document.createElement('section');
      section.className = 'card';
      section.dataset.opsRedemptions = '1';
      section.innerHTML = `<h2>Reward-Status</h2>${data.redemptions.map(item => `<div class="row"><div class="row-main"><b>${esc(item.reward)}</b><small>${esc(item.fulfillment_code)} · ${dateTime(item.requested_at)}</small></div><span class="badge">${esc(rewardStatusLabel(item.status))}</span></div>`).join('')}`;
      const cards = target.querySelectorAll('.card');
      if (cards.length) cards[0].after(section); else target.appendChild(section);
    } catch (_) {}
  }

  function removeShopEntry() {
    document.querySelectorAll('[data-p2-route="shop"]').forEach(button => button.remove());
  }

  async function ensureAdminButton() {
    const heading = [...document.querySelectorAll('.pagehead h1')].find(node => node.textContent.trim() === 'Mehr');
    const target = heading?.closest('.content');
    const grid = target?.querySelector('.more-grid');
    if (!grid || grid.querySelector('[data-ops-admin]')) return;
    if (adminKnown === false) return;
    try {
      const data = await api('/admin/');
      adminKnown = true;
      const notifications = document.createElement('button');
      notifications.type = 'button';
      notifications.className = 'more-item';
      notifications.dataset.opsCenter = '1';
      notifications.textContent = '♢ Benachrichtigungen';
      notifications.addEventListener('click', showNotifications);
      grid.appendChild(notifications);

      const admin = document.createElement('button');
      admin.type = 'button';
      admin.className = 'more-item';
      admin.dataset.opsAdmin = '1';
      admin.textContent = '⌘ Administration';
      admin.addEventListener('click', showAdmin);
      grid.appendChild(admin);
      void data;
    } catch (error) {
      if (error.status === 403) adminKnown = false;
      if (!grid.querySelector('[data-ops-center]')) {
        const notifications = document.createElement('button');
        notifications.type = 'button';
        notifications.className = 'more-item';
        notifications.dataset.opsCenter = '1';
        notifications.textContent = '♢ Benachrichtigungen';
        notifications.addEventListener('click', showNotifications);
        grid.appendChild(notifications);
      }
    }
  }

  function moduleMarkup(item) {
    return `<div class="row"><div class="row-main"><b>${esc(item.name)}</b><small>${esc(item.description || item.key)}</small></div><button class="btn ghost" type="button" data-admin-module="${esc(item.key)}" data-enabled="${item.enabled ? '1' : '0'}" ${item.locked ? 'disabled' : ''}>${item.locked ? 'Deaktiviert' : (item.enabled ? 'Aktiv' : 'Inaktiv')}</button></div>`;
  }

  async function showAdmin() {
    const target = content();
    if (!target) return;
    target.innerHTML = `${backButton()}<div class="pagehead"><span>A+ Esthetic</span><h1>Administration</h1><p>Kunden, Rewards, Einstellungen und Push zentral verwalten.</p></div><div class="loading">Wird geladen…</div>`;
    bindBack();
    try {
      const data = await api('/admin/');
      target.innerHTML = `${backButton()}
        <div class="pagehead"><span>A+ Esthetic</span><h1>Administration</h1><p>Kunden, Rewards, Einstellungen und Push zentral verwalten.</p></div>
        <div class="stats"><div class="stat"><b>${data.stats.customers}</b><small>Kunden</small></div><div class="stat"><b>${data.stats.active_packages}</b><small>Pakete</small></div><div class="stat"><b>${data.stats.pending_rewards}</b><small>Rewards offen</small></div><div class="stat"><b>${data.stats.push_devices}</b><small>Push-Geräte</small></div></div>
        <section class="card"><h2>Admin-Bereiche</h2><div class="more-grid"><a href="${esc(data.links.book_admin)}" target="_blank" rel="noopener">Kalender & Book Admin</a><a href="${esc(data.links.app_admin)}" target="_blank" rel="noopener">Vollständiger App Admin</a><button type="button" data-admin-customers>Kunden durchsuchen</button></div></section>
        <section class="card"><h2>Push Notification senden</h2><p class="muted">Android: ${data.push.android ? 'konfiguriert' : 'nicht konfiguriert'} · iOS: ${data.push.ios ? 'konfiguriert' : 'nicht konfiguriert'}</p><form class="form" data-admin-notification><label>Kunden-ID (leer bei alle)<input name="user_id" inputmode="numeric"></label><label class="check"><input type="checkbox" name="all_customers"><span>An alle Kunden senden</span></label><label>Titel<input name="title" maxlength="180" required></label><label>Text<textarea name="body" maxlength="5000" rows="3" required></textarea></label><label>Ziel<select name="deeplink"><option value="">Notification Center</option><option value="home">Home</option><option value="booking">Termine</option><option value="wallet">Wallet</option><option value="club">Club</option><option value="profile">Profil</option></select></label><button class="btn primary" type="submit">Senden</button></form></section>
        <section class="card"><h2>Reward Fulfillment</h2>${data.pending_rewards.length ? data.pending_rewards.map(item => `<div class="row"><div class="row-main"><b>${esc(item.reward)} · ${esc(item.fulfillment_code)}</b><small>${esc(item.customer.name)} · ${esc(item.customer.email)}</small></div><button class="btn ghost" type="button" data-admin-reward="${item.id}" data-action="processing">Bearbeiten</button><button class="btn primary" type="button" data-admin-reward="${item.id}" data-action="fulfill">Erfüllt</button><button class="btn ghost" type="button" data-admin-reward="${item.id}" data-action="cancel">Storno</button></div>`).join('') : '<p class="empty">Keine offenen Rewards.</p>'}</section>
        <section class="card"><h2>Module & Einstellungen</h2>${data.modules.map(moduleMarkup).join('')}</section>`;
      bindBack();
      bindAdmin(target);
    } catch (error) {
      target.innerHTML += `<div class="errorbox">${esc(error.message)}</div>`;
    }
  }

  function bindAdmin(target) {
    target.querySelector('[data-admin-customers]')?.addEventListener('click', showCustomers);
    target.querySelectorAll('[data-admin-module]').forEach(button => button.addEventListener('click', async () => {
      const enabled = button.dataset.enabled !== '1';
      try {
        await api(`/admin/modules/${button.dataset.adminModule}/`, { method: 'POST', body: JSON.stringify({ enabled, customer_visible: enabled }) });
        await showAdmin();
      } catch (error) { alert(error.message); }
    }));
    target.querySelectorAll('[data-admin-reward]').forEach(button => button.addEventListener('click', async () => {
      const action = button.dataset.action;
      if ((action === 'cancel' || action === 'fulfill') && !confirm(action === 'cancel' ? 'Reward stornieren und Coins zurückbuchen?' : 'Reward als erfüllt markieren?')) return;
      try {
        await api(`/admin/rewards/${button.dataset.adminReward}/`, { method: 'POST', body: JSON.stringify({ action }) });
        await showAdmin();
      } catch (error) { alert(error.message); }
    }));
    target.querySelector('[data-admin-notification]')?.addEventListener('submit', async event => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const all = form.get('all_customers') === 'on';
      const payload = {
        all_customers: all,
        user_id: all ? null : Number(form.get('user_id')),
        title: form.get('title'),
        body: form.get('body'),
        deeplink: form.get('deeplink'),
        category: 'general',
      };
      const button = event.currentTarget.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        const result = await api('/admin/notifications/', { method: 'POST', body: JSON.stringify(payload) });
        alert(`Notification für ${result.recipients} Empfänger gespeichert; ${result.push_deliveries} Push-Zustellungen bestätigt.`);
        event.currentTarget.reset();
      } catch (error) { alert(error.message); }
      finally { button.disabled = false; }
    });
  }

  async function showCustomers() {
    const target = content();
    if (!target) return;
    target.innerHTML = `${backButton()}<div class="pagehead"><span>Administration</span><h1>Kunden</h1><p>Mitglieder und Kontodaten durchsuchen.</p></div><section class="card"><form class="form" data-customer-search><label>Suche<input name="q" placeholder="Name, E-Mail oder Telefon"></label><button class="btn primary">Suchen</button></form><div data-customer-results class="loading">Wird geladen…</div></section>`;
    bindBack();
    const load = async query => {
      const data = await api(`/admin/customers/?q=${encodeURIComponent(query || '')}`);
      const results = target.querySelector('[data-customer-results]');
      results.className = '';
      results.innerHTML = data.customers.length ? data.customers.map(customer => `<div class="row"><div class="row-main"><b>${esc(customer.name)}</b><small>#${customer.id} · ${esc(customer.email)} · ${esc(customer.phone || 'kein Telefon')}</small><small>${esc(customer.member_number)} · ${esc(customer.tier)} · ${customer.coins} Coins · ${customer.active_packages} Pakete</small></div></div>`).join('') : '<p class="empty">Keine Kunden gefunden.</p>';
    };
    target.querySelector('[data-customer-search]')?.addEventListener('submit', async event => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      await load(form.get('q'));
    });
    await load('');
  }

  function platformName() {
    const platform = window.Capacitor?.getPlatform?.() || '';
    return platform === 'ios' ? 'ios' : platform === 'android' ? 'android' : '';
  }

  async function registerPushDevice(value) {
    const platform = platformName();
    if (!platform || !token() || !value) return;
    try {
      await api('/notifications/devices/', {
        method: 'POST',
        body: JSON.stringify({ token: value, platform, app_version: '1.0' }),
      });
      refreshBell();
    } catch (_) {}
  }

  async function syncNativePush() {
    if (!token()) return;
    const plugin = window.Capacitor?.Plugins?.PushNotifications;
    if (!plugin || !platformName()) return;
    try {
      if (!pushListenersBound) {
        pushListenersBound = true;
        plugin.addListener('registration', registration => registerPushDevice(registration.value));
        plugin.addListener('registrationError', () => {});
        plugin.addListener('pushNotificationReceived', () => refreshBell());
        plugin.addListener('pushNotificationActionPerformed', event => {
          const route = event?.notification?.data?.deeplink;
          if (route && ['home','club','booking','wallet','more','messages','reminders','profile'].includes(route)) {
            document.querySelector(`.nav [data-route="${route}"]`)?.click();
          } else {
            showNotifications();
          }
        });
      }
      const permission = await plugin.checkPermissions();
      let receive = permission.receive;
      if (receive === 'prompt') {
        const requested = await plugin.requestPermissions();
        receive = requested.receive;
      }
      if (receive === 'granted') await plugin.register();
    } catch (_) {}
  }

  function enhance() {
    removeShopEntry();
    enhanceWalletRedemptions();
    ensureAdminButton();

    const top = document.querySelector('.topbar-row');
    if (top && !top.querySelector('[data-ops-notifications]')) {
      const button = document.createElement('button');
      button.className = 'iconbtn ops-bell';
      button.type = 'button';
      button.dataset.opsNotifications = '1';
      button.setAttribute('aria-label', 'Benachrichtigungen');
      button.textContent = '♢';
      button.addEventListener('click', showNotifications);
      top.appendChild(button);
      refreshBell();
    }
    syncNativePush();
  }

  const observer = new MutationObserver(enhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', enhance);
  window.addEventListener('focus', () => { enhance(); refreshBell(); });
  window.addEventListener('storage', event => { if (event.key === 'aplus_token') { adminKnown = null; syncNativePush(); } });
})();
