#!/usr/bin/env python3
from pathlib import Path
import re


def replace_once(path, old, new, label):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'{label}: expected source block not found in {path}')
    text = text.replace(old, new, 1)
    p.write_text(text, encoding='utf-8')
    print('patched', path, '-', label)


def regex_once(path, pattern, replacement, label):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f'{label}: expected one match in {path}, got {count}')
    p.write_text(new, encoding='utf-8')
    print('patched', path, '-', label)


# 1) Smooth route transitions: keep the current screen visible while the next API payload loads.
replace_once(
    'www/app.js',
    """  async function navigate(route) {\n    state.route = route;\n    await renderRoute();\n  }""",
    """  async function navigate(route) {\n    if (!route || route === state.route || document.body.classList.contains('route-transitioning')) return;\n    state.route = route;\n    document.body.classList.add('route-transitioning');\n    root.querySelectorAll('.nav [data-route]').forEach(button => {\n      button.classList.toggle('active', button.dataset.route === route);\n    });\n    try {\n      await renderRoute();\n    } finally {\n      requestAnimationFrame(() => document.body.classList.remove('route-transitioning'));\n    }\n  }""",
    'smooth navigate',
)

replace_once(
    'www/app.js',
    """  async function renderRoute() {\n    if (!state.token) return showLogin();\n    const titles = { home: 'Übersicht', club: 'Customer Club', booking: 'Termine', wallet: 'Wallet & Rewards', reminders: 'Erinnerungen', messages: 'Nachrichten', profile: 'Profil', more: 'Mehr' };\n    loading(titles[state.route] || 'A+ Esthetic');\n    try {""",
    """  async function renderRoute() {\n    if (!state.token) return showLogin();\n    try {""",
    'remove intermediate loading shell',
)

# shell() already binds navigation. These two extra bindings caused duplicate route requests.
replace_once(
    'www/app.js',
    """    `, 'home');\n    bindShell();\n  }\n\n  async function renderClub()""",
    """    `, 'home');\n  }\n\n  async function renderClub()""",
    'remove duplicate home bindings',
)
replace_once(
    'www/app.js',
    """    `, 'more');\n    root.querySelectorAll('[data-route]').forEach((button) => button.addEventListener('click', () => navigate(button.dataset.route)));\n    document.getElementById('logout')?.addEventListener('click', () => logout());""",
    """    `, 'more');\n    document.getElementById('logout')?.addEventListener('click', () => logout());""",
    'remove duplicate more bindings',
)

# 2) Booking screen: no staff picker, and no raw datetime-local control.
booking_pattern = r"  async function renderBooking\(\) \{.*?\n  \}\n\n  async function renderWallet\(\) \{"
booking_replacement = r'''  async function renderBooking() {
    const data = await api('/booking/');
    shell(`
      <div class="pagehead"><span>Organisation</span><h1>Termine</h1><p>Terminart auswählen und anschließend bequem eine freie Zeit wählen.</p></div>
      <section class="card booking-request-card">
        <h2>Neue Anfrage</h2>
        <form id="booking-form" class="form">
          <label>Terminart
            <select name="service_id" required>
              <option value="">Bitte wählen</option>
              ${data.services.map(s => `<option value="${s.id}">${esc(s.name)} · ${s.duration_minutes} Min.</option>`).join('')}
            </select>
          </label>
          <div class="booking-picker-wrap">
            <span>Wunschtermin</span>
            <input type="hidden" name="starts_at" required>
            <div data-booking-picker></div>
            <small class="booking-modern-note">Der passende Ansprechpartner aus dem A+ Team wird automatisch für Sie eingeplant.</small>
          </div>
          <button class="btn primary" type="submit" disabled>Terminanfrage senden</button>
        </form>
      </section>
      <section class="card"><h2>Ihre Termine</h2>${data.appointments.length ? data.appointments.map(a => `<div class="row"><div class="row-main"><b>${esc(a.service)}</b><small>${dateTime(a.starts_at)}</small></div><span class="badge">${esc(a.status)}</span></div>`).join('') : '<p class="empty">Noch keine Termine.</p>'}</section>
    `, 'booking');
    document.getElementById('booking-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const startsAt = String(form.get('starts_at') || '');
      if (!startsAt) {
        alert('Bitte wählen Sie eine freie Zeit.');
        return;
      }
      const payload = { service_id: Number(form.get('service_id')), starts_at: startsAt };
      const button = event.currentTarget.querySelector('button[type="submit"]');
      button.disabled = true;
      button.textContent = 'Wird gesendet…';
      try {
        await api('/booking/', { method: 'POST', body: JSON.stringify(payload) });
        alert('Terminanfrage wurde gespeichert.');
        await renderBooking();
      } catch (error) {
        alert(error.message);
        button.disabled = false;
        button.textContent = 'Terminanfrage senden';
      }
    });
  }

  async function renderWallet() {'''
