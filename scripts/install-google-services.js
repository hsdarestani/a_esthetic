const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const source = path.join(root, 'config', 'firebase', 'google-services.json');
const target = path.join(root, 'android', 'app', 'google-services.json');
const expectedPackage = 'de.aplusesthetic.app';

if (!fs.existsSync(source)) {
  throw new Error(`Missing Firebase Android config: ${source}`);
}

const config = JSON.parse(fs.readFileSync(source, 'utf8'));
const clients = Array.isArray(config.client) ? config.client : [];
const matches = clients.some(
  (client) => client?.client_info?.android_client_info?.package_name === expectedPackage,
);

if (!matches) {
  throw new Error(`Firebase config does not contain Android package ${expectedPackage}`);
}

const targetDir = path.dirname(target);
if (!fs.existsSync(targetDir)) {
  console.log('Android project is not generated yet; Firebase config copy deferred.');
  process.exit(0);
}

fs.copyFileSync(source, target);
console.log(`Installed Firebase config for ${expectedPackage} at android/app/google-services.json`);
