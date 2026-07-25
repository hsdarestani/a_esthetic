import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from platform_app.models import IntegrationConfig, SyncEvent


@dataclass
class SyncResult:
    ok: bool
    data: object = None
    error: str = ""


class JsonRpcClient:
    def __init__(self, url, headers=None):
        self.url = url
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.counter = 0

    def call(self, method, params=None):
        self.counter += 1
        payload = {"jsonrpc": "2.0", "id": self.counter, "method": method, "params": params or []}
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=self.headers, method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
        if data.get("error"):
            raise RuntimeError(str(data["error"]))
        return data.get("result")


class SimplyBookClient:
    """Official SimplyBook JSON-RPC client. Credentials are server-side only."""

    def __init__(self):
        self.company = os.environ.get("SIMPLYBOOK_COMPANY")
        self.api_key = os.environ.get("SIMPLYBOOK_API_KEY")
        if not self.company or not self.api_key:
            raise ImproperlyConfigured("SimplyBook API credentials are missing")
        login = JsonRpcClient("https://user-api.simplybook.me/login")
        token = login.call("getToken", [self.company, self.api_key])
        self.client = JsonRpcClient(
            "https://user-api.simplybook.me/",
            headers={"X-Company-Login": self.company, "X-Token": token},
        )

    def services(self):
        return self.client.call("getEventList", [])

    def performers(self):
        return self.client.call("getUnitList", [True, True, [], ""])

    def available_times(self, from_date, to_date, event_id, unit_id=None, count=1):
        return self.client.call("getStartTimeMatrix", [str(from_date), str(to_date), event_id, unit_id, count])


class DoctolibPartnerClient:
    """Configurable OAuth2 client for an approved Doctolib Partner API contract. No scraping."""

    def __init__(self):
        self.base = os.environ.get("DOCTOLIB_API_BASE", "").rstrip("/")
        self.client_id = os.environ.get("DOCTOLIB_CLIENT_ID")
        self.client_secret = os.environ.get("DOCTOLIB_CLIENT_SECRET")
        self.token_url = os.environ.get("DOCTOLIB_TOKEN_URL", f"{self.base}/oauth/token" if self.base else "")
        if not all([self.base, self.client_id, self.client_secret, self.token_url]):
            raise ImproperlyConfigured("Doctolib Partner API credentials are missing")
        self.token = self._token()

    def _token(self):
        body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret}).encode()
        request = urllib.request.Request(self.token_url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
        return data["access_token"]

    def get(self, path, params=None):
        url = f"{self.base}/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)


def check_provider(provider):
    config, _ = IntegrationConfig.objects.get_or_create(provider=provider)
    try:
        if provider == "simplybook":
            client = SimplyBookClient()
            data = {"services": len(client.services() or []), "performers": len(client.performers() or [])}
        elif provider == "doctolib":
            client = DoctolibPartnerClient()
            health_path = os.environ.get("DOCTOLIB_HEALTH_PATH", "health")
            data = client.get(health_path)
        else:
            data = {"configured": True}
        config.status = "Konfiguriert und erreichbar"
        config.last_sync_at = timezone.now()
        config.save(update_fields=["status", "last_sync_at"])
        SyncEvent.objects.create(integration=config, direction="out", entity_type="connection_test", status="success", message=json.dumps(data, default=str)[:2000])
        return SyncResult(True, data=data)
    except Exception as exc:
        config.status = "Nicht bereit"
        config.save(update_fields=["status"])
        SyncEvent.objects.create(integration=config, direction="out", entity_type="connection_test", status="failed", message=str(exc)[:2000])
        return SyncResult(False, error=str(exc))