regex_once('www/app.js', booking_pattern, booking_replacement, 'modern booking screen')

# 3) Slots API: staff is internal. Return the union of free times across all eligible A+ team members.
slots_pattern = r"@csrf_exempt\n@require_http_methods\(\[\"GET\"\]\)\ndef mobile_slots\(request\):.*?\n\n\n@csrf_exempt\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\ndef mobile_booking"
slots_replacement = r'''@csrf_exempt
@require_http_methods(["GET"])
def mobile_slots(request):
    user, error = _auth(request)
    if error:
        return error
    service = Service.objects.filter(
        pk=request.GET.get("service_id"),
        active=True,
        bookable_in_app=True,
    ).first()
    if not service:
        return JsonResponse({"ok": False, "error": "service_not_found"}, status=400)
    try:
        day = date.fromisoformat(str(request.GET.get("day") or ""))
    except ValueError:
        return JsonResponse({"ok": False, "error": "invalid_day"}, status=400)

    exclude_appointment_id = None
    raw_exclude = request.GET.get("exclude_appointment_id")
    if raw_exclude:
        owned = Appointment.objects.filter(pk=raw_exclude, user=user).first()
        if owned:
            exclude_appointment_id = owned.pk

    eligible = StaffMember.objects.filter(active=True, services=service).distinct().order_by("display_name")
    requested_staff_id = request.GET.get("staff_id")
    if requested_staff_id:
        eligible = eligible.filter(pk=requested_staff_id)
    if not eligible.exists():
        return JsonResponse({"ok": False, "error": "staff_not_found"}, status=400)

    unique_slots = set()
    for member in eligible:
        unique_slots.update(available_slots(
            service,
            member,
            day,
            exclude_appointment_id=exclude_appointment_id,
        ))

    slots = sorted(unique_slots)
    return JsonResponse({
        "ok": True,
        "service_id": service.pk,
        "day": day.isoformat(),
        "slots": [slot.isoformat() for slot in slots],
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_booking'''
regex_once('p0_app/views.py', slots_pattern, slots_replacement, 'aggregate staff availability')

