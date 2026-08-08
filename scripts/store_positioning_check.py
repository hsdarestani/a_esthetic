#!/usr/bin/env python3
from pathlib import Path
import sys

# A+ Esthetic is a customer club / loyalty app. Store-facing native metadata must
# never describe it as a medical, healthcare, diagnosis or treatment app.
FILES = [
    Path('capacitor.config.json'),
    Path('manifest.json'),
    Path('www/index.html'),
    Path('docs/STORE_RELEASE.md'),
]
FORBIDDEN = {
    'medical app', 'medical-app', 'health app', 'health-app',
    'diagnosis', 'diagnose', 'therapieempfehlung', 'behandlungsempfehlung',
    'gesundheits-app', 'gesundheitsapp', 'healthcare app',
}

bad = []
for path in FILES:
    if not path.exists():
        continue
    text = path.read_text(encoding='utf-8').lower()
    for term in FORBIDDEN:
        if term in text:
            bad.append(f'{path}: {term}')

if bad:
    print('Store positioning check failed:')
    for item in bad:
        print(f' - {item}')
    sys.exit(1)

print('Store positioning check passed: A+ Esthetic is described as a customer club / loyalty app.')
