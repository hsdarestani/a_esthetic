document.addEventListener('click',e=>{const btn=e.target.closest('[data-menu]');if(btn)document.querySelector('#sidebar')?.classList.toggle('open');if(e.target.matches('.sidebar.open a'))document.querySelector('#sidebar')?.classList.remove('open')});
if('serviceWorker' in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('/sw.js').catch(()=>{}));
