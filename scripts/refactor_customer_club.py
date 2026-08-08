#!/usr/bin/env python3
from pathlib import Path
import re


def replace(path: str, old: str, new: str):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    if old not in text:
        return False
    p.write_text(text.replace(old, new), encoding='utf-8')
    return True


def regex_replace(path: str, pattern: str, replacement: str, flags=0):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    new, count = re.subn(pattern, replacement, text, flags=flags)
    if count:
        p.write_text(new, encoding='utf-8')
    return count

changed = []

# Store-facing navigation: customer club only.
base = Path('templates/base.html')
if base.exists():
    text = base.read_text(encoding='utf-8')
    original = text
    text = text.replace("{% if feature_modules.passport.enabled %}<a href=\"{% url 'passport' %}\">▤ <span>Beauty Passport</span></a>{% endif %}", '')
    text = text.replace("{% if feature_modules.ai.enabled %}<a href=\"{% url 'beauty_assistant' %}\">✦ <span>Wissensassistent</span></a>{% endif %}", '')
    text = re.sub(r'<div class="legal-note"><b>Medizinischer Hinweis</b>.*?</div>', '', text, flags=re.S)
    if text != original:
        base.write_text(text, encoding='utf-8'); changed.append(str(base))

# Remove unfinished third-party login buttons and medical positioning from login.
login = Path('templates/registration/login.html')
if login.exists():
    text = login.read_text(encoding='utf-8')
    original = text
    text = re.sub(r'<div class="social-grid">.*?</div>', '', text, flags=re.S)
    text = text.replace('Durch die Anmeldung akzeptieren Sie die Datenschutz- und Nutzungsbedingungen. Die App ersetzt keine ärztliche Beratung.', 'Durch die Anmeldung akzeptieren Sie die Datenschutz- und Nutzungsbedingungen.')
    if text != original:
        login.write_text(text, encoding='utf-8'); changed.append(str(login))

# Customer-facing copy.
app = Path('templates/app.html')
if app.exists():
    text = app.read_text(encoding='utf-8')
    original = text
    replacements = {
        'Termine, Mitgliedschaft, Wallet, Beauty Passport, Erinnerungen und sichere Kommunikation – ohne automatische medizinische Diagnose oder Behandlungsempfehlung.': 'Mitgliedschaft, Vorteile, Rewards, Termine, Erinnerungen und direkter Kundenservice – alles an einem Ort.',
        '<a class="btn ghost" href="{% url \'passport\' %}">Beauty Passport</a>': '<a class="btn ghost" href="{% url \'club\' %}">Club-Vorteile</a>',
        '<a href="{% url \'passport\' %}">Beauty Passport</a>': '<a href="{% url \'club\' %}">Club-Vorteile</a>',
        'Die Buchung ist eine organisatorische Anfrage. Medizinische Leistungen werden erst nach persönlicher ärztlicher Aufklärung bestätigt.': 'Die Buchung ist eine organisatorische Anfrage. Termine werden vom A+ Esthetic Team separat bestätigt.',
        'Coins werden erst nach einem verifizierten ersten Besuch vergeben und stehen nicht mit Arztvergütung in Verbindung.': 'Coins werden erst nach einem verifizierten ersten Besuch vergeben.',
        'Medizinische Leistungen sind als Reward technisch ausgeschlossen.': 'Rewards und Vorteile werden ausschließlich von A+ Esthetic definiert.',
        'Medizinische Inhalte werden als Einladung zur erneuten Beurteilung formuliert, nicht als Aufforderung zur Behandlung.': 'Persönliche Erinnerungen für Termine, Club-Aktionen und organisatorische Hinweise.',
        '<h2>Kein Notfallkanal</h2><p>Bei akuten oder schweren Beschwerden wenden Sie sich an den ärztlichen Bereitschaftsdienst oder den Notruf. Diese Funktion ist nicht zur Notfallbeurteilung bestimmt.</p>': '<h2>Kundenservice</h2><p>Nutzen Sie die Nachrichtenfunktion für Fragen zu Mitgliedschaft, Terminen, Rewards und Ihrem A+ Esthetic Konto.</p>',
        '<label class="checkline"><input type="checkbox" name="health_data_consent" {% if profile.health_data_consent %}checked{% endif %}><span>Zweckgebundene Verarbeitung besonderer Gesundheitsdaten</span></label>': '',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    if text != original:
        app.write_text(text, encoding='utf-8'); changed.append(str(app))

# Appointment form: organisation only; do not ask for a healthcare-specific acknowledgement.
forms = Path('platform_app/forms.py')
if forms.exists():
    text = forms.read_text(encoding='utf-8')
    original = text
    text = text.replace("fields=('service','staff','starts_at','notes_customer','consent_acknowledged')", "fields=('service','staff','starts_at','notes_customer')")
    text = text.replace(",'consent_acknowledged':'Ich bestätige, dass die Buchung keine medizinische Beratung oder Behandlungszusage darstellt.'", '')
    if text != original:
        forms.write_text(text, encoding='utf-8'); changed.append(str(forms))

# Keep legacy DB tables for migration safety, but remove medical-only features from the customer product.
views = Path('platform_app/views.py')
if views.exists():
    text = views.read_text(encoding='utf-8')
    original = text
    text = re.sub(
        r"@login_required\ndef beauty_assistant\(request\):.*?(?=@login_required\ndef booking\(request\):)",
        "@login_required\ndef beauty_assistant(request):\n    messages.info(request,'Diese Funktion gehört nicht zum A+ Esthetic Kundenclub.')\n    return redirect('dashboard')\n",
        text, flags=re.S)
    text = re.sub(
        r"@login_required\ndef passport\(request\):.*?(?=@login_required\ndef reminders\(request\):)",
        "@login_required\ndef passport(request):\n    messages.info(request,'Diese Funktion gehört nicht zum A+ Esthetic Kundenclub.')\n    return redirect('dashboard')\n",
        text, flags=re.S)
    text = text.replace("profile.health_data_consent=request.POST.get('health_data_consent')=='on'; ", '')
    if text != original:
        views.write_text(text, encoding='utf-8'); changed.append(str(views))

# Turn legacy modules off in seed data when their feature keys are present.
seed = Path('platform_app/management/commands/seed_platform.py')
if seed.exists():
    text = seed.read_text(encoding='utf-8')
    original = text
    # Works with common tuple/dict seed layouts without changing database schema.
    text = re.sub(r"(['\"](?:ai|passport)['\"].{0,220}?['\"]enabled['\"]\s*:\s*)True", r"\1False", text, flags=re.S)
    text = re.sub(r"(['\"](?:ai|passport)['\"].{0,220}?['\"]customer_visible['\"]\s*:\s*)True", r"\1False", text, flags=re.S)
    if text != original:
        seed.write_text(text, encoding='utf-8'); changed.append(str(seed))

print('Customer-club refactor complete.')
for path in changed:
    print(' -', path)
