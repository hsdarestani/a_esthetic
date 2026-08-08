import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';

const platform = process.argv[2];
if (!['android', 'ios'].includes(platform)) {
  console.error('Usage: node scripts/prepare-mobile.mjs <android|ios>');
  process.exit(2);
}

const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const run = (args) => execFileSync(npx, args, { stdio: 'inherit', env: process.env });

if (!existsSync('node_modules/@capacitor/cli')) {
  console.error('Capacitor dependencies are missing. Run npm install first.');
  process.exit(2);
}

if (!existsSync(platform)) {
  run(['cap', 'add', platform]);
}

run(['cap', 'sync', platform]);
console.log(`Capacitor ${platform} project is ready.`);
