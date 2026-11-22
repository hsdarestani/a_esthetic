// The global Capacitor native bridge is injected by iOS/Android on app startup.
// The plugin must ALSO be registered in JavaScript, per Capacitor's custom plugin API.
import { Capacitor, registerPlugin } from '@capacitor/core';

if (Capacitor.isNativePlatform()) {
  const staffPlugin = registerPlugin('NativeStaff');
  // Do not fake the native implementation in a browser or silently downgrade.
  // Expose the proxy even if availability headers have not been populated at
  // boot time. Let the first native call report its real error instead of
  // incorrectly suppressing a compiled Swift plugin.
  window.APlusNativeStaff = staffPlugin;
  window.APlusNativeStaffAvailable = Capacitor.isPluginAvailable('NativeStaff');
  // Read-only bridge self-test before staff sign-in; never includes credentials.
  // Enables real device/Simulator QA to distinguish JS registration from
  // native Swift loading. Failed probes are deliberately handled.
  window.APlusNativeStaffProbe = staffPlugin.probe()
    .then(result => {
      const ok = Boolean(result?.ok && result?.native);
      console.info(ok ? 'APLUS_NATIVE_STAFF_PROBE_OK' : 'APLUS_NATIVE_STAFF_PROBE_INVALID');
      return {ok, code:ok ? 'OK' : 'INVALID_RESPONSE'};
    })
    .catch(error => {
      const code = String(error?.code || 'NATIVE_BRIDGE_ERROR').slice(0,48);
      console.warn('APLUS_NATIVE_STAFF_PROBE_FAILED', code);
      return {ok:false, code};
    });
}
