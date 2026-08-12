(() => {
  'use strict';

  const API_BASE = 'https://esthetic.smarbiz.sbs/api/mobile';
  const cart = new Map();
  const objectUrls = new Set();

  const token = () => localStorage.getItem('aplus_token') || '';
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const euro = cents => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format((Number(cents) || 0) / 100);
  const dateOnly = value => value ? new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(`${value}T12:00:00`)) : '–';
  const dateTime = value => value ? new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '–';

  function clearObjectUrls() {
    objectUrls.forEach(url => URL.revokeObjectURL(url));
    objectUrls.clear();
  }

  function humanError(code) {
    const errors = {
      authentication_required: 'Bitte melden Sie sich erneut an.',
      wallet_provider_not_configured: 'Dieser Wallet-Anbieter ist serverseitig noch nicht freigeschaltet.',
      wallet_generation_failed: 'Die Wallet-Karte konnte nicht erzeugt werden.',
      name_required: 'Bitte geben Sie einen Produktnamen ein.',
      invalid_opened_date: 'Bitte prüfen Sie das Öffnungsdatum.',
      invalid_expiry_date: 'Bitte prüfen Sie das Ablaufdatum.',
      expiry_before_opened: 'Das Ablaufdatum muss nach dem Öffnungsdatum liegen.',
      cabinet_product_not_found: 'Dieses Produkt wurde nicht gefunden.',
      invalid_routine_period: 'Bitte wählen Sie eine gültige Routine.',
      invalid_weekdays: 'Bitte prüfen Sie die Wochentage.',
      routine_not_found: 'Dieser Routine-Schritt wurde nicht gefunden.',
      items_required: 'Ihr Warenkorb ist leer.',
      invalid_order_item: 'Bitte prüfen Sie den Warenkorb.',
      quantity_too_large: 'Die gewählte Menge ist zu hoch.',
      invalid_delivery_method: 'Bitte wählen Sie Abholung oder Versand.',
      shipping_address_required: 'Für Versand ist eine Lieferadresse erforderlich.',
      product_unavailable: 'Ein Produkt ist aktuell nicht verfügbar.',
      product_not_shippable: 'Ein Produkt ist nicht für Versand verfügbar.',
      product_not_collectable: 'Ein Produkt ist nicht für Abholung verfügbar.',
      insufficient_stock: 'Die gewünschte Menge ist aktuell nicht verfügbar.',
      order_total_too_large: 'Diese Bestellung kann nicht in einem Schritt verarbeitet werden.',
      order_not_found: 'Diese Bestellung wurde nicht gefunden.',
      order_cannot_be_cancelled: 'Diese Bestellung kann nicht mehr direkt in der App storniert werden.'
    };
    return errors[code] || 'Die Aktion konnte nicht durchgeführt werden.';
  }

  async function p2Api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok || body.ok === false) {
      const error = new Error(humanError(body.error));
      error.code = body.error;
      error.status = response.status;
      throw error;
    }
    return body;
  }

  function content() {
    return document.querySelector('.shell .content');
  }

  function backMarkup(kicker, title, subtitle) {
    return `<div class="pagehead"><span>${esc(kicker)}</span><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>
      <div class="actions" style="margin-bottom:12px"><button class="btn ghost" type="button" data-p2-back>← Mehr</button></div>`;
  }

  function bindBack() {
    document.querySelector('[data-p2-back]')?.addEventListener('click', () => {
      clearObjectUrls();
      const more = document.querySelector('.nav [data-route="more"]');
      if (more) more.click();
    });
  }

  function p2Loading(kicker, title, subtitle) {
    const target = content();
    if (!target) return false;
    clearObjectUrls();
    target.innerHTML = `${backMarkup(kicker, title, subtitle)}<div class="loading">Wird geladen…</div>`;
    bindBack();
    return true;
  }

  function p2Fail(error, retry) {
    const target = content();
    if (!target) return;
    target.innerHTML += `<div class="errorbox">${esc(error.message)}</div><div class="actions"><button class="btn primary" type="button" data-p2-retry>Erneut versuchen</button></div>`;
    target.querySelector('[data-p2-retry]')?.addEventListener('click', retry);
  }

  async function loadWalletQr() {
    const image = document.querySelector('[data-p2-wallet-qr]');
    if (!image) return;
    try {
      const response = await fetch(`${API_BASE}/wallet-pass/qr/`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      if (!response.ok) throw new Error('qr_failed');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      objectUrls.add(url);
      image.src = url;
    } catch (_) {
      image.replaceWith(Object.assign(document.createElement('div'), { className: 'empty', textContent: 'QR-Code nicht verfügbar' }));
    }
  }

  async function downloadApplePass(button) {
    button.disabled = true;
    const old = button.textContent;
    button.textContent = 'Wird erstellt…';
    try {
      const response = await fetch(`${API_BASE}/wallet-pass/apple/`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      if (!response.ok) {
        let body = {};
        try { body = await response.json(); } catch (_) {}
        throw new Error(humanError(body.error));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      objectUrls.add(url);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'A-Plus-Esthetic.pkpass';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } catch (error) {
      alert(error.message);
    } finally {
      button.disabled = false;
      button.textContent = old;
    }
  }

  async function showWallet() {
    if (!p2Loading('A+ Beauty Club', 'Mitgliedskarte', 'Ihre digitale A+ Karte, QR und Wallet.')) return;
    try {
      const data = await p2Api('/wallet-pass/');
      const card = data.card;
      const target = content();
      target.innerHTML = `${backMarkup('A+ Beauty Club', 'Mitgliedskarte', 'Ihre digitale A+ Karte, QR und Wallet.')}
        <section class="card" style="background:linear-gradient(135deg,#111a22,#253642);color:#fff;border:none;overflow:hidden;position:relative">
          <div style="position:absolute;width:180px;height:180px;border-radius:50%;right:-70px;top:-80px;background:rgba(199,154,98,.2)"></div>
          <div style="display:flex;justify-content:space-between;gap:16px;position:relative">
            <div>
              <small style="color:#f0d7ad;letter-spacing:.12em">A+ ESTHETIC · BEAUTY CLUB</small>
              <h2 style="font-size:26px;margin:10px 0 2px;color:#fff">${esc(card.name)}</h2>
              <div style="color:#f0d7ad;font-weight:700">${esc(card.tier)}</div>
              <div style="margin-top:18px;font-size:12px;opacity:.7">MITGLIEDSNUMMER</div>
              <div style="font-weight:700;letter-spacing:.08em">${esc(card.member_number)}</div>
            </div>
            <div style="background:#fff;padding:8px;border-radius:14px;width:112px;height:112px;flex:none">
              <img data-p2-wallet-qr alt="A+ Mitglieds-QR" style="width:100%;height:100%;object-fit:contain">
            </div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:20px;position:relative">
            <div><small style="opacity:.7">A+ Coins</small><b style="display:block">${Number(card.coin_balance) || 0}</b></div>
            <div><small style="opacity:.7">A+ Credit</small><b style="display:block">${euro(card.credit_cents)}</b></div>
            <div><small style="opacity:.7">Status</small><b style="display:block">${esc(card.status_label)}</b></div>
          </div>
        </section>
        <section class="card">
          <h2>In Wallet speichern</h2>
          <p class="muted">Die digitale Karte oben funktioniert immer. Apple/Google Wallet wird nur aktiviert, wenn der jeweilige Anbieter serverseitig konfiguriert ist.</p>
          <div class="actions">
            ${data.providers.apple.configured
              ? '<button class="btn primary" type="button" data-p2-apple> Apple Wallet</button>'
              : '<button class="btn ghost" type="button" disabled> Apple Wallet · Einrichtung</button>'}
            ${data.providers.google.configured
              ? '<button class="btn primary" type="button" data-p2-google>Google Wallet</button>'
              : '<button class="btn ghost" type="button" disabled>Google Wallet · Einrichtung</button>'}
          </div>
        </section>
        <div class="notice">${esc(data.note)}</div>`;
      bindBack();
      await loadWalletQr();
      target.querySelector('[data-p2-apple]')?.addEventListener('click', event => downloadApplePass(event.currentTarget));
      target.querySelector('[data-p2-google]')?.addEventListener('click', async event => {
        event.currentTarget.disabled = true;
        try {
          const result = await p2Api('/wallet-pass/google/');
          window.location.href = result.save_url;
        } catch (error) {
          alert(error.message);
          event.currentTarget.disabled = false;
        }
      });
    } catch (error) { p2Fail(error, showWallet); }
  }

  function expiryBadge(expiresOn) {
    if (!expiresOn) return '';
    const now = new Date();
    const expires = new Date(`${expiresOn}T12:00:00`);
    const days = Math.ceil((expires - now) / 86400000);
    if (days < 0) return '<span class="badge">Abgelaufen</span>';
    if (days <= 30) return `<span class="badge">Noch ${days} Tage</span>`;
    return '';
  }

  function weekdayOptions() {
    const days = [['0','Mo'],['1','Di'],['2','Mi'],['3','Do'],['4','Fr'],['5','Sa'],['6','So']];
    return `<div style="display:flex;flex-wrap:wrap;gap:8px">${days.map(([value,label]) => `<label class="check" style="margin:0"><input type="checkbox" name="weekday" value="${value}"><span>${label}</span></label>`).join('')}</div>`;
  }

  async function showCabinet() {
    if (!p2Loading('Ihre Produkte', 'Beauty Cabinet', 'Produkte, Haltbarkeit und persönliche Routinen an einem Ort.')) return;
    try {
      const data = await p2Api('/cabinet/');
      const target = content();
      target.innerHTML = `${backMarkup('Ihre Produkte', 'Beauty Cabinet', 'Produkte, Haltbarkeit und persönliche Routinen an einem Ort.')}
        <div class="notice">${esc(data.safety_note)}</div>
        <section class="card">
          <h2>Produkt hinzufügen</h2>
          <form id="p2-cabinet-form" class="form">
            <label>Name<input name="name" maxlength="180" required placeholder="z. B. Hydration Serum"></label>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
              <label>Marke<input name="brand" maxlength="120"></label>
              <label>Kategorie<input name="category" maxlength="80" placeholder="Serum, SPF …"></label>
            </div>
            <label>Barcode<input name="barcode" maxlength="64" inputmode="numeric"></label>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
              <label>Geöffnet am<input name="opened_on" type="date"></label>
              <label>Haltbar bis<input name="expires_on" type="date"></label>
            </div>
            <label>Eigene Notiz<textarea name="notes" rows="2" maxlength="3000"></textarea></label>
            <button class="btn primary" type="submit">Zum Cabinet hinzufügen</button>
          </form>
        </section>
        ${data.products.length ? data.products.map(product => `
          <section class="card" style="opacity:${product.archived ? '.62' : '1'}">
            <div class="row"><div class="row-main"><h2 style="margin:0">${esc(product.name)}</h2><small>${esc([product.brand, product.category].filter(Boolean).join(' · ') || 'Eigenes Produkt')}</small></div>${expiryBadge(product.expires_on)}</div>
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:10px 0">
              <small>Geöffnet<br><b>${dateOnly(product.opened_on)}</b></small>
              <small>Haltbar bis<br><b>${dateOnly(product.expires_on)}</b></small>
            </div>
            ${product.notes ? `<p>${esc(product.notes)}</p>` : ''}
            <div class="actions"><button class="btn ghost" type="button" data-p2-archive="${product.id}" data-archived="${product.archived ? '1' : '0'}">${product.archived ? 'Reaktivieren' : 'Archivieren'}</button><button class="btn ghost" type="button" data-p2-delete-product="${product.id}">Löschen</button></div>
            <div class="separator"></div>
            <h3>Routine</h3>
            ${product.routines.length ? product.routines.map(step => `<div class="row" style="margin:8px 0"><div class="row-main"><b>${esc(step.period_label)}</b><small>${esc(step.note || (step.weekdays.length ? 'Wochentage: ' + step.weekdays.map(n => ['Mo','Di','Mi','Do','Fr','Sa','So'][n]).join(', ') : 'Persönliche Routine'))}</small></div><button class="btn ghost" type="button" data-p2-toggle-routine="${step.id}">${step.active ? 'Aktiv' : 'Pausiert'}</button><button class="btn ghost" type="button" data-p2-delete-routine="${step.id}">×</button></div>`).join('') : '<p class="empty">Noch keine Routine.</p>'}
            ${product.archived ? '' : `<form class="form" data-p2-routine-form="${product.id}">
              <label>Zeit<select name="period">${data.periods.map(period => `<option value="${esc(period.value)}">${esc(period.label)}</option>`).join('')}</select></label>
              <label>Wochentage (optional)${weekdayOptions()}</label>
              <label>Eigene Notiz<input name="note" maxlength="300" placeholder="Optional"></label>
              <button class="btn primary" type="submit">Routine hinzufügen</button>
            </form>`}
          </section>`).join('') : '<section class="card"><p class="empty">Noch keine Produkte im Beauty Cabinet.</p></section>'}`;
      bindBack();

      target.querySelector('#p2-cabinet-form')?.addEventListener('submit', async event => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        try {
          await p2Api('/cabinet/', { method: 'POST', body: JSON.stringify(Object.fromEntries(form.entries())) });
          await showCabinet();
        } catch (error) { alert(error.message); }
      });
      target.querySelectorAll('[data-p2-routine-form]').forEach(form => form.addEventListener('submit', async event => {
        event.preventDefault();
        const values = new FormData(event.currentTarget);
        const weekdays = values.getAll('weekday').map(Number);
        try {
          await p2Api(`/cabinet/${event.currentTarget.dataset.p2RoutineForm}/routine/`, { method: 'POST', body: JSON.stringify({ period: values.get('period'), weekdays, note: values.get('note') }) });
          await showCabinet();
        } catch (error) { alert(error.message); }
      }));
      target.querySelectorAll('[data-p2-archive]').forEach(button => button.addEventListener('click', async () => {
        try {
          await p2Api(`/cabinet/${button.dataset.p2Archive}/archive/`, { method: 'POST', body: JSON.stringify({ archived: button.dataset.archived !== '1' }) });
          await showCabinet();
        } catch (error) { alert(error.message); }
      }));
      target.querySelectorAll('[data-p2-delete-product]').forEach(button => button.addEventListener('click', async () => {
        if (!confirm('Produkt und zugehörige Routine-Schritte löschen?')) return;
        try { await p2Api(`/cabinet/${button.dataset.p2DeleteProduct}/delete/`, { method: 'DELETE' }); await showCabinet(); }
        catch (error) { alert(error.message); }
      }));
      target.querySelectorAll('[data-p2-toggle-routine]').forEach(button => button.addEventListener('click', async () => {
        try { await p2Api(`/cabinet/routine/${button.dataset.p2ToggleRoutine}/toggle/`, { method: 'POST', body: '{}' }); await showCabinet(); }
        catch (error) { alert(error.message); }
      }));
      target.querySelectorAll('[data-p2-delete-routine]').forEach(button => button.addEventListener('click', async () => {
        try { await p2Api(`/cabinet/routine/${button.dataset.p2DeleteRoutine}/delete/`, { method: 'DELETE' }); await showCabinet(); }
        catch (error) { alert(error.message); }
      }));
    } catch (error) { p2Fail(error, showCabinet); }
  }

  function cartTotal(productsById) {
    let total = 0;
    cart.forEach((quantity, id) => {
      const product = productsById.get(Number(id));
      if (product) total += product.price_cents * quantity;
    });
    return total;
  }

  function cartMarkup(products) {
    const productsById = new Map(products.map(product => [Number(product.id), product]));
    const entries = [...cart.entries()].filter(([id]) => productsById.has(Number(id)) && cart.get(id) > 0);
    if (!entries.length) return '<p class="empty">Ihr Warenkorb ist leer.</p>';
    return `${entries.map(([id, quantity]) => {
      const product = productsById.get(Number(id));
      return `<div class="row" style="margin:8px 0"><div class="row-main"><b>${esc(product.name)}</b><small>${quantity} × ${euro(product.price_cents)}</small></div><button class="btn ghost" type="button" data-p2-cart-minus="${product.id}">−</button><b>${quantity}</b><button class="btn ghost" type="button" data-p2-cart-plus="${product.id}">+</button></div>`;
    }).join('')}<div class="separator"></div><div class="row"><b>Gesamt</b><b>${euro(cartTotal(productsById))}</b></div>`;
  }

  async function showShop() {
    if (!p2Loading('A+ Auswahl', 'Shop', 'Produkte bestellen, Abholung oder Versand wählen und Status verfolgen.')) return;
    try {
      const data = await p2Api('/shop/');
      const target = content();
      const productsById = new Map(data.products.map(product => [Number(product.id), product]));
      target.innerHTML = `${backMarkup('A+ Auswahl', 'Shop', 'Produkte bestellen, Abholung oder Versand wählen und Status verfolgen.')}
        <div class="notice">${esc(data.payment_note)}</div>
        <section class="card"><h2>Produkte</h2>
          ${data.products.length ? data.products.map(product => `
            <div class="separator"></div><div class="row" style="align-items:flex-start">
              ${product.image_url ? `<img src="${esc(product.image_url)}" alt="" style="width:70px;height:70px;object-fit:cover;border-radius:14px;background:#eee">` : ''}
              <div class="row-main"><b>${esc(product.name)}</b><small>${esc(product.category || '')}</small><p style="margin:6px 0">${esc(product.description || '')}</p><b>${euro(product.price_cents)}</b><small style="display:block">${product.stock_quantity} verfügbar · ${[product.allow_collect ? 'Abholung' : '', product.allow_shipping ? 'Versand' : ''].filter(Boolean).join(' / ')}</small></div>
              <div style="display:flex;flex-direction:column;gap:6px"><button class="btn primary" type="button" data-p2-cart-add="${product.id}" ${product.in_stock ? '' : 'disabled'}>${product.in_stock ? '+ Warenkorb' : 'Ausverkauft'}</button><button class="btn ghost" type="button" data-p2-cabinet-shop="${product.id}">+ Cabinet</button></div>
            </div>`).join('') : '<p class="empty">Aktuell sind noch keine Shop-Produkte veröffentlicht.</p>'}
        </section>
        <section class="card"><h2>Warenkorb</h2><div data-p2-cart>${cartMarkup(data.products)}</div>
          <form id="p2-checkout" class="form" style="margin-top:14px">
            <label>Lieferart<select name="delivery_method"><option value="collect">Click & Collect</option><option value="shipping">Versand</option></select></label>
            <label>Name für Versand<input name="shipping_name" maxlength="160"></label>
            <label>Lieferadresse<textarea name="shipping_address" rows="3" maxlength="3000" placeholder="Nur bei Versand erforderlich"></textarea></label>
            <label>Notiz<textarea name="customer_note" rows="2" maxlength="3000"></textarea></label>
            <button class="btn primary" type="submit" ${cart.size ? '' : 'disabled'}>Bestellung absenden</button>
          </form>
        </section>
        <section class="card"><h2>Meine Bestellungen</h2>
          ${data.orders.length ? data.orders.map(order => `
            <div class="separator"></div><div class="row"><div class="row-main"><b>${esc(order.order_number)}</b><small>${dateTime(order.created_at)} · ${esc(order.delivery_label)}</small></div><span class="badge">${esc(order.status_label)}</span></div>
            <div style="margin:8px 0">${order.items.map(item => `<small style="display:block">${item.quantity} × ${esc(item.product_name)} · ${euro(item.line_total_cents)}</small>`).join('')}</div>
            <div class="row"><b>${euro(order.total_cents)}</b>${order.can_cancel ? `<button class="btn ghost" type="button" data-p2-cancel-order="${order.id}">Stornieren</button>` : ''}</div>
            ${order.events.length ? `<div style="margin-top:8px">${order.events.map(event => `<small style="display:block">${dateTime(event.created_at)} · ${esc(event.status_label)}${event.note ? ' · ' + esc(event.note) : ''}</small>`).join('')}</div>` : ''}`
          ).join('') : '<p class="empty">Noch keine Bestellung.</p>'}
        </section>`;
      bindBack();

      const rerenderCart = () => {
        const node = target.querySelector('[data-p2-cart]');
        if (node) node.innerHTML = cartMarkup(data.products);
        const submit = target.querySelector('#p2-checkout button[type="submit"]');
        if (submit) submit.disabled = ![...cart.values()].some(quantity => quantity > 0);
        bindCartControls();
      };
      const bindCartControls = () => {
        target.querySelectorAll('[data-p2-cart-minus]').forEach(button => button.onclick = () => {
          const id = Number(button.dataset.p2CartMinus);
          const next = Math.max(0, (cart.get(id) || 0) - 1);
          if (next) cart.set(id, next); else cart.delete(id);
          rerenderCart();
        });
        target.querySelectorAll('[data-p2-cart-plus]').forEach(button => button.onclick = () => {
          const id = Number(button.dataset.p2CartPlus);
          const product = productsById.get(id);
          if (!product) return;
          cart.set(id, Math.min(product.stock_quantity, (cart.get(id) || 0) + 1));
          rerenderCart();
        });
      };
      bindCartControls();

      target.querySelectorAll('[data-p2-cart-add]').forEach(button => button.addEventListener('click', () => {
        const id = Number(button.dataset.p2CartAdd);
        const product = productsById.get(id);
        if (!product) return;
        cart.set(id, Math.min(product.stock_quantity, (cart.get(id) || 0) + 1));
        rerenderCart();
      }));
      target.querySelectorAll('[data-p2-cabinet-shop]').forEach(button => button.addEventListener('click', async () => {
        try {
          await p2Api('/cabinet/', { method: 'POST', body: JSON.stringify({ shop_product_id: Number(button.dataset.p2CabinetShop) }) });
          alert('Produkt wurde zum Beauty Cabinet hinzugefügt.');
        } catch (error) { alert(error.message); }
      }));
      target.querySelector('#p2-checkout')?.addEventListener('submit', async event => {
        event.preventDefault();
        const values = new FormData(event.currentTarget);
        const items = [...cart.entries()].filter(([, quantity]) => quantity > 0).map(([product_id, quantity]) => ({ product_id: Number(product_id), quantity }));
        try {
          const result = await p2Api('/shop/orders/', { method: 'POST', body: JSON.stringify({
            items,
            delivery_method: values.get('delivery_method'),
            shipping_name: values.get('shipping_name'),
            shipping_address: values.get('shipping_address'),
            customer_note: values.get('customer_note'),
          }) });
          cart.clear();
          alert(`Bestellung ${result.order.order_number} wurde erfasst.`);
          await showShop();
        } catch (error) { alert(error.message); }
      });
      target.querySelectorAll('[data-p2-cancel-order]').forEach(button => button.addEventListener('click', async () => {
        if (!confirm('Diese Bestellung stornieren?')) return;
        try { await p2Api(`/shop/orders/${button.dataset.p2CancelOrder}/cancel/`, { method: 'POST', body: '{}' }); await showShop(); }
        catch (error) { alert(error.message); }
      }));
    } catch (error) { p2Fail(error, showShop); }
  }

  function enhanceMore() {
    const heading = [...document.querySelectorAll('.pagehead h1')].find(node => node.textContent.trim() === 'Mehr');
    if (!heading) return;
    const grid = heading.closest('.content')?.querySelector('.more-grid');
    if (!grid || grid.querySelector('[data-p2-route]')) return;
    const items = [
      ['wallet', '◆ Mitgliedskarte'],
      ['cabinet', '◈ Beauty Cabinet'],
      ['shop', '◉ Shop'],
    ];
    items.forEach(([route, label]) => {
      const button = document.createElement('button');
      button.className = 'more-item';
      button.type = 'button';
      button.dataset.p2Route = route;
      button.textContent = label;
      grid.appendChild(button);
    });
    grid.querySelector('[data-p2-route="wallet"]')?.addEventListener('click', showWallet);
    grid.querySelector('[data-p2-route="cabinet"]')?.addEventListener('click', showCabinet);
    grid.querySelector('[data-p2-route="shop"]')?.addEventListener('click', showShop);
  }

  const observer = new MutationObserver(enhanceMore);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', enhanceMore);
})();
