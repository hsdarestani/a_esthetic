"""Browser regression and media capture on the synthetic loopback environment."""
import argparse
import json
import statistics
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

APP = 'http://127.0.0.1:5181'
BOOK = 'http://127.0.0.1:5182'
PASSWORD = 'Preview-only-2026!'


def login(page, role):
    page.goto(APP)
    page.get_by_label('E-Mail-Adresse').fill(role+'@example.test')
    page.get_by_label('Passwort',exact=True).fill(PASSWORD)
    page.get_by_role('button',name='Anmelden',exact=True).click()


def clock(page):
    return page.locator('[data-cal-date]').input_value()


def swipe(page, vertical=False, reverse=False):
    timeline = page.locator('[data-cal-scroll]')
    bounds = timeline.bounding_box()
    x, y = bounds['x']+bounds['width']*.55, bounds['y']+bounds['height']*.56
    session = page.context.new_cdp_session(page)
    session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for step in range(1,10):
        delta = step*15*(1 if reverse else -1)
        session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[
            {'x':x if vertical else x+delta,'y':y+delta if vertical else y}]})
    session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    session.detach()


def screenshot(page, out, name):
    if out:
        page.wait_for_timeout(400)
        page.screenshot(path=out/f'APlus-{name}.png',animations='disabled')


def buttons(page, label):
    return page.get_by_role('button',name=label,exact=True)


