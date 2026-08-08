import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const node = process.execPath;
execFileSync(node, ['scripts/prepare-mobile.mjs', 'ios'], { stdio: 'inherit', env: process.env });

const teamId = process.env.APPLE_TEAM_ID || process.env.IOS_TEAM_ID;
if (!teamId) {
  console.error('Missing APPLE_TEAM_ID (or IOS_TEAM_ID).');
  process.exit(2);
}

const signingStyle = process.env.IOS_SIGNING_STYLE || 'automatic';
const exportMethod = process.env.IOS_EXPORT_METHOD || 'app-store-connect';
const signingCertificate = process.env.IOS_SIGNING_CERTIFICATE;
const provisioningProfile = process.env.IOS_PROVISIONING_PROFILE;

if (signingStyle === 'manual' && (!signingCertificate || !provisioningProfile)) {
  console.error('Manual iOS signing requires IOS_SIGNING_CERTIFICATE and IOS_PROVISIONING_PROFILE.');
  process.exit(2);
}

const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const args = [
  'cap', 'build', 'ios',
  '--scheme', process.env.IOS_SCHEME || 'App',
  '--configuration', process.env.IOS_CONFIGURATION || 'Release',
  '--xcode-team-id', teamId,
  '--xcode-export-method', exportMethod,
  '--xcode-signing-style', signingStyle,
];
if (signingCertificate) args.push('--xcode-signing-certificate', signingCertificate);
if (provisioningProfile) args.push('--xcode-provisioning-profile', provisioningProfile);

execFileSync(npx, args, { stdio: 'inherit', env: process.env });

function findFiles(dir, extension, out = []) {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) findFiles(path, extension, out);
    else if (entry.name.endsWith(extension)) out.push(path);
  }
  return out;
}

const ipas = findFiles('ios', '.ipa')
  .map((path) => ({ path, mtime: statSync(path).mtimeMs }))
  .sort((a, b) => b.mtime - a.mtime);
if (!ipas.length) {
  console.error('Capacitor build completed but no IPA artifact was found.');
  process.exit(3);
}

mkdirSync('dist', { recursive: true });
const output = 'dist/a-esthetic.ipa';
copyFileSync(ipas[0].path, output);
console.log(`IOS_ARTIFACT=${resolve(output)}`);
