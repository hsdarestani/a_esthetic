/* Focused iOS APNs / admin-handoff regression checks. No production API calls. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../www/native-push.js'), 'utf8');

function harness({ platform = 'ios', cached = '', permission = 'granted', delayedPost = false } = {}) {
  const values = new Map([['aplus_token', 'signed-admin-test-token']]);
  if (cached) values.set('aplus_push_token', cached);
  const handlers = {};
  const requests = [];
  let releasePost;
  const postGate = new Promise(resolve => { releasePost = resolve; });
  const storage = {
    getItem: k => values.get(k) || null,
    setItem: (k, v) => values.set(k, String(v)),
    removeItem: k => values.delete(k),
  };
  const native = {
    addListener(name, cb) { handlers[name] = cb; },
    async checkPermissions() { return { receive: permission }; },
    async requestPermissions() { return { receive: permission }; },
    async register() {
      queueMicrotask(() => handlers.registration?.({ value: 'apns-device-token' }));
    },
  };
  const fakeWindow = {
    Capacitor: { getPlatform: () => platform, Plugins: { PushNotifications: native } },
    addEventListener() {},
  };
  const sandbox = {
    window: fakeWindow,
    document: { documentElement: {} },
    localStorage: storage,
    MutationObserver: class { observe() {} },
    fetch: async (url, options) => {
      requests.push({ url, method: options.method, body: options.body });
      if (delayedPost && options.method === 'POST') await postGate;
      return { ok: true, status: 200 };
    },
    setTimeout, clearTimeout, queueMicrotask, console,
  };
  vm.runInNewContext(source, sandbox, { filename: 'native-push.js' });
  return { app: fakeWindow, storage, requests, releasePost };
}

async function main() {
  // Registration must not report success until our server has stored the APNs token.
  const first = harness({ delayedPost: true });
  let done = false;
  const registration = first.app.APlusNativePush.register().then(value => { done = true; return value; });
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(done, false, 'admin navigated away before device was saved');
  first.releasePost();
  assert.equal(await registration, true);
  assert.equal(first.storage.getItem('aplus_push_token'), 'apns-device-token');
  assert.equal(first.requests.filter(r => r.method === 'POST').length, 1);

  // A previously registered token can be reattached to an existing admin
  // session without forcing the user to wait for a new APNs callback.
  const cached = harness({ cached: 'previous-apns-token' });
  assert.equal(await cached.app.APlusNativePush.register(), true);
  assert.equal(cached.requests[0].method, 'POST');
  assert.match(cached.requests[0].body, /previous-apns-token/);

  // Denied notifications are not reported as a successful registration.
  const denied = harness({ permission: 'denied' });
  assert.equal(await denied.app.APlusNativePush.register(), false);

  console.log('PASS: iOS APNs registration waits for server persistence; cached/denied states verified');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
