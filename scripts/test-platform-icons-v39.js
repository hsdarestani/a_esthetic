const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const read = path => fs.readFileSync(path, 'utf8');
const icons = read('www/esthetic-icon-system-v39.js');
const globals = { window: {} };
vm.runInNewContext(icons, globals);
const found = globals.window.AEstheticIconSet;
for (const key of ['dashboard','appointments','records','points','friends','settings','phone','instagram','directions','benefits','membership','review']) {
  assert.ok(found[key].includes('<svg'), 'missing '+key);
  assert.ok(found[key].includes('viewBox="0 0 24 24"'), 'invalid icon '+key);
}
assert.notEqual(found.points, found.records);
const app = read('www/core-app.js');
assert.ok(app.includes('const NAV_ICONS = window.AEstheticIconSet'), 'core must use shared icons');
assert.ok(app.includes('selectedSalutation='), 'hero must use explicit Anrede');
const dash = read('www/customer-dashboard-v3.js');
assert.ok(dash.includes('...window.AEstheticIconSet'), 'dashboard must use shared icons');
const auth = read('www/account-onboarding.js');
assert.ok(auth.includes("const canApple = platform === 'ios'"), 'native Apple button must be iOS only');
assert.ok(auth.includes("const showApple = !/Android/i.test(navigator.userAgent)"), 'Android browser must hide Apple button');
const html = read('www/index.html');
assert.ok(html.indexOf('esthetic-icon-system-v39.js') < html.indexOf('core-app.js'), 'icons loaded too late');
assert.ok(html.includes('iconography-v39.css'), 'missing icons stylesheet');
console.log('A+ Premium icons, auth platform rules and gender fallback OK');
