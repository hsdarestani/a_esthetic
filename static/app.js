document.addEventListener('click', event => {
  const menu = event.target.closest('[data-menu]');
  if (menu) document.querySelector('#sidebar')?.classList.toggle('open');
  if (event.target.matches('.sidebar.open a')) document.querySelector('#sidebar')?.classList.remove('open');
});

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}

function csrfToken() {
  return document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  return Uint8Array.from([...raw].map(char => char.charCodeAt(0)));
}

document.querySelector('[data-enable-push]')?.addEventListener('click', async event => {
  const button = event.currentTarget;
  try {
    const registration = await navigator.serviceWorker.ready;
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error('Push-Berechtigung wurde nicht erteilt.');
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(button.dataset.vapid)
    });
    const response = await fetch('/push/subscribe/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrfToken())},
      body: JSON.stringify(subscription.toJSON())
    });
    if (!response.ok) throw new Error('Push konnte nicht gespeichert werden.');
    button.textContent = 'Push ist aktiviert';
    button.disabled = true;
  } catch (error) {
    window.alert(error.message || 'Push konnte nicht aktiviert werden.');
  }
});

document.querySelectorAll('[data-comparison]').forEach(wrapper => {
  const range = wrapper.querySelector('input[type="range"]');
  const top = wrapper.querySelector('.comparison-top');
  if (range && top) range.addEventListener('input', () => { top.style.clipPath = `inset(0 ${100 - range.value}% 0 0)`; });
});
