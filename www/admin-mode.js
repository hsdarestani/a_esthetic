(() => {
  'use strict';

  const API = `${window.APlusRuntime.origin}/api/mobile/staff`;
  let workspace;
  let pendingPatient;
  let pendingCalendar = false;

  // Existing Book sessions can still return to this app with this logout marker.
  const params = new URLSearchParams(location.search);
  if (params.get('admin_logout') === '1') {
    localStorage.removeItem('aplus_token');
    sessionStorage.removeItem('aplus_admin_resume');
    params.delete('admin_logout');
    history.replaceState(null, '', location.pathname + (params.size ? '?' + params : '') + location.hash);
  }

  async function resolve(token) {
    const response = await fetch(API + '/session/', {
      headers: {Authorization: 'Bearer ' + token, Accept: 'application/json'},
      cache: 'no-store', aplusSilent: true, signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      const error = new Error('Sitzung konnte nicht geprüft werden.');
      if (response.status === 401) error.code = 'staff_session_expired';
      throw error;
    }
    return response.json();
  }

  window.APlusAdminMode = {
    resolve,
    async mount(root, token, role, logout) {
      await this.unmount();
      if (window.Capacitor?.isNativePlatform?.() && window.Capacitor?.Plugins?.NativeStaff) {
        const {mountNativeWorkspace} = await import('./mobile/native-workspace.mjs');
        workspace = await mountNativeWorkspace({token, identity:role, origin:window.APlusRuntime.origin, logout,
          initialPatient:pendingPatient, initialCalendar:pendingCalendar});
        pendingPatient = null;
        pendingCalendar = false;
        return;
      }
      const {mountWorkspace} = await import('./mobile/workspace.mjs');
      workspace = mountWorkspace({root, token, identity: role, origin: window.APlusRuntime.origin, logout});
      if (pendingPatient) {
        workspace.openPatient(pendingPatient);
        pendingPatient = null;
      } else if (pendingCalendar) {
        workspace.openCalendar();
      }
      pendingCalendar = false;
    },
    open({patientId} = {}) {
      const ident = Number(patientId);
      if (workspace) {
        if (ident > 0) workspace.openPatient(ident);
        else workspace.openCalendar();
      } else if (localStorage.getItem('aplus_token')) {
        if (ident > 0) pendingPatient = ident;
        else pendingCalendar = true;
      }
    },
    back() {
      return workspace?.back() || false;
    },
    unmount() {
      const former = workspace;
      workspace = null;
      return former?.destroy();
    },
  };
})();
