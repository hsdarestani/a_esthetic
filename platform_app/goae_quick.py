"""Clinic-configured, versioned GOÄ draft templates for the private Book bridge."""
import json
import os
import re

from django.conf import settings

from .goae_tariff import CATALOG


def templates():
    configured = getattr(settings, 'GOAE_QUICK_TEMPLATES', None)
    if configured is None:
        try:
            configured = json.loads(os.getenv('GOAE_QUICK_TEMPLATES', '{}'))
        except ValueError:
            return {}
    if not isinstance(configured, dict):
        return {}
    return {
        key: item for key, item in configured.items()
        if isinstance(key, str) and isinstance(item, dict)
        and isinstance(item.get('label'), str) and item['label'].strip()
        and isinstance(item.get('version'), str) and item['version'].strip()
        and isinstance(item.get('approved_by'), str) and item['approved_by'].strip()
        and isinstance(item.get('lines'), list) and 1 <= len(item['lines']) <= 50
    }


def template_options():
    return {key: {'label': item['label'], 'version': item['version']}
            for key, item in templates().items()}


def draft_lines(plan):
    if not isinstance(plan, dict):
        raise ValueError('Ungültige Angaben für die Schnellrechnung.')
    key, version, scope = plan.get('treatment'), plan.get('version'), plan.get('quantity')
    template = templates().get(key) if isinstance(key, str) else None
    if template is None or template['version'] != version:
        raise ValueError('Keine gültige, freigegebene Vorlage vorhanden.')
    if type(scope) is not int or not 1 <= scope <= 100:
        raise ValueError('Bitte den Behandlungsumfang prüfen.')
    desired = plan.get('desired_cents')
    if type(desired) is not int or not 0 <= desired <= 100_000_000:
        raise ValueError('Bitte einen gültigen Wunschbetrag eingeben.')

    lines = []
    for rule in template['lines']:
        if not isinstance(rule, dict) or type(rule.get('quantity')) is not int or rule['quantity'] < 1:
            raise ValueError('GOÄ-Vorlage: Anzahl pro Position prüfen.')
        multiple = rule.get('per_unit', False)
        if type(multiple) is not bool:
            raise ValueError('GOÄ-Vorlage: Mengeneinstellung prüfen.')
        quantity = rule['quantity'] * (scope if multiple else 1)
        row = {'quantity': quantity, 'goae_vat_rate': rule.get('vat_rate')}
        if rule.get('kind') == 'material':
            desc = rule.get('description')
            if not isinstance(desc, str) or not 4 <= len(desc.strip()) <= 220:
                raise ValueError('GOÄ-Vorlage: Materialbezeichnung prüfen.')
            reference = rule.get('receipt_reference', '')
            if not isinstance(reference, str) or len(reference) > 250:
                raise ValueError('GOÄ-Vorlage: Belegreferenz prüfen.')
            row.update(kind='material', goae_description=desc,
                       goae_base_eur=rule.get('unit_cost_eur'),
                       material_receipt_reference=reference)
        else:
            code = str(rule.get('number') or '')
            factor = str(rule.get('factor') or '')
            if code not in CATALOG or not re.fullmatch(r'[0-9]+(?:[,.][0-9]{1,4})?', factor):
                raise ValueError('GOÄ-Vorlage: Amtliche Ziffer und Faktor prüfen.')
            row.update(kind='service', tariff_source='official_catalog',
                       goae_number=code, goae_factor=factor)
        lines.append(row)
    return lines, {'treatment': key, 'version': version, 'quantity': scope, 'desired_cents': desired}
