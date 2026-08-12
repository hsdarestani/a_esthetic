(() => {
  'use strict';

  const featureMeta = [
    { match: 'Nachrichten', icon: '✉', subtitle: 'Direkter Kontakt zum A+ Team', tone: 'dark' },
    { match: 'Erinnerungen', icon: '◷', subtitle: 'Termine & wichtige Hinweise', tone: 'sage' },
    { match: 'Profil', icon: '◎', subtitle: 'Konto & persönliche Einstellungen', tone: 'gold' },
    { match: 'Support', icon: '?', subtitle: 'Hilfe, Antworten & Kontakt', tone: 'rose' },
    { match: 'Fortschritt', icon: '◫', subtitle: 'Ihre private Beauty Journey', tone: 'rose' },
    { match: 'Nachsorge', icon: '✓', subtitle: 'Persönliche Hinweise im Blick', tone: 'sage' },
    { match: 'Beauty Plan', icon: '✦', subtitle: 'Ziele, Schritte & Planung', tone: 'gold' },
    { match: 'Mitgliedskarte', icon: '◆', subtitle: 'Member ID & Wallet Pass', tone: 'dark' },
    { match: 'Beauty Cabinet', icon: '◇', subtitle: 'Produkte & Routinen verwalten', tone: 'gold' },
    { match: 'Shop', icon: '◉', subtitle: 'A+ Auswahl & Bestellungen', tone: 'rose' },
    { match: 'Challenges', icon: '✦', subtitle: 'Club Challenges & Badges', tone: 'dark' },
    { match: 'Events', icon: '◆', subtitle: 'Einladungen & Member Events', tone: 'gold' },
    { match: 'Concierge', icon: '◎', subtitle: 'Premium Service & Organisation', tone: 'dark' },
  ];

  function cleanLabel(value = '') {
    return String(value).replace(/^[^A-Za-zÄÖÜäöüß0-9?]+\s*/, '').trim();
  }

  function enhanceLogin() {
    const auth = document.querySelector('.auth');
    if (!auth || auth.querySelector('.auth-showcase')) return;
    const panel = document.createElement('section');
    panel.className = 'auth-showcase';
    panel.setAttribute('aria-hidden', 'true');
    panel.innerHTML = `
      <div class="auth-showcase-brand">
        <div class="brandmark">A+</div>
        <div><b>A+ ESTHETIC</b><small>PRIVATE CUSTOMER CLUB</small></div>
      </div>
      <div class="auth-showcase-copy">
        <span class="auth-eyebrow">Private Member Experience</span>
        <h2>Beauty, beautifully <em>organized.</em></h2>
        <p>Ihr persönlicher A+ Space für Membership, Beauty Journey, Termine, Produkte, Events und Concierge – an einem Ort.</p>
        <div class="auth-feature-row">
          <span class="auth-feature-pill"><i></i>Member Wallet</span>
          <span class="auth-feature-pill"><i></i>Beauty Journey</span>
          <span class="auth-feature-pill"><i></i>Private Concierge</span>
        </div>
      </div>
      <div class="auth-showcase-foot"><span>FRANKFURT · A+ ESTHETIC</span><span>MEMBER EXPERIENCE · 2026</span></div>`;
    auth.insertBefore(panel, auth.firstChild);
  }

  function enhanceHome() {
    const heading = [...document.querySelectorAll('.pagehead h1')].find(node => node.textContent.trim().startsWith('Hallo '));
    if (!heading) return;
    const content = heading.closest('.content');
    if (!content) return;
    content.classList.add('dashboard-home');
    document.body.dataset.wowPage = 'home';

    const hero = content.querySelector('.hero');
    if (hero && !hero.dataset.wowHero) {
      hero.dataset.wowHero = '1';
      const firstSmall = hero.querySelector('small');
      if (firstSmall) firstSmall.classList.add('hero-label');
      const emblem = document.createElement('div');
      emblem.className = 'hero-emblem';
      emblem.textContent = 'A+';
      hero.appendChild(emblem);
    }

    const stats = content.querySelector('.stats');
    if (stats) {
      const cards = [...content.querySelectorAll(':scope > .card')];
      cards[0]?.classList.add('dashboard-primary');
      cards[1]?.classList.add('dashboard-secondary');
    }
  }

  function tileMeta(node) {
    const label = cleanLabel(node.dataset.wowOriginal || node.textContent);
    return featureMeta.find(item => label.includes(item.match));
  }

  function enhanceFeatureTile(node) {
    if (!node || node.dataset.wowTile === '1') return;
    const original = node.textContent.trim();
    const meta = tileMeta(node);
    if (!meta) return;
    node.dataset.wowOriginal = original;
    node.dataset.wowTile = '1';
    node.dataset.tone = meta.tone;
    node.classList.add('feature-tile');
    const title = cleanLabel(original);
    node.innerHTML = `<span class="feature-icon">${meta.icon}</span><span class="feature-title">${title}</span><small class="feature-subtitle">${meta.subtitle}</small>`;
  }

  function enhanceMore() {
    const heading = [...document.querySelectorAll('.pagehead h1')].find(node => node.textContent.trim() === 'Mehr');
    if (!heading) return;
    const content = heading.closest('.content');
    if (!content) return;
    content.classList.add('more-hub');
    document.body.dataset.wowPage = 'more';

    if (!content.querySelector('.experience-banner')) {
      const banner = document.createElement('section');
      banner.className = 'experience-banner';
      banner.innerHTML = `
        <small>Your A+ World</small>
        <h2>Alles, was Ihre Beauty Journey besonders macht.</h2>
        <p>Entdecken Sie Ihren privaten Member Space – von persönlicher Planung und Produkten bis zu Events und Concierge.</p>
        <div class="experience-meta"><span>Private</span><span>Personal</span><span>Premium</span></div>`;
      heading.closest('.pagehead')?.insertAdjacentElement('afterend', banner);
    }

    const cards = [...content.querySelectorAll(':scope > .card')];
    const featureCard = cards.find(card => card.querySelector('.more-grid'));
    if (featureCard) {
      featureCard.classList.add('feature-card');
      featureCard.querySelectorAll('.more-grid > button, .more-grid > a').forEach(enhanceFeatureTile);
    }
    cards.forEach(card => {
      if (card !== featureCard && card.querySelector('.more-grid')) card.classList.add('legal-card');
    });

    const logout = content.querySelector('#logout');
    if (logout && !logout.closest('.logout-wrap')) {
      const wrap = document.createElement('div');
      wrap.className = 'logout-wrap';
      logout.parentNode.insertBefore(wrap, logout);
      wrap.appendChild(logout);
    }
  }

  function enhanceGeneralPage() {
    const content = document.querySelector('.shell .content');
    const h1 = content?.querySelector('.pagehead h1');
    if (!content || !h1) return;
    if (h1.textContent.trim().startsWith('Hallo ') || h1.textContent.trim() === 'Mehr') return;
    document.body.dataset.wowPage = h1.textContent.trim().toLowerCase().replace(/[^a-z0-9äöüß]+/g, '-');
  }

  let queued = false;
  function run() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      enhanceLogin();
      enhanceHome();
      enhanceMore();
      enhanceGeneralPage();
    });
  }

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', run);
  window.addEventListener('load', run);
  setTimeout(run, 0);
})();
