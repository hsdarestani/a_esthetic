#!/usr/bin/env python3
"""Fail native store builds if A+ Esthetic includes a stale production hostname."""
from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "www"
CANONICAL = "https://app.a-esthetic.de"
RETIRED = "esthetic.smarbiz.sbs"
MODULES = (
    "core-app.js",
    "account-onboarding.js",
    "booking-direct-api.js",
    "admin-mode.js",
    "booking-consent-bridge.js",
    "booking-book-flow.js",
    "focused-upgrade.js",
    "apple-wallet-native.js",
    "native-push.js",
    "native-interactions.js",
    "customer-dashboard-v3.js",
)


class AppReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        candidate = props.get("src") if tag == "script" else props.get("href") if tag == "link" else None
        if candidate and candidate.startswith("./"):
            self.assets.append(candidate)


def check():
    errors = []
    for item in WEB.rglob("*"):
        if item.is_file() and item.suffix.lower() in {".js", ".html", ".css", ".json"}:
            body = item.read_text(encoding="utf-8")
            if RETIRED in body:
                errors.append(f"Retired host found in packaged asset: {item.relative_to(ROOT)}")

    for name in MODULES:
        body = (WEB / name).read_text(encoding="utf-8")
        if f"const APP_ORIGIN = '{CANONICAL}';" not in body:
            errors.append(f"Wrong mobile origin: {name}")

    core = (WEB / "core-app.js").read_text(encoding="utf-8")
    if 'data-forgot-password href="${APP_ORIGIN}/accounts/password/reset/"' not in core:
        errors.append("Missing canonical password reset link")
    onboarding = (WEB / "account-onboarding.js").read_text(encoding="utf-8")
    if "${APP_ORIGIN}/accounts/${provider}/login/" not in onboarding:
        errors.append("Native OAuth browser flow missing canonical origin")
    if "de.aplusesthetic.app:" not in onboarding:
        errors.append("Native OAuth return deep link is missing")

    cap = json.loads((ROOT / "capacitor.config.json").read_text(encoding="utf-8"))
    if cap.get("appId") != "de.aplusesthetic.app":
        errors.append("Native bundle ID mismatch")
    navigation = cap.get("server", {}).get("allowNavigation", [])
    if "app.a-esthetic.de" not in navigation or "book.a-esthetic.de" not in navigation:
        errors.append("Canonical app and booking hosts missing from native navigation allowlist")
    if RETIRED in json.dumps(cap):
        errors.append("Retired host in Capacitor config")

    index = (WEB / "index.html").read_text(encoding="utf-8")
    parser = AppReferences()
    parser.feed(index)
    for ref in parser.assets:
        local_path = urlsplit(ref).path.removeprefix("./")
        if not (WEB / local_path).is_file():
            errors.append(f"Missing bundled script or stylesheet: {ref}")
    for name in ("core-app.js", "account-onboarding.js", "booking-direct-api.js"):
        if not any(name in ref for ref in parser.assets):
            errors.append(f"Missing essential native script tag: {name}")

    if errors:
        raise SystemExit("\n".join("FAIL " + err for err in errors))
    print(f"PASS: canonical host {CANONICAL}, {len(MODULES)} mobile modules, "
          f"{len(parser.assets)} local assets, password recovery, OAuth, Capacitor routing")


if __name__ == "__main__":
    check()
