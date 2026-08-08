import { existsSync, readFileSync } from 'node:fs';

const required = [
  'package.json',
  'capacitor.config.json',
  'www/index.html',
  'www/app.css',
  'www/app.js',
  'scripts/prepare-mobile.mjs',
  'scripts/build-android.mjs',
  'scripts/build-ios.mjs',
];

const missing = required.filter((path) => !existsSync(path));
if (missing.length) {
  console.error(`Missing mobile files: ${missing.join(', ')}`);
  process.exit(1);
}

const config = JSON.parse(readFileSync('capacitor.config.json', 'utf8'));
if (config.appId !== 'de.aplusesthetic.club') {
  console.error(`Unexpected appId: ${config.appId}`);
  process.exit(1);
}
if (config.server?.url) {
  console.error('Production config must not use Capacitor server.url.');
  process.exit(1);
}
if (config.webDir !== 'www') {
  console.error(`Unexpected webDir: ${config.webDir}`);
  process.exit(1);
}

const mobileText = [
  readFileSync('www/index.html', 'utf8'),
  readFileSync('www/app.js', 'utf8'),
].join('\n').toLowerCase();
const forbidden = ['diagnose', 'therapie', 'gesundheitsdaten', 'medizinische beratung', 'medical advice', 'health data'];
const found = forbidden.filter((term) => mobileText.includes(term));
if (found.length) {
  console.error(`Customer-club mobile UI contains forbidden health/medical positioning: ${found.join(', ')}`);
  process.exit(1);
}

console.log('A+ Esthetic mobile release validation passed.');