# 4) Rescheduling also assigns the available A+ team member automatically.
reschedule_pattern = r'''        service = appointment\.service\n        eligible = StaffMember\.objects\.filter\(active=True, services=service\)\.distinct\(\)\.order_by\("display_name"\)\n        staff_id = data\.get\("staff_id"\) or appointment\.staff_id\n        staff = eligible\.filter\(pk=staff_id\)\.first\(\) if staff_id else None\n        if not staff:\n            return JsonResponse\(\{"ok": False, "error": "staff_not_found"\}, status=400\)\n\n        locked_staff = StaffMember\.objects\.select_for_update\(\)\.get\(pk=staff\.pk\)\n        local_day = starts_at\.astimezone\(timezone\.get_current_timezone\(\)\)\.date\(\)\n        if starts_at not in available_slots\(\n            service,\n            locked_staff,\n            local_day,\n            exclude_appointment_id=appointment\.pk,\n        \):\n            return JsonResponse\(\{"ok": False, "error": "time_not_available"\}, status=409\)'''
reschedule_replacement = '''        service = appointment.service
        eligible = StaffMember.objects.filter(active=True, services=service).distinct().order_by("display_name")
        requested_staff_id = data.get("staff_id")
        if requested_staff_id:
            eligible = eligible.filter(pk=requested_staff_id)

        local_day = starts_at.astimezone(timezone.get_current_timezone()).date()
        locked_staff = None
        for candidate in eligible:
            candidate_locked = StaffMember.objects.select_for_update().get(pk=candidate.pk)
            if starts_at in available_slots(
                service,
                candidate_locked,
                local_day,
                exclude_appointment_id=appointment.pk,
            ):
                locked_staff = candidate_locked
                break
        if not locked_staff:
            return JsonResponse({"ok": False, "error": "time_not_available"}, status=409)'''
regex_once('p0_app/appointment_views.py', reschedule_pattern, reschedule_replacement, 'automatic staff on reschedule')

# 5) Reschedule editor uses the same modern picker and no Ansprechpartner field.
editor_pattern = r"  function buildRescheduleEditor\(appointment, staffOptions, container\) \{.*?\n  \}\n\n  async function enhanceBookingManagement\(\) \{"
editor_replacement = r'''  function buildRescheduleEditor(appointment, staffOptions, container) {
    container.innerHTML = '';
    const editor = document.createElement('div');
    editor.className = 'form reschedule-modern';
    editor.innerHTML = `
      <div data-reschedule-picker></div>
      <div class="actions">
        <button class="btn primary" type="button" data-save-reschedule disabled>Umbuchung speichern</button>
        <button class="btn ghost" type="button" data-close-reschedule>Abbrechen</button>
      </div>`;
    container.appendChild(editor);

    const save = editor.querySelector('[data-save-reschedule]');
    let selectedSlot = '';
    const host = editor.querySelector('[data-reschedule-picker]');
    if (!window.APlusBookingPicker) {
      host.innerHTML = '<div class="notice">Die Terminauswahl konnte nicht geladen werden. Bitte öffnen Sie die Seite erneut.</div>';
      return;
    }

    window.APlusBookingPicker.mountStandalone(host, {
      serviceId: appointment.service_id,
      excludeAppointmentId: appointment.id,
      onSelect: value => {
        selectedSlot = value || '';
        save.disabled = !selectedSlot;
      },
    });

    editor.querySelector('[data-close-reschedule]').addEventListener('click', () => { container.innerHTML = ''; });
    save.addEventListener('click', async () => {
      if (!selectedSlot) return;
      save.disabled = true;
      save.textContent = 'Wird gespeichert…';
      try {
        await api(`/booking/${appointment.id}/change/`, {
          method: 'POST',
          body: JSON.stringify({ action: 'reschedule', starts_at: selectedSlot }),
        });
        refreshBooking();
      } catch (error) {
        alert(errorText(error.message));
        save.disabled = false;
        save.textContent = 'Umbuchung speichern';
      }
    });
  }

  async function enhanceBookingManagement() {'''
regex_once('www/p0-booking-change.js', editor_pattern, editor_replacement, 'modern reschedule picker')

# Keep the management list customer-facing: staff assignment is internal.
p = Path('www/p0-booking-change.js')
text = p.read_text(encoding='utf-8')
text = text.replace("${esc(formatDateTime(appointment.starts_at))}${appointment.staff ? ` · ${esc(appointment.staff)}` : ''}", "${esc(formatDateTime(appointment.starts_at))}")
p.write_text(text, encoding='utf-8')