def run(browser, output):
    artifacts = {'viewports':[],'calendar':{}}
    context = browser.new_context(
        viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True,
        record_video_dir=str(output/'raw-video') if output else None,
        record_video_size={'width':390,'height':844} if output else None,
    )
    page = context.new_page()
    errors = []
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.route('**/*',lambda route: route.continue_() if route.request.url.startswith((APP,BOOK)) else route.abort())
    page.add_init_script("""
        window.calendarMetrics = [];
        window.addEventListener('aplus:calendar-ready', e => calendarMetrics.push(e.detail));
    """)
    page.goto(APP)
    form = page.locator('[data-login]')
    expect(form).to_be_visible()
    screenshot(page, output,'login')
    buttons(page,'Anmelden').click()
    expect(page.locator('#ma-email-error')).to_be_visible()
    form.get_by_label('E-Mail-Adresse').fill('admin@example.test')
    form.get_by_label('Passwort',exact=True).fill('wrong-password')
    buttons(page,'Passwort anzeigen').click()
    expect(form.locator('[name=password]')).to_have_attribute('type','text')
    buttons(page,'Passwort ausblenden').click()
    buttons(page,'Anmelden').click()
    expect(form.get_by_role('alert')).to_contain_text('nicht korrekt')
    expect(form.locator('[name=email]')).to_have_value('admin@example.test')
    expect(form.locator('[name=password]')).to_have_value('wrong-password')
    buttons(page,'Passwort vergessen?').click()
    buttons(page,'Link anfordern').click()
    expect(page.get_by_role('heading',name='E-Mail prüfen')).to_be_visible()
    screenshot(page, output,'recovery')
    buttons(page,'Zur Anmeldung').click()
    buttons(page,'Konto erstellen').click()
    screenshot(page, output,'registration')
    page.get_by_label('Anrede').select_option('divers')
    page.get_by_label('Vorname',exact=True).fill('Juno')
    page.get_by_label('Nachname',exact=True).fill('Voss')
    page.get_by_label('E-Mail-Adresse').fill('signup-qa@example.test')
    page.get_by_label('Mobilnummer').fill('+4915112345678')
    buttons(page,'Weiter').click()
    screenshot(page, output,'registration-password')
    page.get_by_label('Passwort',exact=True).fill(PASSWORD)
    page.get_by_label('Passwort bestätigen').fill('DifferentPreviewPwd1!')
    buttons(page,'Konto erstellen').click()
    expect(page.get_by_text('Die Passwörter stimmen nicht überein.')).to_be_visible()
    page.get_by_label('Passwort bestätigen').fill(PASSWORD)
    buttons(page,'Konto erstellen').click()
    expect(page.get_by_role('heading',name='Fast fertig')).to_be_visible()
    screenshot(page, output,'verification')
    buttons(page,'Abmelden').click()
    expect(form).to_be_visible()
    login(page,'admin')
    expect(page.get_by_role('heading',name='Hallo, Mara')).to_be_visible()
    screenshot(page, output,'dashboard')
    page.reload()
    expect(page.get_by_role('heading',name='Hallo, Mara')).to_be_visible()
    buttons(page,'Kalender').click()
    expect(page.locator('[data-cal-item^="appointment:"]').first).to_be_visible()
    screenshot(page, output,'calendar')
    initial = date.fromisoformat(clock(page))
    scroll = page.locator('[data-cal-scroll]')
    scroll.evaluate('(n) => n.scrollTop = 702')
    swipe(page)
    expect(page.locator('[data-cal-date]')).to_have_value(str(initial+timedelta(days=1)))
    assert abs(scroll.evaluate('(n) => n.scrollTop')-702) <= 3
    swipe(page,reverse=True)
    expect(page.locator('[data-cal-date]')).to_have_value(str(initial))
    swipe(page,vertical=True)
    expect(page.locator('[data-cal-date]')).to_have_value(str(initial))
    assert scroll.evaluate('(n) => n.scrollTop') > 715
    scroll.evaluate('(n) => n.scrollTop = 667')
    page.get_by_label('Kalenderansicht').select_option('week')
    expect(page.locator('[data-cal-columns] > span')).to_have_count(3)
    swipe(page)
    expect(page.locator('[data-cal-date]')).to_have_value(str(initial+timedelta(days=1)))
    screenshot(page, output,'calendar-week')
    date_input = page.locator('[data-cal-date]')
    date_input.fill(f'{initial.year}-12-31')
    buttons(page,'Nächster Tag').click()
    expect(date_input).to_have_value(f'{initial.year+1}-01-01')
    expect(page.locator('[data-cal-month]')).to_contain_text('Januar')
    buttons(page,'Heute').click()
    page.evaluate("""() => {
        window.calendarFrames = [];
        let last = performance.now();
        const stop = last + 650;
        const sample = now => {
          calendarFrames.push(now-last);
          last = now;
          if (now < stop) requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
    }""")
    for direction in ('Nächster Tag','Vorheriger Tag') * 4:
        buttons(page,direction).click()
    expect(date_input).to_have_value(str(initial))
    for mode in ('provider','service'):
        page.get_by_label('Kalenderansicht').select_option(mode)
        expect(page.locator('[data-cal-columns] > span').first).to_be_visible()
        filter_box = page.locator('[data-cal-filter]')
        filter_box.select_option(index=1)
        expect(page.locator('[data-cal-columns] > span')).to_have_count(1)
    page.get_by_label('Kalenderansicht').select_option('day')
    network = page.context
    network.set_offline(True)
    date_input.fill(str(initial+timedelta(days=83)))
    expect(page.locator('[data-cal-status]')).to_contain_text('konnte nicht geladen werden')
    network.set_offline(False)
    expect(page.locator('[data-cal-status]')).to_be_hidden()
    buttons(page,'Heute').click()
    expect(page.locator('[data-cal-item^="appointment:"]').first).to_be_visible()
    page.locator('[data-cal-item^="appointment:"]').first.click()
    expect(page.get_by_role('dialog')).to_be_visible()
    screenshot(page, output,'appointment')
    buttons(page,'Schließen').click()
    buttons(page,'Kalendereintrag hinzufügen').click()
    page.get_by_role('button',name='Neuer Termin').click()
    page.get_by_label('Patient suchen').fill('Nora Berg')
    buttons(page,'Suchen').click()
    expect(page.locator('select[name=customer_id] option').first).to_contain_text('Nora Berg')
    page.get_by_label('Behandler',exact=True).select_option(label='Mara Winter')
    page.get_by_label('Behandlung',exact=True).select_option(label='Laser Haarentfernung')
    page.get_by_label('Beginn').fill('16:00')
    buttons(page,'Speichern').click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    scroll.evaluate('(n) => n.scrollTop=16*60*1.24-110')
    created = page.get_by_role('button',name='16:00 · Nora Berg · Laser Haarentfernung')
    expect(created).to_be_visible()
    created.click()
    buttons(page,'Termin bearbeiten').click()
    page.get_by_label('Beginn').fill('16:30')
    buttons(page,'Speichern').click()
    updated = page.get_by_role('button',name='16:30 · Nora Berg · Laser Haarentfernung')
    expect(updated).to_be_visible()
    updated.click()
    buttons(page,'Termin absagen').click()
    buttons(page,'Absage bestätigen').click()
    expect(updated).to_have_count(0)
    buttons(page,'Kalendereintrag hinzufügen').click()
    page.get_by_role('button',name='Notiz hinzufügen').click()
    page.get_by_label('Behandler',exact=True).select_option(label='Mara Winter')
    page.get_by_label('Beginn').fill('16:15')
    page.get_by_label('Ende',exact=True).fill('16:45')
    page.get_by_label('Notiz',exact=True).fill('Interne Testnotiz')
    buttons(page,'Speichern').click()
    expect(page.get_by_role('button',name='16:15 · Interne Testnotiz · Notiz')).to_be_visible()
    metrics = page.evaluate('calendarMetrics')
    frames = sorted(page.evaluate('calendarFrames').copy()[1:])
    artifacts['calendar'] = {
        'frame_samples':len(frames),
        'frame_p95_ms':round(frames[int(len(frames)*.95)-1],2),
        'warm_n':sum(m['cached'] for m in metrics),
        'warm_median_ms':round(statistics.median(m['milliseconds'] for m in metrics if m['cached']),2),
        'cold_median_ms':round(statistics.median(m['milliseconds'] for m in metrics if not m['cached']),2),
        'cold_n':sum(not m['cached'] for m in metrics),
    }
    buttons(page,'Mehr').click()
    page.get_by_role('button',name='Konto und Einstellungen').click()
    buttons(page,'Abmelden').click()
    expect(form).to_be_visible()
    login(page,'doctor')
    expect(page.get_by_text('Arztzugang',exact=True)).to_be_visible()
    expect(page.get_by_role('heading',name='Kalender')).to_be_visible()
    screenshot(page, output,'doctor-calendar')
    buttons(page,'Patienten').click()
    expect(page.get_by_role('button',name='Mila Stein',exact=False)).to_be_visible()
    expect(page.get_by_role('button',name='Nora Berg',exact=False)).to_have_count(0)
    page.get_by_role('button',name='Mila Stein',exact=False).click()
    expect(page.get_by_role('dialog').get_by_text('Erstgespräch')).to_be_visible()
    buttons(page,'Aktennotiz hinzufügen').click()
    page.get_by_label('Titel').fill('QA-Aktennotiz')
    page.get_by_label('Interne Notiz').fill('Synthetischer Inhalt')
    buttons(page,'Speichern').click()
    expect(page.get_by_role('dialog').get_by_text('QA-Aktennotiz')).to_be_visible()
    page.evaluate("localStorage.setItem('aplus_token','expired-fixture')")
    page.reload()
    expect(form).to_be_visible()
    login(page,'customer')
    expect(page.get_by_role('button',name='Startseite')).to_be_visible()
    assert page.locator('.mw').count() == 0
    assert not errors, errors
    if output:
        page.wait_for_timeout(350)
        video = page.video
        context.close()
        video.save_as(output/'APlus-mobile-demo.webm')
    else:
        context.close()
    for width,height in [(320,568),(360,800),(430,932),(820,1180)]:
        device = browser.new_page(viewport={'width':width,'height':height},has_touch=True,is_mobile=True)
        device.route('**/*',lambda route: route.continue_() if route.request.url.startswith((APP,BOOK)) else route.abort())
        login(device,'admin')
        expect(device.get_by_role('heading',name='Hallo, Mara')).to_be_visible()
        buttons(device,'Kalender').click()
        expect(device.locator('[data-cal-item^="appointment:"]').first).to_be_visible()
        assert device.evaluate('document.documentElement.scrollWidth <= innerWidth')
        artifacts['viewports'].append([width,height])
        device.close()
    return artifacts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--chromium')
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    if args.output:
        args.output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium,
                                             args=['--no-sandbox','--no-proxy-server','--disable-dev-shm-usage'])
        try:
            results = run(browser,args.output)
        finally:
            browser.close()
    print(json.dumps(results,ensure_ascii=False,indent=2))
