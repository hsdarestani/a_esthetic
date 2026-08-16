(() => {
  'use strict';

  const rewardIcons = ['🎁', '◆', '♕', '✦', '◇', '★'];
  const historyIcons = ['★', '▣', '♥', '✦', '◆'];
  let queued = false;

  function navButton(route) {
    return document.querySelector(`.nav button[data-route="${route}"]`);
  }

  function relabelNavigation() {
    const nav = document.querySelector('.nav');
    if (!nav || nav.dataset.referenceNav === '1') return;
    nav.dataset.referenceNav = '1';
    nav.classList.add('reference-nav');

    const config = {
      home: { order: 1, icon: '⌂', label: 'Home' },
      wallet: { order: 2, icon: '🎁', label: 'Rewards' },
      club: { order: 3, icon: 'A+', label: '' },
      booking: { order: 4, icon: '◇', label: 'Termine' },
      more: { order: 5, icon: '◎', label: 'Profil' },
    };

    Object.entries(config).forEach(([route, meta]) => {
      const button = navButton(route);
      if (!button) return;
      button.style.order = String(meta.order);
      button.classList.toggle('nav-center', route === 'club');
      button.innerHTML = route === 'club'
        ? `<span class="nav-center-mark">A+</span><span class="nav-center-label">Club</span>`
        : `<span class="nav-icon">${meta.icon}</span><span>${meta.label}</span>`;
    });
  }

  function tuneTopbar(title) {
    const topbar = document.querySelector('.topbar');
    const brand = topbar?.querySelector('.topbrand');
    if (!topbar || !brand) return;
    topbar.classList.add('reference-topbar');
    const b = brand.querySelector('b');
    const small = brand.querySelector('small');
    if (b) b.textContent = title || 'A+ ESTHETIC';
    if (small) small.textContent = title ? 'CUSTOMER CLUB' : 'CUSTOMER CLUB';
  }

  function sectionByTitle(content, title) {
    return [...content.querySelectorAll(':scope > .card')].find(card =>
      card.querySelector(':scope > h2')?.textContent.trim().startsWith(title)
    );
  }

  function enhanceWallet() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading || !heading.textContent.includes('Wallet')) return false;
    if (content.dataset.referenceWallet === '1') return true;

    content.dataset.referenceWallet = '1';
    content.classList.add('reference-page', 'wallet-reference');
    document.body.dataset.referencePage = 'wallet';
    tuneTopbar('Wallet');

    const pagehead = heading.closest('.pagehead');
    const eyebrow = pagehead?.querySelector('span');
    const intro = pagehead?.querySelector('p');
    if (eyebrow) eyebrow.textContent = 'A+ ESTHETIC';
    heading.textContent = 'Wallet';
    if (intro) intro.textContent = 'Sammeln, einlösen und Vorteile jederzeit im Blick behalten.';

    const balanceGrid = content.querySelector(':scope > .grid2');
    const heroes = balanceGrid ? [...balanceGrid.querySelectorAll(':scope > .hero')] : [];
    const credit = heroes[0];
    const coins = heroes[1];

    if (coins) {
      coins.classList.add('wallet-balance-card');
      const small = coins.querySelector('small');
      const amount = coins.querySelector('h2');
      const text = coins.querySelector('p');
      if (small) small.textContent = 'Guthaben';
      if (amount) amount.classList.add('wallet-balance-number');
      if (text) text.innerHTML = '<span class="coin-symbol">✦</span> A+ Coins';
      if (!coins.querySelector('.wallet-emblem')) {
        coins.insertAdjacentHTML('beforeend', '<div class="wallet-emblem" aria-hidden="true"><span>A+</span></div>');
      }
    }

    if (credit) {
      credit.classList.add('wallet-credit-card');
      const small = credit.querySelector('small');
      const text = credit.querySelector('p');
      if (small) small.textContent = 'A+ Credit';
      if (text) text.textContent = 'Persönliches Club-Guthaben';
    }

    if (balanceGrid && coins && credit) {
      balanceGrid.insertBefore(coins, credit);
    }

    const rewards = sectionByTitle(content, 'Rewards');
    if (rewards) {
      rewards.classList.add('rewards-card');
      const title = rewards.querySelector(':scope > h2');
      if (title) title.innerHTML = 'Rewards <small class="section-action">Alle anzeigen</small>';
      const rows = [...rewards.querySelectorAll(':scope > .row')];
      rows.forEach((row, index) => {
        row.classList.add('reward-item');
        if (!row.querySelector('.reward-visual')) {
          row.insertAdjacentHTML('afterbegin', `<div class="reward-visual" aria-hidden="true"><span>${rewardIcons[index % rewardIcons.length]}</span></div>`);
        }
        const button = row.querySelector('[data-reward]');
        if (button) {
          button.classList.add('reward-cost');
          button.innerHTML = `<span class="mini-coin">✦</span> ${button.textContent.replace(/\s*Coins\s*/i, '').trim()}`;
        }
      });
      if (!rewards.querySelector('.redeem-jump')) {
        rewards.insertAdjacentHTML('beforeend', '<button type="button" class="redeem-jump"><span>🎁</span> Einlösen</button>');
        rewards.querySelector('.redeem-jump')?.addEventListener('click', () => {
          const first = rewards.querySelector('[data-reward]:not(:disabled)');
          first?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
          first?.classList.add('reward-pulse');
          setTimeout(() => first?.classList.remove('reward-pulse'), 1100);
        });
      }
    }

    const transactions = sectionByTitle(content, 'Transaktionen');
    if (transactions) {
      transactions.classList.add('history-card');
      const title = transactions.querySelector(':scope > h2');
      if (title) title.innerHTML = 'A+ Coins Historie <small class="section-action">Alle anzeigen</small>';
      [...transactions.querySelectorAll(':scope > .row')].forEach((row, index) => {
        row.classList.add('history-item');
        if (!row.querySelector('.history-icon')) {
          row.insertAdjacentHTML('afterbegin', `<span class="history-icon" aria-hidden="true">${historyIcons[index % historyIcons.length]}</span>`);
        }
      });
    }

    const packages = sectionByTitle(content, 'Pakete');
    if (packages) packages.classList.add('packages-card');

    if (transactions && !content.querySelector('.benefits-panel')) {
      transactions.insertAdjacentHTML('afterend', `
        <section class="benefits-panel">
          <h2>Deine Vorteile</h2>
          <div class="benefits-grid">
            <div><span>◇</span><b>Exklusive<br>Rewards</b></div>
            <div><span>♔</span><b>Geburtstags-<br>überraschungen</b></div>
            <div><span>⌁</span><b>Spezielle<br>Aktionen</b></div>
            <div><span>♕</span><b>Bevorzugte<br>Einladungen</b></div>
          </div>
        </section>`);
    }

    return true;
  }

  function enhanceHome() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading || !heading.textContent.trim().startsWith('Hallo ')) return false;
    content.classList.add('reference-page', 'home-reference');
    document.body.dataset.referencePage = 'home';
    tuneTopbar('A+ Esthetic');
    const hero = content.querySelector(':scope > .hero');
    hero?.classList.add('reference-member-card');
    return true;
  }

  function enhanceClub() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading || heading.textContent.trim() !== 'Customer Club') return false;
    content.classList.add('reference-page', 'club-reference');
    document.body.dataset.referencePage = 'club';
    tuneTopbar('Customer Club');
    content.querySelector(':scope > .hero')?.classList.add('reference-member-card');
    return true;
  }

  function enhanceGeneric() {
    const content = document.querySelector('.shell .content');
    const heading = content?.querySelector('.pagehead h1');
    if (!content || !heading) return;
    content.classList.add('reference-page');
    if (heading.textContent.trim() === 'Termine') document.body.dataset.referencePage = 'booking';
    if (heading.textContent.trim() === 'Profil') document.body.dataset.referencePage = 'profile';
  }

  function run() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      relabelNavigation();
      if (enhanceWallet()) return;
      if (enhanceHome()) return;
      if (enhanceClub()) return;
      enhanceGeneric();
    });
  }

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', run);
  window.addEventListener('load', run);
  setTimeout(run, 0);
})();
