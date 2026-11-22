// The global Capacitor native bridge is injected by iOS/Android on app startup.
// The plugin must ALSO be registered in JavaScript, per Capacitor's custom plugin API.
import { Capacitor, registerPlugin } from '@capacitor/core';

if (Capacitor.isNativePlatform()) {
  const staffPlugin = registerPlugin('NativeStaff');
  // Do not fake the native implementation in a browser or silently downgrade.
  window.APlusNativeStaff = Capacitor.isPluginAvailable('NativeStaff') ? staffPlugin : null;
}
