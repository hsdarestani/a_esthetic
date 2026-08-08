#!/usr/bin/env python3
from pathlib import Path
import sys

# A+ Esthetic is a customer club / loyalty app. Validate only customer/store-facing
# metadata and local native UI. Internal compliance documentation may explicitly
# discuss excluded categories and therefore must not be scanned as product copy.
FILES = [
    Path('capacitor.config.json'),
    Path('manifest.json'),
    Path('www/index.html'),
    Path('www/app.js'),
    Path('store/metadata.de.json'),
]
FORBIDDEN_LABELS = {
    'medical app', 'medical-app', 'health app', 'health-app',
    'diagnose-app', 'therapie-app', 'gesundheits-app', 'gesundheitsapp',
    'healthcare app', 'clinical decision', 'behandlungsempfehlungs-app',
}

bad = []
for path in FILES:
    if not path.exists():
        continue
    text = path.read_text(encoding='utf-8').lower()
    for term in FORBIDDEN_LABELS:
        if term in text:
            bad.append(f'{path}: {term}')

if bad:
    print('Store positioning check failed:')
    for item in bad:
        print(f' - {item}')
    sys.exit(1)

print('Store positioning check passed: A+ Esthetic is described as a customer club / loyalty app.')
