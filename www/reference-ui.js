(() => {
  'use strict';

  let queued = false;

  const svg = (body, cls = '') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
  const icons = {
    home: svg('<path d="M3.8 10.6 12 3.8l8.2 6.8v8.8a1 1 0 0 1-1 1h-4.7v-6.1h-5v6.1H4.8a1 1 0 0 1-1-1z"/>'),
    gift: svg('<path d="M4 10h16v10H4z"/><path d="M2.8 7h18.4v3H2.8zM12 7v13"/><path d="M12 7H8.7A2.7 2.7 0 1 1 12 3.4V7Zm0 0h3.3A2.7 2.7 0 1 0 12 3.4V7Z"/>'),
    calendar: svg('<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4M17 3v4M3 10h18"/><path d="m8.4 15 2.1 2.1 4.9-5"/>'),
    profile: svg('<circle cx="12" cy="8" r="3.7"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/>'),
    bell: svg('<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/>'),
    star: svg('<path d="m12 3 2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7L6.8 19l1-5.8-4.2-4.1 5.8-.8z"/>'),
    bag: svg('<path d="M5 8h14l1.2 13H3.8z"/><path d="M8.5 9V6.7a3.5 3.5 0 0 1 7 0V9"/>'),
    heart: svg('<path d="M20.8 4.9a5.4 5.4 0 0 0-7.7 0L12 6l-1.1-1.1a5.4 5.4 0 0 0-7.7 7.7L12 21l8.8-8.4a5.4 5.4 0 0 0 0-7.7Z"/>'),
    ticket: svg('<path d="M4 6h16v4a2.5 2.5 0 0 0 0 5v4H4v-4a2.5 2.5 0 0 0 0-5z"/><path d="M12 8.5v7"/>'),
    crown: svg('<path d="m3 8 4.4 3 4.6-6 4.6 6L21 8l-2 10H5z"/><path d="M6 21h12"/>'),
    sparkle: svg('<path d="m12 2 1.3 4.1L17 8l-3.7 1.9L12 14l-1.3-4.1L7 8l3.7-1.9z"/><path d="m19 14 .7 2.2L22 17l-2.3.8L19 20l-.7-2.2L16 17l2.3-.8z"/>'),
    refresh: svg('<path d="M20 7v5h-5"/><path d="M19 12a7 7 0 1 0-1.7 4.6"/>')
  };

  function lotus(cls = 'lotus-mark') {
    return `<svg class="${cls}" viewBox="0 0 120 92" aria-hidden="true">
      <g fill="none" stroke="currentColor" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round">
        <path d="M60 72C44 60 41 44 60 20c19 24 16 40 0 52Z"/>
        <path d="M57 70C38 69 25 59 22 38c18 2 30 11 35 32Z"/>
        <path d="M63 70c19-1 32-11 35-32-18 2-30 11-35 32Z"/>
        <path d="M48 72C30 77 17 73 8 63c17 0 28 2 40 9Z"/>
        <path d="M72 72c18 5 31 1 40-9-17 0-28 2-40 9Z"/>
        <path d="M60 20V8M43 28l-6-10M77 28l6-10"/>
        <circle cx="60" cy="5" r="1.8" fill="currentColor" stroke="none"/>
        <circle cx="34" cy="15" r="1.8" fill="currentColor" stroke="none"/>
        <circle cx="86" cy="15" r="1.8" fill="currentColor" stroke="none"/>
      </g>
      <text x="60" y="52" text-anchor="middle" font-family="Georgia,serif" font-size="15" font-style="italic" fill="currentColor">A+</text>
    </svg>`;
  }

  function rewardType(label = '') {
    const l = label.toLowerCase();
    if (l.includes('rabatt') || l.includes('%') || l.includes('discount')) return 'ticket';
    if (l.includes('bag') || l.includes('tasche')) return 'bag';
    if (l.includes('vip') || l.includes('upgrade') || l.includes('member')) return 'crown';
    if (l.includes('gift') || l.includes('geschenk')) return 'gift';
    if (l.includes('birthday') || l.includes('geburtstag')) return 'sparkle';
    return 'star';
  }

  function rewardArt(label) {
    const type = rewardType(label);
    const art = {
      gift: `<div class="gift-art"><i></i><i></i><i></i></div>`,
      ticket: `<div class="ticket-art"><span>10%</span><i></i></div>`,
      bag: `<div class="bag-art"><i></i><span>A+</span></div>`,
      crown: `<div class="vip-art">${lotus('mini-lotus')}<span>VIP</span></div>`,
      sparkle: `<div class="sparkle-art">${icons.sparkle}</div>`,
      star: `<div class="sparkle-art">${icons.star}</div>`
    };
    return `<div class="reward-art reward-art-${type}">${art[type]}</div>`;
  }

  function historyIcon(label = '') {
    const l = label.toLowerCase();
    if (l.includes('kauf') || l.includes('order') || l.includes('produkt')) return icons.bag;
    if (l.includes('bewert') || l.includes('review')) return icons.heart;
    if (l.includes('geburt')) return icons.sparkle;
    return icons.star;
  }

  function replaceRefreshWithBell() {
    const old = document.querySelector('.topbar [data-refresh], .topbar .iconbtn');
    if (!old || old.dataset.luxuryBell === '1') return;
    const bell = old.cloneNode(false);
    bell.removeAttribute('data-refresh');
    bell.dataset.luxuryBell = '1';
    bell.className = 'iconbtn luxury-bell';
    bell.setAttribute('aria-label', 'Benachrichtigungen');
    bell.innerHTML = `${icons.bell}<span class="notification-dot"></span>`;
    old.replaceWith(bell);
  }

  function navButton(route) {
    return document.querySelector(`.nav button[data-route="${route}"]`);
  }

  function rebuildNavigation() {
    const nav = document.querySelector('.nav');
    if (!nav || nav.dataset.luxuryNav === '1') return;
    nav.dataset.luxuryNav = '1';
    nav.classList.add('luxury-nav');
    const config = {
      home: { order: 1, icon: icons.home, label: 'Home' },
      wallet: { order: 2, icon: icons.gift, label: 'Rewards' },
      club: { order: 3, icon: lotus('nav-lotus'), label: 'Club', center: true },
      booking: { order: 4, icon: icons.calendar, label: 'Termine' },
      more: { order: 5, icon: icons.profile, label: 'Profil' }
    };
    Object.entries(config).forEach(([route, meta]) => {
      const button = navButton(route);
      if (!button) return;
      button.style.order = meta.order;
      button.classList.toggle('nav-center', !!meta.center);
      button.innerHTML = meta.center
        ? `<span class="nav-center-disc">${meta.icon}</span><span class="nav-label">${meta.label}</span>`
        : `<span class="nav-icon">${meta.icon}</span><span class="nav-label">${meta.label}</span>`;
    });
  }

  function tuneTopbar(title = 'A+ Esthetic') {
    const topbar = document.querySelector('.topbar');
    const brand = topbar?.querySelector('.topbrand');
    if (!topbar || !brand) return;
    topbar.classList.add('luxury-topbar');
    brand.innerHTML = `<span class="topbar-lotus">${lotus('topbar-lotus-svg')}</span><span class="topbar-title"><b>${title}</b><small>A+ ESTHETIC</small></span>`;
    replaceRefreshWithBell();
  }

  function sectionByTitle(content, title) {
    return [...content.querySelectorAll(':scope > .card')].find(card =>
      card.querySelector(':scope > h2')?.textContent.trim().startsWith(title)
    );
  }

  function addWalletHeaderCard(coins) {
    if (!coins || coins.querySelector('.wallet-lotus-watermark')) return;
    coins.insertAdjacentHTML('beforeend', `<div class="wallet-lotus-watermark">${lotus('wallet-lotus-svg')}</div><div class="wallet-shine"></div>`);
  }

  function enhanceRewardsCard(rewards) {
    if (!rewards || rewards.dataset.luxuryRewards === '1') return;
    rewards.dataset.luxuryRewards = '1';
    rewards.classList.add('luxury-rewards');
    const title = rewards.querySelector(':scope > h2');
    if (title) title.innerHTML = `Rewards <button type="button" class="section-link" tabindex="-1">Alle anzeigen</button>`;
    const rows = [...rewards.querySelectorAll(':scope > .row')];
    rows.forEach((row) => {
      row.classList.add('luxury-reward-card');
      const label = row.querySelector('.row-main b')?.textContent.trim() || 'Reward';
      if (!row.querySelector('.reward-art')) row.insertAdjacentHTML('afterbegin', rewardArt(label));
      const button = row.querySelector('[data-reward]');
      if (button) {
        button.classList.add('reward-cost-pill');
        const amount = button.textContent.replace(/\s*Coins\s*/i, '').trim();
        button.innerHTML = `<span class="coin-mini">✦</span><span>${amount}</span>`;
      }
    });
    if (!rewards.querySelector('.redeem-main')) {
      rewards.insertAdjacentHTML('beforeend', `<button type="button" class="redeem-main">${icons.gift}<span>Einlösen</span></button>`);
      rewards.querySelector('.redeem-main')?.addEventListener('click', () => {
        const first = rewards.querySelector('[data-reward]:not(:disabled)');
        first?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
        first?.closest('.luxury-reward-card')?.classList.add('reward-focus');
        setTimeout(() => first?.closest('.luxury-reward-card')?.classList.remove('reward-focus'), 900);
      });
    }
  }

  function enhanceHistory(transactions) {
    if (!transactions || transactions.dataset.luxuryHistory === '1') return;
    transactions.dataset.luxuryHistory = '1';
    transactions.classList.add('luxury-history');
    const title = transactions.querySelector(':scope > h2');
    if (title) title.innerHTML = `A+ Coins Historie <button type="button" class="section-link" tabindex="-1">Alle anzeigen</button>`;
    [...transactions.querySelectorAll(':scope > .row')].forEach(row => {
      row.classList.add('luxury-history-row');
      const label = row.querySelector('.row-main b')?.textContent || '';
      if (!row.querySelector('.history-orb')) row.insertAdjacentHTML('afterbegin', `<span class="history-orb">${historyIcon(label)}</span>`);
    });
  }

  function enhanceWallet() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading || !heading.textContent.includes('Wallet')) return false;
    if (content.dataset.luxuryWallet === '1') return true;
    content.dataset.luxuryWallet = '1';
    content.classList.add('luxury-page', 'luxury-wallet');
    document.body.dataset.luxuryPage = 'wallet';
    tuneTopbar('Wallet');

    const pagehead = heading.closest('.pagehead');
    pagehead?.classList.add('wallet-intro');
    const eyebrow = pagehead?.querySelector('span');
    const intro = pagehead?.querySelector('p');
    if (eyebrow) eyebrow.textContent = 'REWARDS & A+ COINS';
    heading.textContent = 'Wallet';
    if (intro) intro.textContent = 'Sammeln, einlösen und Vorteile jederzeit im Blick behalten.';

    const grid = content.querySelector(':scope > .grid2');
    const heroes = grid ? [...grid.querySelectorAll(':scope > .hero')] : [];
    const credit = heroes[0];
    const coins = heroes[1];
    if (coins) {
      coins.classList.add('wallet-balance');
      const small = coins.querySelector('small');
      const amount = coins.querySelector('h2');
      const text = coins.querySelector('p');
      if (small) small.textContent = 'Guthaben';
      if (amount) amount.classList.add('balance-number');
      if (text) text.innerHTML = `<span class="coin-round">✦</span><strong>A+ Coins</strong>`;
      addWalletHeaderCard(coins);
    }
    if (credit) {
      credit.classList.add('wallet-credit');
      const small = credit.querySelector('small');
      const text = credit.querySelector('p');
      if (small) small.textContent = 'A+ Credit';
      if (text) text.textContent = 'Persönliches Club-Guthaben';
    }
    if (grid && coins && credit) grid.insertBefore(coins, credit);

    enhanceRewardsCard(sectionByTitle(content, 'Rewards'));
    const packages = sectionByTitle(content, 'Pakete');
    if (packages) {
      packages.classList.add('luxury-packages');
      const h2 = packages.querySelector(':scope > h2');
      if (h2) h2.textContent = 'Deine Pakete';
    }
    const transactions = sectionByTitle(content, 'Transaktionen');
    enhanceHistory(transactions);

    if (transactions && !content.querySelector('.luxury-benefits')) {
      transactions.insertAdjacentHTML('afterend', `
        <section class="luxury-benefits">
          <h2>Deine Vorteile</h2>
          <div class="benefit-grid">
            <div><span>${icons.star}</span><b>Exklusive<br>Rewards</b></div>
            <div><span>${icons.sparkle}</span><b>Geburtstags-<br>überraschungen</b></div>
            <div><span>${icons.ticket}</span><b>Spezielle<br>Aktionen</b></div>
            <div><span>${icons.crown}</span><b>Bevorzugte<br>Einladungen</b></div>
          </div>
        </section>`);
    }
    return true;
  }

  function addMemberWatermark(hero) {
    if (!hero || hero.querySelector('.member-lotus')) return;
    hero.insertAdjacentHTML('beforeend', `<span class="member-lotus">${lotus('member-lotus-svg')}</span>`);
  }

  function enhanceHome() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading || !heading.textContent.trim().startsWith('Hallo ')) return false;
    if (content.dataset.luxuryHome === '1') return true;
    content.dataset.luxuryHome = '1';
    content.classList.add('luxury-page', 'luxury-home');
    document.body.dataset.luxuryPage = 'home';
    tuneTopbar('A+ Esthetic');
    const pagehead = heading.closest('.pagehead');
    pagehead?.classList.add('home-intro');
    const hero = content.querySelector(':scope > .hero');
    hero?.classList.add('luxury-member-card');
    addMemberWatermark(hero);
    [...content.querySelectorAll(':scope > .card')].forEach((card, i) => card.classList.add(i === 0 ? 'appointment-card' : 'reminder-card'));
    return true;
  }

  function enhanceClub() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading || heading.textContent.trim() !== 'Customer Club') return false;
    if (content.dataset.luxuryClub === '1') return true;
    content.dataset.luxuryClub = '1';
    content.classList.add('luxury-page', 'luxury-club');
    document.body.dataset.luxuryPage = 'club';
    tuneTopbar('Customer Club');
    const hero = content.querySelector(':scope > .hero');
    hero?.classList.add('luxury-member-card');
    addMemberWatermark(hero);
    return true;
  }

  function enhanceBooking() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading || heading.textContent.trim() !== 'Termine') return false;
    content.classList.add('luxury-page', 'luxury-booking');
    document.body.dataset.luxuryPage = 'booking';
    tuneTopbar('Termine');
    return true;
  }

  function enhanceMore() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading || heading.textContent.trim() !== 'Mehr') return false;
    content.classList.add('luxury-page', 'luxury-profile-hub');
    document.body.dataset.luxuryPage = 'profile';
    tuneTopbar('Profil');
    return true;
  }

  function enhanceLogin() {
    const auth = document.querySelector('.auth');
    const card = auth?.querySelector('.auth-card');
    if (!auth || !card || card.dataset.luxuryLogin === '1') return false;
    card.dataset.luxuryLogin = '1';
    auth.classList.add('luxury-auth');
    card.querySelector('.brandrow')?.classList.add('legacy-brandrow');
    card.insertAdjacentHTML('afterbegin', `<div class="luxury-login-brand">${lotus('login-lotus')}<b>A+ ESTHETIC</b><small>BEAUTY CLUB</small></div>`);
    return true;
  }

  function enhanceGeneric() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading) return;
    content.classList.add('luxury-page');
    tuneTopbar(heading.textContent.trim());
  }

  function run() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      if (enhanceLogin()) return;
      rebuildNavigation();
      if (enhanceWallet()) return;
      if (enhanceHome()) return;
      if (enhanceClub()) return;
      if (enhanceBooking()) return;
      if (enhanceMore()) return;
      enhanceGeneric();
    });
  }

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', run);
  window.addEventListener('load', run);
  setTimeout(run, 0);
})();