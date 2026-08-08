import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const node = process.execPath;
execFileSync(node, ['scripts/prepare-mobile.mjs', 'android'], { stdio: 'inherit', env: process.env });

const keystorePath = process.env.ANDROID_KEYSTORE_PATH;
const keystorePass = process.env.ANDROID_KEYSTORE_PASSWORD || process.env.ANDROID_KEYSTORE_PASS;
const keystoreAlias = process.env.ANDROID_KEY_ALIAS;
const aliasPass = process.env.ANDROID_KEY_PASSWORD || process.env.ANDROID_KEY_ALIAS_PASSWORD;

const missing = [];
if (!keystorePath) missing.push('ANDROID_KEYSTORE_PATH');
if (!keystorePass) missing.push('ANDROID_KEYSTORE_PASSWORD');
if (!keystoreAlias) missing.push('ANDROID_KEY_ALIAS');
if (!aliasPass) missing.push('ANDROID_KEY_PASSWORD');
if (missing.length) {
  console.error(`Missing Android signing environment variables: ${missing.join(', ')}`);
  process.exit(2);
}
if (!existsSync(keystorePath)) {
  console.error(`Android keystore not found: ${keystorePath}`);
  process.exit(2);
}

const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
execFileSync(npx, [
  'cap', 'build', 'android',
  '--androidreleasetype', 'AAB',
  '--keystorepath', resolve(keystorePath),
  '--keystorepass', keystorePass,
  '--keystorealias', keystoreAlias,
  '--keystorealiaspass', aliasPass,
  '--signing-type', process.env.ANDROID_SIGNING_TYPE || 'jarsigner',
], { stdio: 'inherit', env: process.env });

function findFiles(dir, extension, out = []) {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) findFiles(path, extension, out);
    else if (entry.name.endsWith(extension)) out.push(path);
  }
  return out;
}

const bundles = findFiles('android', '.aab')
  .map((path) => ({ path, mtime: statSync(path).mtimeMs }))
  .sort((a, b) => b.mtime - a.mtime);
if (!bundles.length) {
  console.error('Capacitor build completed but no AAB artifact was found.');
  process.exit(3);
}

mkdirSync('dist', { recursive: true });
const output = 'dist/a-esthetic.aab';
copyFileSync(bundles[0].path, output);
console.log(`ANDROID_ARTIFACT=${resolve(output)}`);
