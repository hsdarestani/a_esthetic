// Bundle the official Capacitor JavaScript registration for the local staff plugin.
// Native Swift/Java registration alone does not install a web-facing JS proxy.
import { build } from 'esbuild';
import { mkdir } from 'node:fs/promises';

await mkdir('www/mobile', { recursive: true });
await build({
  entryPoints: ['scripts/native_staff_bridge_entry.mjs'],
  outfile: 'www/mobile/native-staff-bridge.js',
  platform: 'browser',
  format: 'iife',
  bundle: true,
  target: ['safari16', 'chrome105'],
  minify: true,
  sourcemap: false,
  logLevel: 'warning',
});
console.log('Built Capacitor NativeStaff JavaScript bridge');
