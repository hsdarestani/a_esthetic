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
}