# 6) Production validation must know about the new release markers/assets.
workflow = Path('.github/workflows/deploy-customer-club-web.yml')
text = workflow.read_text(encoding='utf-8')
text = text.replace('for FILE in index.html app.css app.js p0.js p0-booking-change.js p1.js p2.js p3.js wow.js sw.js; do', 'for FILE in index.html app.css reference-ui.css booking-modern.css app.js booking-modern.js p0.js p0-booking-change.js p1.js p2.js p3.js sw.js; do')
text = text.replace("grep -q 'app.css?v=20260812-wow-v1' www/index.html", "grep -q 'booking-modern.css?v=20260816-booking-v1' www/index.html")
text = text.replace("grep -q 'wow.js?v=20260812-wow-v1' www/index.html", "grep -q 'booking-modern.js?v=20260816-booking-v1' www/index.html")
text = text.replace('node --check www/wow.js', 'node --check www/booking-modern.js\n          node --check www/reference-ui.js')
text = text.replace('for FILE in index.html app.css app.js p0.js p0-booking-change.js p1.js p2.js p3.js wow.js sw.js; do', 'for FILE in index.html app.css reference-ui.css booking-modern.css app.js booking-modern.js p0.js p0-booking-change.js p1.js p2.js p3.js sw.js; do')
text = text.replace('WOW_RELEASE_ID="20260812-wow-v1"', 'WOW_RELEASE_ID="20260816-booking-v1"')
text = text.replace('grep -q "app.css?v=$WOW_RELEASE_ID" "$RELEASE_DIR/index.html"', 'grep -q "booking-modern.css?v=$WOW_RELEASE_ID" "$RELEASE_DIR/index.html"')
text = text.replace('grep -q "wow.js?v=$WOW_RELEASE_ID" "$RELEASE_DIR/index.html"', 'grep -q "booking-modern.js?v=$WOW_RELEASE_ID" "$RELEASE_DIR/index.html"')
text = text.replace('grep -q "wow.js?v=$WOW_RELEASE_ID" "$WEBROOT/index.html"', 'grep -q "booking-modern.js?v=$WOW_RELEASE_ID" "$WEBROOT/index.html"')
text = text.replace('wow_marker = f\'wow.js?v={wow_release}\'', 'wow_marker = f\'booking-modern.js?v={wow_release}\'')
text = text.replace('css_marker = f\'app.css?v={wow_release}\'', 'css_marker = f\'booking-modern.css?v={wow_release}\'')
text = text.replace("assets = ('app.css','app.js','p0.js','p0-booking-change.js','p1.js','p2.js','p3.js','wow.js','sw.js')", "assets = ('app.css','reference-ui.css','booking-modern.css','app.js','booking-modern.js','p0.js','p0-booking-change.js','p1.js','p2.js','p3.js','sw.js')")
text = text.replace("css_status, css, _ = fetch(f'https://{domain}/app.css?v={wow_release}')", "css_status, css, _ = fetch(f'https://{domain}/booking-modern.css?v={wow_release}')")
text = text.replace("wow_status, wow, _ = fetch(f'https://{domain}/wow.js?v={wow_release}')", "wow_status, wow, _ = fetch(f'https://{domain}/booking-modern.js?v={wow_release}')")
text = text.replace("if css_status != 200 or 'dashboard-home' not in css or 'auth-showcase' not in css or 'feature-tile' not in css:", "if css_status != 200 or 'smart-picker' not in css or 'smart-time' not in css:")
text = text.replace("raise SystemExit('Public CSS is not the WOW redesign build.')", "raise SystemExit('Public CSS is not the modern booking build.')")
text = text.replace("if wow_status != 200 or 'featureMeta' not in wow or 'enhanceHome' not in wow or 'enhanceMore' not in wow:", "if wow_status != 200 or 'APlusBookingPicker' not in wow or 'fetchSlots' not in wow:")
text = text.replace("raise SystemExit('Public wow.js is stale or incomplete.')", "raise SystemExit('Public booking-modern.js is stale or incomplete.')")
workflow.write_text(text, encoding='utf-8')
print('patched deploy workflow markers')

print('Booking UX v1 patch complete.')
