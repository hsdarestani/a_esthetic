/* Regression tests for the iOS blank-screen and SMS onboarding recovery paths.
 * Run: node scripts/test-ios-onboarding-recovery.js
 * No live SMS, production credentials, or network access required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness(file, fetchMock, initialToken = 'test-token') {
  const handlers = {};
  const timers = [];
  const storage = new Map(initialToken ? [['aplus_token', initialToken]] : []);
  const localStorage = {
    getItem: key => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, String(value)),
    removeItem: key => storage.delete(key),
  };
  const listener = (name, callback) => { handlers[name] = callback; };
  const noopButton = { addEventListener() {} };
  const form = { addEventListener(name, callback) { handlers['sms:' + name] = callback; } };
  const profileForm = { addEventListener() {} };
  const root = {
    innerHTML: '',
    get firstElementChild() { return this.innerHTML ? {} : null; },
    querySelector(selector) {
      if (selector === '.onboarding-card') return this.innerHTML.includes('onboarding-card') ? {} : null;
      if (selector === '[data-sms-confirm]') return this.innerHTML.includes('data-sms-confirm') ? form : null;
      if (selector === '[data-profile-completion]') return this.innerHTML.includes('data-profile-completion') ? profileForm : null;
      if (selector === '[data-reconnect]') return noopButton;
      if (selector === '[data-onboarding-retry]') return noopButton;
      return null;
    },
    querySelectorAll() { return []; },
  };
  const document = {
    visibilityState: 'visible',
    documentElement: {},
    body: {classList: {contains: () => false, remove() {}}},
    getElementById(id) { return id === 'app' ? root : null; },
    addEventListener() {},
    querySelector() { return null; },
  };
  let reloadCount = 0;
  const location = {search: '', pathname: '/', reload() { reloadCount++; }};
  const window = {
    AEstheticIconSet: {},
    addEventListener() {},
    Capacitor: null,
  };
  const sandbox = {
    window, document, location, localStorage, Headers, AbortController,
    URLSearchParams, navigator: {userAgent: 'iPhone'},
    performance: {now: () => 0},
    MutationObserver: class {observe() {}},
    FormData: class {get(name) { return name === 'code' ? '123456' : ''; }},
    fetch: fetchMock, setTimeout(fn, ms) {timers.push({fn, ms}); return timers.length;},
    clearTimeout() {}, requestAnimationFrame() {}, console,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), sandbox, {filename:file});
  return {window, root, localStorage, handlers, timers, get reloadCount() {return reloadCount;}};
}

function ok(data) {
  return {ok:true, status:200, json:async()=>data};
}
async function settle() {
  for(let i=0;i<5;i++) await Promise.resolve();
}

async function run() {
  // Previously #app was still empty while /me waited indefinitely.
  const waiting = harness('www/core-app.js', (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => {
      const error = new Error('aborted'); error.name = 'AbortError'; reject(error);
    });
  }));
  assert.match(waiting.root.innerHTML, /Willkommen zurück/);
  const authTimer = waiting.timers.find(item => item.ms === 12000);
  assert.ok(authTimer, 'Missing bounded auth request');
  authTimer.fn();
  await settle();
  assert.match(waiting.root.innerHTML, /Erneut verbinden/);
  assert.equal(waiting.localStorage.getItem('aplus_token'), 'test-token');

  // A successful confirmation refreshes the in-memory session, not the WebView.
  const requests = [];
  const sms = harness('www/account-onboarding.js', async(url, options) => {
    requests.push(url);
    if(url.endsWith('/onboarding/')) return ok({
      account:{profile_complete:false, email_verified:true, phone_verified:false, sms_pending:true},
      profile:{email:'test@example.com',phone:'+491700000000',first_name:'Test',last_name:'Person',salutation:'frau'},
    });
    if(url.endsWith('/verification/sms/confirm/')) return ok({account:{profile_complete:true}});
    throw new Error('Unexpected route ' + url);
  });
  let refreshed = 0;
  sms.window.APlusRefreshAuth = async() => {refreshed++;};
  await sms.window.APlusOnboarding.start();
  assert.ok(sms.handlers['sms:submit'], 'SMS confirmation handler was not registered');
  await sms.handlers['sms:submit']({preventDefault() {}, currentTarget:{}});
  assert.equal(refreshed, 1);
  assert.equal(sms.reloadCount, 0);
  assert.equal(sms.localStorage.getItem('aplus_token'), 'test-token');
  assert.ok(requests.some(p=>p.endsWith('/verification/sms/confirm/')));

  // Offline onboarding used to destroy the token and force a reload loop.
  const offline = harness('www/account-onboarding.js', async() => {throw new TypeError('Network unavailable');});
  await offline.window.APlusOnboarding.start();
  assert.match(offline.root.innerHTML, /Verbindung unterbrochen/);
  assert.match(offline.root.innerHTML, /Erneut versuchen/);
  assert.equal(offline.localStorage.getItem('aplus_token'), 'test-token');
  assert.equal(offline.reloadCount, 0);

  console.log('PASS: iOS startup timeout, SMS session refresh, and offline onboarding recovery');
}
run().catch(error => {console.error(error); process.exitCode = 1;});
