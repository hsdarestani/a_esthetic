const sidebar = document.querySelector('#sidebar');

function setMenu(open) {
  sidebar?.classList.toggle('open', open);
  document.body.classList.toggle('menu-open', open);
  document.querySelector('[data-menu]')?.setAttribute('aria-expanded', String(open));
}

document.addEventListener('click', event => {
  if (event.target.closest('[data-menu]')) {
    setMenu(!sidebar?.classList.contains('open'));
    return;
  }
  if (event.target.closest('[data-menu-close]')) {
    setMenu(false);
    return;
  }
  if (event.target.closest('.sidebar.open a')) setMenu(false);
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') setMenu(false);
});

window.addEventListener('resize', () => {
  if (window.innerWidth > 1120) setMenu(false);
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
  if (range && top) {
    range.addEventListener('input', () => {
      top.style.clipPath = `inset(0 ${100 - range.value}% 0 0)`;
    });
  }
});
