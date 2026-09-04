import base64
import json
import os
import time

from django.utils import timezone

from .ops_models import AppNotification, PushDevice


def _env_json(name, b64_name):
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        encoded = (os.environ.get(b64_name) or "").strip()
        if encoded:
            raw = base64.b64decode(encoded).decode("utf-8")
    return json.loads(raw) if raw else None


def _env_private_key(name, b64_name):
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        encoded = (os.environ.get(b64_name) or "").strip()
        if encoded:
            raw = base64.b64decode(encoded).decode("utf-8")
    return raw.replace("\\n", "\n") if raw else ""


def push_configuration():
    firebase = bool(
        (os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
        or (os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64") or "").strip()
    )
    apns = all([
        (os.environ.get("APNS_KEY_ID") or "").strip(),
        (os.environ.get("APNS_TEAM_ID") or "").strip(),
        _env_private_key("APNS_PRIVATE_KEY", "APNS_PRIVATE_KEY_B64"),
    ])
    return {"android": firebase, "ios": apns}


def _android_push(token, title, body, data):
    import requests
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    info = _env_json("FIREBASE_SERVICE_ACCOUNT_JSON", "FIREBASE_SERVICE_ACCOUNT_B64")
    if not info:
        raise RuntimeError("firebase_not_configured")
    project_id = info.get("project_id")
    if not project_id:
        raise RuntimeError("firebase_project_id_missing")
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"],
    )
    credentials.refresh(Request())
    message_data = {str(k): str(v) for k, v in (data or {}).items() if v is not None}
    response = requests.post(
        f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "message": {
                "token": token,
                "notification": {"title": title, "body": body},
                "data": message_data,
                "android": {"priority": "high"},
            }
        },
        timeout=20,
    )
    if not response.ok:
        error = RuntimeError(f"fcm_http_{response.status_code}:{response.text[:500]}")
        error.status_code = response.status_code
        raise error
    payload = response.json() if response.content else {}
    return {"ok": True, "provider": "fcm", "id": payload.get("name", "")}


def _ios_push(token, title, body, data):
    import httpx
    import jwt

    key_id = (os.environ.get("APNS_KEY_ID") or "").strip()
    team_id = (os.environ.get("APNS_TEAM_ID") or "").strip()
    private_key = _env_private_key("APNS_PRIVATE_KEY", "APNS_PRIVATE_KEY_B64")
    if not key_id or not team_id or not private_key:
        raise RuntimeError("apns_not_configured")

    auth_token = jwt.encode(
        {"iss": team_id, "iat": int(time.time())},
        private_key,
        algorithm="ES256",
        headers={"alg": "ES256", "kid": key_id},
    )
    environment = (os.environ.get("APNS_ENV") or "production").strip().lower()
    host = "https://api.sandbox.push.apple.com" if environment == "sandbox" else "https://api.push.apple.com"
    topic = (os.environ.get("APNS_BUNDLE_ID") or "de.aplusesthetic.app").strip()
    payload = {
        "aps": {
            "alert": {"title": title, "body": body},
            "sound": "default",
        },
        "data": data or {},
    }
    with httpx.Client(http2=True, timeout=20.0) as client:
        response = client.post(
            f"{host}/3/device/{token}",
            headers={
                "authorization": f"bearer {auth_token}",
                "apns-topic": topic,
                "apns-push-type": "alert",
                "apns-priority": "10",
            },
            json=payload,
        )
    if response.status_code != 200:
        error = RuntimeError(f"apns_http_{response.status_code}:{response.text[:500]}")
        error.status_code = response.status_code
        raise error
    return {"ok": True, "provider": "apns", "id": response.headers.get("apns-id", "")}


def deliver_notification(notification):
    devices = PushDevice.objects.filter(user=notification.user, enabled=True)
    results = []
    config = push_configuration()
    for device in devices:
        if not config.get(device.platform):
            results.append({"device": device.pk, "platform": device.platform, "ok": False, "error": "provider_not_configured"})
            continue
        try:
            data = {**(notification.data or {})}
            if notification.deeplink:
                data["deeplink"] = notification.deeplink
            data["notification_id"] = str(notification.pk)
            if device.platform == "android":
                result = _android_push(device.token, notification.title, notification.body, data)
            else:
                result = _ios_push(device.token, notification.title, notification.body, data)
            results.append({"device": device.pk, "platform": device.platform, **result})
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code in {400, 404, 410}:
                device.enabled = False
                device.save(update_fields=["enabled"])
            results.append({
                "device": device.pk,
                "platform": device.platform,
                "ok": False,
                "error": str(exc)[:500],
            })

    notification.push_attempted_at = timezone.now()
    notification.push_result = {"configured": config, "devices": results}
    notification.save(update_fields=["push_attempted_at", "push_result"])
    return notification.push_result


def create_notification(user, title, body="", category="general", deeplink="", data=None, send_push=True):
    item = AppNotification.objects.create(
        user=user,
        title=str(title)[:180],
        body=str(body)[:5000],
        category=category,
        deeplink=str(deeplink)[:240],
        data=data or {},
    )
    if send_push:
        deliver_notification(item)
    return item
