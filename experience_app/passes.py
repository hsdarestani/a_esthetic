import hashlib
import json
import os
import subprocess
import tempfile
import time
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import jwt
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from platform_app.models import MemberAccount, WalletAccount

from .models import MemberPass


def _member_payload(user):
    member, _ = MemberAccount.objects.get_or_create(user=user)
    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    tier = member.tier.name if member.tier else "A+ Member"
    full_name = user.get_full_name() or user.email or user.username
    return member, wallet, tier, full_name


def _icon_bytes(size):
    image = Image.new("RGB", (size, size), "#17212a")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(size * 0.42))
    except OSError:
        font = ImageFont.load_default()
    text = "A+"
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (size - (bbox[2] - bbox[0])) / 2
    y = (size - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((x, y), text, fill="#e0c79f", font=font)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def build_apple_pass(user):
    required = ["APPLE_PASS_TYPE_ID", "APPLE_TEAM_ID", "APPLE_PASS_CERT_PATH", "APPLE_PASS_KEY_PATH", "APPLE_WWDR_CERT_PATH"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ImproperlyConfigured("Apple-Wallet-Konfiguration fehlt: " + ", ".join(missing))
    member, wallet, tier, full_name = _member_payload(user)
    record, _ = MemberPass.objects.get_or_create(user=user, provider="apple")
    pass_type = os.environ["APPLE_PASS_TYPE_ID"]
    web_service_url = os.environ.get("APPLE_PASS_WEB_SERVICE_URL", "https://esthetic.smarbiz.sbs/wallet/apple/")
    pass_json = {
        "formatVersion": 1,
        "passTypeIdentifier": pass_type,
        "serialNumber": record.serial_number,
        "teamIdentifier": os.environ["APPLE_TEAM_ID"],
        "organizationName": "A+ Esthetic",
        "description": "A+ Esthetic Mitgliedskarte",
        "logoText": "A+ Esthetic",
        "foregroundColor": "rgb(23, 33, 42)",
        "backgroundColor": "rgb(246, 241, 234)",
        "labelColor": "rgb(120, 92, 60)",
        "webServiceURL": web_service_url.rstrip("/"),
        "authenticationToken": member.qr_token,
        "barcode": {"format": "PKBarcodeFormatQR", "message": member.qr_token, "messageEncoding": "iso-8859-1", "altText": member.member_number},
        "storeCard": {
            "headerFields": [{"key": "tier", "label": "STATUS", "value": tier}],
            "primaryFields": [{"key": "name", "label": "MITGLIED", "value": full_name}],
            "secondaryFields": [
                {"key": "coins", "label": "A+ COINS", "value": wallet.coin_balance},
                {"key": "credit", "label": "A+ CREDIT", "value": wallet.balance_cents / 100, "currencyCode": "EUR"},
            ],
            "auxiliaryFields": [{"key": "number", "label": "MITGLIEDSNUMMER", "value": member.member_number}],
            "backFields": [
                {"key": "issuer", "label": "Herausgeber", "value": "A+ Esthetic"},
                {"key": "medical", "label": "Medizinischer Hinweis", "value": "Die Mitgliedskarte enthält keine medizinische Empfehlung und verarbeitet keine Arztvergütung."},
            ],
        },
    }
    files = {
        "pass.json": json.dumps(pass_json, ensure_ascii=False, separators=(",", ":")).encode(),
        "icon.png": _icon_bytes(29),
        "icon@2x.png": _icon_bytes(58),
        "logo.png": _icon_bytes(80),
        "logo@2x.png": _icon_bytes(160),
    }
    manifest = {name: hashlib.sha1(content).hexdigest() for name, content in files.items()}
    files["manifest.json"] = json.dumps(manifest, separators=(",", ":")).encode()
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        for name, content in files.items():
            (directory / name).write_bytes(content)
        signature = directory / "signature"
        command = [
            "openssl", "smime", "-binary", "-sign",
            "-certfile", os.environ["APPLE_WWDR_CERT_PATH"],
            "-signer", os.environ["APPLE_PASS_CERT_PATH"],
            "-inkey", os.environ["APPLE_PASS_KEY_PATH"],
            "-in", str(directory / "manifest.json"),
            "-out", str(signature),
            "-outform", "DER",
        ]
        subprocess.run(command, check=True, capture_output=True)
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for name in files:
                archive.write(directory / name, name)
            archive.write(signature, "signature")
        output.seek(0)
    record.status = "active"
    record.last_synced_at = timezone.now()
    record.last_error = ""
    record.save(update_fields=["status", "last_synced_at", "last_error", "updated_at"])
    return output


def google_save_url(user):
    required = ["GOOGLE_WALLET_ISSUER_ID", "GOOGLE_WALLET_SERVICE_ACCOUNT_JSON"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ImproperlyConfigured("Google-Wallet-Konfiguration fehlt: " + ", ".join(missing))
    credentials = json.loads(os.environ["GOOGLE_WALLET_SERVICE_ACCOUNT_JSON"])
    issuer_id = os.environ["GOOGLE_WALLET_ISSUER_ID"]
    member, wallet, tier, full_name = _member_payload(user)
    record, _ = MemberPass.objects.get_or_create(user=user, provider="google")
    class_id = f"{issuer_id}.a_plus_esthetic_member"
    object_id = f"{issuer_id}.{member.member_number.lower().replace('-', '_')}"
    payload = {
        "iss": credentials["client_email"],
        "aud": "google",
        "origins": ["https://esthetic.smarbiz.sbs"],
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {
            "loyaltyClasses": [{
                "id": class_id,
                "issuerName": "A+ Esthetic",
                "programName": "A+ Beauty Club",
                "programLogo": {"sourceUri": {"uri": "https://esthetic.smarbiz.sbs/static/icon-512.png"}, "contentDescription": {"defaultValue": {"language": "de", "value": "A+ Esthetic"}}},
                "reviewStatus": "UNDER_REVIEW",
            }],
            "loyaltyObjects": [{
                "id": object_id,
                "classId": class_id,
                "state": "ACTIVE",
                "accountId": member.member_number,
                "accountName": full_name,
                "loyaltyPoints": {"label": "A+ Coins", "balance": {"int": wallet.coin_balance}},
                "barcode": {"type": "QR_CODE", "value": member.qr_token, "alternateText": member.member_number},
                "textModulesData": [
                    {"header": "Status", "body": tier, "id": "tier"},
                    {"header": "A+ Credit", "body": f"{wallet.balance_cents / 100:.2f} €", "id": "credit"},
                    {"header": "Herausgeber", "body": "A+ Esthetic", "id": "issuer"},
                ],
            }],
        },
    }
    token = jwt.encode(payload, credentials["private_key"], algorithm="RS256")
    record.external_object_id = object_id
    record.status = "active"
    record.last_synced_at = timezone.now()
    record.last_error = ""
    record.save(update_fields=["external_object_id", "status", "last_synced_at", "last_error", "updated_at"])
    return "https://pay.google.com/gp/v/save/" + token
