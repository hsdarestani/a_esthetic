"""Read-only remote staging reachability gate for final Appetize builds.

Never probes live patient records or performs a state-changing operation.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from mobile_staff_preview import validate_public_origins


class StrictRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urlsplit(req.full_url)
        new = urlsplit(newurl)
        if new.scheme != "https" or new.hostname != old.hostname:
            raise ValueError("Staging redirected outside its own HTTPS hostname")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_origin(url: str) -> str:
    """Validate one remote app origin, including authentication-protected landing pages."""
    parsed = urlsplit(url)
    if parsed.hostname and (parsed.hostname.endswith(".test")
                             or parsed.hostname.endswith(".invalid")
                             or parsed.hostname.endswith(".example")):
        raise ValueError("Example/placeholder staging domains cannot be used in Appetize builds")
    opener = urllib.request.build_opener(StrictRedirects())
    request = urllib.request.Request(url + "/", method="GET",
                                     headers={"User-Agent": "APlus-Staging-Readiness/1.0"})
    try:
        response = opener.open(request, timeout=12)
        code = response.status
        effective = response.geturl()
        response.close()
    except urllib.error.HTTPError as error:
        code = error.code
        effective = error.geturl()
        error.close()
    actual = urlsplit(effective)
    if actual.scheme != "https" or actual.hostname != parsed.hostname:
        raise ValueError("Staging response resolved to a different or insecure host")
    if code not in (200, 401, 403):
        raise ValueError(f"Staging origin did not respond as expected: HTTP {code}")
    return f"{parsed.hostname}: HTTP {code}"


def main() -> int:
    app, book, remote = validate_public_origins(
        os.environ.get("STAGING_APP_URL"), os.environ.get("STAGING_BOOK_URL")
    )
    if not remote:
        raise ValueError("Only explicitly configured remote staging is accepted")
    for url in (app, book):
        print("Stage origin reachable:", check_origin(url))
    print("Staging host reachability verified; endpoint/role E2E QA is STILL required")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, urllib.error.URLError) as exc:
        print(f"STAGING PREFLIGHT FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
