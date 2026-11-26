(() => {
  'use strict';

  const API = `${window.APlusRuntime.origin}/api/mobile/staff`;
  let owner;
  let closing=Promise.resolve();
  let pendingRoute;

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
    mount(root, token, role, logout, {forceWeb=false,navigation}={}) {
      const native = Boolean(window.Capacitor?.isNativePlatform?.()) && !forceWeb;
      if(owner?.token===token && owner.native===native)return owner.ready;
      if(owner)this.unmount();
      const instance={token,native,abort:new AbortController()};
      owner=instance;
      instance.ready=closing.then(async()=>{
        if(owner!==instance)return;
        const initialRoute=pendingRoute;
        pendingRoute=null;
        instance.workspace=await createWorkspace(root,token,role,logout,{native,navigation,signal:instance.abort.signal,initialRoute});
        if(owner===instance && pendingRoute){
          const route=pendingRoute;
          pendingRoute=null;
          openRoute(instance.workspace,route);
        }
      }).catch(error=>{
        if(owner!==instance)return;
        owner=null;
        throw error;
      });
      return instance.ready;
    },
    open({patientId} = {}) {
      const ident=Number(patientId);
      const route=ident>0?ident:'calendar';
      if(owner?.workspace)openRoute(owner.workspace,route);
      else if(localStorage.getItem('aplus_token'))pendingRoute=route;
    },
    back() {
      return owner ? (owner.workspace?.back() ?? true) : false;
    },
    unmount() {
      pendingRoute=null;
      const former=owner;
      owner=null;
      if(former){
        former.abort.abort();
        closing=former.ready.catch(()=>{}).then(()=>former.workspace?.destroy()).catch(()=>{});
      }
      return closing;
    },
  };

  function openRoute(workspace,route){
    if(route==='calendar')workspace.openCalendar();
    else workspace.openPatient(route);
  }

  async function createWorkspace(root,token,role,logout,{native,navigation,signal,initialRoute}){
      if (native) {
        try {
          await import('./mobile/native-staff-bridge.js');
        } catch (cause) {
          const error = new Error('Die Native-Bridge konnte nicht geladen werden.');
          error.code = 'NATIVE_BRIDGE_IMPORT';
          throw error;
        }
        const renderer = window.APlusNativeStaff || window.Capacitor?.Plugins?.NativeStaff;
        if (!renderer) {
          const error = new Error('Die NativeStaff-Schnittstelle wurde nicht registriert.');
          error.code = 'NATIVE_PLUGIN_NOT_REGISTERED';
          throw error;
        }
        try {
          const {mountNativeWorkspace} = await import('./mobile/native-workspace.mjs');
          return await mountNativeWorkspace({token,identity:role,origin:window.APlusRuntime.origin,logout,navigation,signal,
            initialPatient:typeof initialRoute==='number'?initialRoute:null,initialCalendar:initialRoute==='calendar'});
        } catch (cause) {
          const error = new Error(cause?.message || 'Native Ansicht konnte nicht geöffnet werden.');
          error.code = String(cause?.code || 'NATIVE_SCREEN_OPEN_FAILED').slice(0,64);
          error.status = cause?.status;
          throw error;
        }
      }
      // Explicit, user-selected temporary Web management when a device fails
      // to open Native. Never pretend this fallback is SwiftUI.
      const {mountWorkspace} = await import('./mobile/workspace.mjs');
      signal.throwIfAborted();
      const workspace=mountWorkspace({root,token,identity:role,origin:window.APlusRuntime.origin,logout});
      if(initialRoute)openRoute(workspace,initialRoute);
      return workspace;
  }
})();
