import base64
import json
import mimetypes
import re
import socket
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from p0_app.push import create_notification

from . import mobile_api
from .models import AuditLog, UserProfile
from .patient_sync import _token

BOOK_BASE = "https://book.a-esthetic.de"
BOOK_INGEST_URL = f"{BOOK_BASE}/api/internal/patient-records/ingest/"
BOOK_LIST_URL = f"{BOOK_BASE}/api/internal/patient-records/portal/list/"
BOOK_FILE_URL = f"{BOOK_BASE}/api/internal/patient-records/portal/file/"
BOOK_ARCHIVE_URL = f"{BOOK_BASE}/api/internal/patient-records/portal/archive/"
BOOK_HOST = "book.a-esthetic.de"
MAX_CUSTOMER_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
    ".doc", ".docx", ".xls", ".xlsx", ".txt", ".rtf", ".csv",
}
ALLOWED_KINDS = {"photo", "form", "document", "note", "other"}


def _identity(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return {
        "email": (user.email or "").strip().lower(),
        "phone": profile.phone,
        "first_name": (user.first_name or "").strip(),
        "last_name": (user.last_name or "").strip(),
        "full_name": (user.get_full_name() or user.username).strip(),
    }


def _book_headers():
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "A+Esthetic-Customer-PatientPortal/1.0",
    }
    token = _token()
    if token:
        headers["X-Aesthetic-Patient-Sync"] = token
    return headers


def _book_json(url, payload, timeout=12):
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers=_book_headers(),
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            body = json.loads(raw or "{}")
            if not (200 <= response.status < 300) or body.get("ok") is not True:
                return None, body, response.status
            return body, None, response.status
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", "replace") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"error": "book_http_error"}
        return None, body, exc.code
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None, {"error": "patient_record_service_unavailable"}, 503


def _error_from_book(error, status):
    code = str((error or {}).get("error") or "patient_record_service_unavailable")
    safe_status = status if status in {400, 401, 403, 404, 409, 413} else 503
    return JsonResponse({"ok": False, "error": code}, status=safe_status)


def _book_binary(payload):
    request = Request(
        BOOK_FILE_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=_book_headers(),
    )
    try:
        with urlopen(request, timeout=20) as response:
            content = response.read(MAX_CUSTOMER_UPLOAD_BYTES * 3)
            return response.status, response.headers, content
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read()
    except (URLError, TimeoutError, OSError):
        return 503, {}, b""


def _filename_from_headers(headers, fallback="dokument"):
    disposition = str(headers.get("Content-Disposition") or "")
    match = re.search(r'filename="?([^";]+)', disposition, re.I)
    if match:
        return Path(match.group(1)).name[:180]
    value = str(headers.get("X-Aesthetic-File-Name") or "").strip()
    return Path(value or fallback).name[:180]


@csrf_exempt
@require_http_methods(["GET"])
def mobile_patient_records(request):
    user, error = mobile_api._auth(request)
    if error:
        return error
    profile, _ = UserProfile.objects.get_or_create(user=user)
    payload, book_error, status = _book_json(BOOK_LIST_URL, _identity(user))
    if not payload:
        return _error_from_book(book_error, status)
    return JsonResponse({
        "ok": True,
        "health_data_consent": profile.health_data_consent,
        "patient_found": payload.get("patient_found", False),
        "patient": payload.get("customer"),
        "records": payload.get("records", []),
        "upload": {
            "max_bytes": MAX_CUSTOMER_UPLOAD_BYTES,
            "max_mb": MAX_CUSTOMER_UPLOAD_BYTES // (1024 * 1024),
            "kinds": [
                {"value": "document", "label": "Dokument"},
                {"value": "photo", "label": "Foto"},
                {"value": "form", "label": "Formular"},
                {"value": "note", "label": "Notiz"},
                {"value": "other", "label": "Sonstiges"},
            ],
        },
    })


