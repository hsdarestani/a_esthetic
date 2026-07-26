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


INK = "#111a22"
INK_2 = "#253642"
GOLD = "#c79a62"
GOLD_LIGHT = "#f0d7ad"
CREAM = "#f7f2ea"
WHITE = "#ffffff"


def _member_payload(user):
    member, _ = MemberAccount.objects.get_or_create(user=user)
    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    tier = member.tier.name if member.tier else "A+ Member"
    full_name = user.get_full_name() or user.email or user.username
    return member, wallet, tier, full_name


def _font(size, bold=False):
    names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _gradient(width, height, start=INK, end=INK_2):
    image = Image.new("RGB", (width, height), start)
    start_rgb = tuple(int(start[index:index + 2], 16) for index in (1, 3, 5))
    end_rgb = tuple(int(end[index:index + 2], 16) for index in (1, 3, 5))
    draw = ImageDraw.Draw(image)
    for x in range(width):
        ratio = x / max(width - 1, 1)
        color = tuple(round(a + (b - a) * ratio) for a, b in zip(start_rgb, end_rgb))
        draw.line((x, 0, x, height), fill=color)
    return image


def _icon_bytes(size):
    image = _gradient(size, size)
    draw = ImageDraw.Draw(image)
    inset = max(2, size // 16)
    draw.rounded_rectangle((inset, inset, size - inset, size - inset), radius=size // 4, outline=GOLD, width=max(1, size // 24))
    font = _font(max(10, int(size * 0.39)), bold=True)
    text = "A+"
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text(((size - (bbox[2] - bbox[0])) / 2, (size - (bbox[3] - bbox[1])) / 2 - bbox[1]), text, fill=GOLD_LIGHT, font=font)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _logo_bytes(width, height):
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    mark_size = min(height - 4, int(width * 0.22))
    draw.rounded_rectangle((2, 2, mark_size, height - 2), radius=max(5, height // 5), outline=GOLD_LIGHT, width=max(1, height // 22))
    mark_font = _font(max(12, int(height * 0.42)), bold=True)
    bbox = draw.textbbox((0, 0), "A+", font=mark_font)
    draw.text(((mark_size - (bbox[2] - bbox[0])) / 2 + 1, (height - (bbox[3] - bbox[1])) / 2 - bbox[1]), "A+", fill=GOLD_LIGHT, font=mark_font)
    word_font = _font(max(10, int(height * 0.25)), bold=True)
    draw.text((mark_size + height * 0.18, height * 0.22), "A+ ESTHETIC", fill=WHITE, font=word_font)
    small_font = _font(max(7, int(height * 0.14)))
    draw.text((mark_size + height * 0.18, height * 0.57), "BEAUTY CLUB", fill=GOLD_LIGHT, font=small_font)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _strip_bytes(width, height):
    image = _gradient(width, height)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((width * 0.66, -height * 0.8, width * 1.12, height * 1.5), fill=(199, 154, 98, 50))
    draw.ellipse((width * 0.77, -height * 0.55, width * 1.05, height * 1.15), outline=(240, 215, 173, 120), width=max(2, width // 180))
    draw.line((width * 0.08, height * 0.78, width * 0.52, height * 0.78), fill=(240, 215, 173, 110), width=max(1, width // 260))
    title_font = _font(max(20, int(height * 0.28)), bold=True)
    subtitle_font = _font(max(10, int(height * 0.13)))
    draw.text((width * 0.08, height * 0.21), "A+ BEAUTY CLUB", fill=WHITE, font=title_font)
    draw.text((width * 0.08, height * 0.56), "YOUR BEAUTY. YOUR BENEFITS.", fill=GOLD_LIGHT, font=subtitle_font)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def build_apple_pass(user):
    required = ["APPLE_PASS_TYPE_ID", "APPLE_TEAM_ID", "APPLE_PASS_CERT_PATH", "APPLE_PASS_KEY_PATH", "APPLE_WWDR_CERT_PATH"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ImproperlyConfigured("Apple-Wallet-Konfiguration fehlt: " + ", ".join(missing))

    member, wallet, tier, full_name = _member_payload(user)
    record, _ = MemberPass.objects.get_or_create(user=user, provider="apple")
    token = member.qr_token
    barcode = {
        "format": "PKBarcodeFormatQR",
        "message": token,
        "messageEncoding": "iso-8859-1",
        "altText": member.member_number,
    }
    pass_json = {
        "formatVersion": 1,
        "passTypeIdentifier": os.environ["APPLE_PASS_TYPE_ID"],
        "serialNumber": record.serial_number,
        "teamIdentifier": os.environ["APPLE_TEAM_ID"],
        "organizationName": "A+ Esthetic",
        "description": "A+ Esthetic Beauty Club Mitgliedskarte",
        "logoText": "A+ Esthetic",
        "foregroundColor": "rgb(255, 255, 255)",
        "backgroundColor": "rgb(17, 26, 34)",
        "labelColor": "rgb(240, 215, 173)",
        "barcode": barcode,
        "barcodes": [barcode],
        "userInfo": {"memberNumber": member.member_number, "tier": tier},
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
                {"key": "website", "label": "Website", "value": "https://a-esthetic.de"},
                {"key": "privacy", "label": "Datenschutz", "value": "Der QR-Code dient ausschließlich der sicheren Identifikation Ihrer A+ Mitgliedschaft."},
                {"key": "medical", "label": "Medizinischer Hinweis", "value": "Die Mitgliedskarte enthält keine medizinische Empfehlung und verarbeitet keine Arztvergütung."},
            ],
        },
    }

    service_url = os.environ.get("APPLE_PASS_WEB_SERVICE_URL", "").strip()
    if service_url:
        pass_json["webServiceURL"] = service_url.rstrip("/")
        pass_json["authenticationToken"] = token

    files = {
        "pass.json": json.dumps(pass_json, ensure_ascii=False, separators=(",", ":")).encode(),
        "icon.png": _icon_bytes(29),
        "icon@2x.png": _icon_bytes(58),
        "icon@3x.png": _icon_bytes(87),
        "logo.png": _logo_bytes(160, 50),
        "logo@2x.png": _logo_bytes(320, 100),
        "logo@3x.png": _logo_bytes(480, 150),
        "strip.png": _strip_bytes(375, 123),
        "strip@2x.png": _strip_bytes(750, 246),
        "strip@3x.png": _strip_bytes(1125, 369),
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
    signed_token = jwt.encode(payload, credentials["private_key"], algorithm="RS256")
    record.external_object_id = object_id
    record.status = "active"
    record.last_synced_at = timezone.now()
    record.last_error = ""
    record.save(update_fields=["external_object_id", "status", "last_synced_at", "last_error", "updated_at"])
    return "https://pay.google.com/gp/v/save/" + signed_token