@csrf_exempt
@require_POST
def mobile_patient_record_upload(request):
    user, error = mobile_api._auth(request)
    if error:
        return error
    profile, _ = UserProfile.objects.get_or_create(user=user)

    consent_value = str(request.POST.get("health_data_consent") or "").strip().lower()
    if not profile.health_data_consent:
        if consent_value not in {"1", "true", "yes", "on"}:
            return JsonResponse({"ok": False, "error": "health_data_consent_required"}, status=409)
        profile.health_data_consent = True
        profile.save(update_fields=["health_data_consent"])
        AuditLog.objects.create(
            actor=user,
            action="Einwilligung Patientenakte",
            entity_type="UserProfile",
            entity_id=str(user.pk),
            metadata={"health_data_consent": True, "source": "patient_portal_upload"},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    kind = str(request.POST.get("kind") or "document").strip().lower()
    if kind not in ALLOWED_KINDS:
        return JsonResponse({"ok": False, "error": "invalid_kind"}, status=400)
    title = str(request.POST.get("title") or "").strip()[:180]
    note = str(request.POST.get("note") or "").strip()[:6000]
    uploaded = request.FILES.get("file")
    payload = {
        **_identity(user),
        "source": "a_esthetic_app_customer",
        "external_id": f"customer-upload:{user.pk}:{uuid.uuid4().hex}",
        "kind": kind,
        "title": title,
        "note": note,
        "captured_at": timezone.now().isoformat(),
        "metadata": {
            "document_type": "customer_upload",
            "customer_upload": True,
            "shared_with_customer": True,
            "health_data_consent": True,
        },
    }

    if uploaded:
        original_name = Path(uploaded.name or "datei").name[:255]
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            return JsonResponse({"ok": False, "error": "file_type"}, status=400)
        if uploaded.size <= 0:
            return JsonResponse({"ok": False, "error": "file_empty"}, status=400)
        if uploaded.size > MAX_CUSTOMER_UPLOAD_BYTES:
            return JsonResponse({"ok": False, "error": "file_size"}, status=413)
        content = uploaded.read(MAX_CUSTOMER_UPLOAD_BYTES + 1)
        if len(content) > MAX_CUSTOMER_UPLOAD_BYTES:
            return JsonResponse({"ok": False, "error": "file_size"}, status=413)
        payload.update({
            "file_base64": base64.b64encode(content).decode("ascii"),
            "original_name": original_name,
            "mime_type": (uploaded.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream")[:120],
        })
        if not payload["title"]:
            payload["title"] = Path(original_name).stem[:180] or "Dokument"
    elif not note:
        return JsonResponse({"ok": False, "error": "empty_record"}, status=400)
    elif not payload["title"]:
        payload["title"] = "Notiz"

    result, book_error, status = _book_json(BOOK_INGEST_URL, payload, timeout=25)
    if not result:
        return _error_from_book(book_error, status)

    AuditLog.objects.create(
        actor=user,
        action="Patientendokument hochgeladen",
        entity_type="PatientRecord",
        entity_id=str(result.get("record_id") or ""),
        metadata={"kind": kind, "title": payload["title"], "source": "customer"},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    create_notification(
        user,
        "Dokument gespeichert",
        f"{payload['title']} wurde sicher in Ihrer Patientenakte gespeichert.",
        category="general",
        deeplink="profile",
        data={"patient_record_id": result.get("record_id")},
        send_push=False,
    )
    return JsonResponse({"ok": True, "record_id": result.get("record_id"), "created": result.get("created", True)}, status=201)


@csrf_exempt
@require_http_methods(["GET"])
def mobile_patient_record_file(request, record_id):
    user, error = mobile_api._auth(request)
    if error:
        return error
    status, headers, content = _book_binary({
        **_identity(user),
        "record_id": str(record_id),
        "download": request.GET.get("download") == "1",
    })
    if status != 200:
        return JsonResponse({"ok": False, "error": "record_not_found" if status == 404 else "patient_record_service_unavailable"}, status=404 if status == 404 else 503)
    response = HttpResponse(content, content_type=headers.get("Content-Type") or "application/octet-stream")
    filename = _filename_from_headers(headers, str(record_id))
    disposition = "attachment" if request.GET.get("download") == "1" else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    return response


@csrf_exempt
@require_POST
def mobile_patient_record_archive(request, record_id):
    user, error = mobile_api._auth(request)
    if error:
        return error
    result, book_error, status = _book_json(BOOK_ARCHIVE_URL, {**_identity(user), "record_id": str(record_id)})
    if not result:
        return _error_from_book(book_error, status)
    AuditLog.objects.create(
        actor=user,
        action="Patientendokument aus Kundenansicht entfernt",
        entity_type="PatientRecord",
        entity_id=str(record_id),
        metadata={"retained_in_clinic_record": True},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"ok": True, "archived": True})


def _resolved_book_addresses():
    addresses = set()
    try:
        for info in socket.getaddrinfo(BOOK_HOST, 443, type=socket.SOCK_STREAM):
            addresses.add(str(info[4][0]).split("%", 1)[0])
    except socket.gaierror:
        pass
    return addresses


def _callback_candidates(request):
    values = []
    for key in ("HTTP_CF_CONNECTING_IP", "HTTP_X_REAL_IP", "REMOTE_ADDR"):
        if request.META.get(key):
            values.append(str(request.META[key]).strip())
    forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR") or "")
    values.extend(part.strip() for part in forwarded.split(",") if part.strip())
    return set(values)


def _book_callback_authorized(request):
    user_agent = str(request.headers.get("User-Agent") or "")
    if user_agent != "A+Esthetic-Book-PatientPortal/1.0":
        return False
    resolved = _resolved_book_addresses()
    return bool(resolved and (_callback_candidates(request) & resolved))


@csrf_exempt
@require_POST
def internal_patient_document_shared(request):
    if not _book_callback_authorized(request):
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)
    email = str(data.get("email") or "").strip().lower()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if not user:
        return JsonResponse({"ok": True, "recipient_found": False})
    title = str(data.get("title") or "Dokument")[:180]
    item = create_notification(
        user,
        "Neues Dokument in Ihrer Patientenakte",
        f"A+ Esthetic hat „{title}“ für Sie bereitgestellt.",
        category="general",
        deeplink="profile",
        data={"patient_record_id": str(data.get("record_id") or "")},
    )
    return JsonResponse({"ok": True, "recipient_found": True, "notification_id": item.pk, "push_result": item.push_result})
