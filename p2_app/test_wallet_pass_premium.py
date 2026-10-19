import json
import os
from io import BytesIO
from pathlib import Path
from unittest import mock
from zipfile import ZipFile

from django.contrib.auth.models import User
from django.test import TestCase

from platform_app.models import MemberAccount
from .passes import build_apple_pass


class PremiumWalletPassTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="very.long.email@example.de",
            email="very.long.email@example.de",
        )
        member, _ = MemberAccount.objects.get_or_create(user=self.user)
        member.status = "active"
        member.save(update_fields=["status"])

    def build_pass(self):
        config = {
            "APPLE_PASS_TYPE_ID": "pass.de.aplusesthetic.app",
            "APPLE_TEAM_ID": "TESTTEAM",
            "APPLE_PASS_CERT_PATH": "/tmp/test-cert.pem",
            "APPLE_PASS_KEY_PATH": "/tmp/test-key.pem",
            "APPLE_WWDR_CERT_PATH": "/tmp/test-wwdr.pem",
        }

        def sign(command, **kwargs):
            Path(command[command.index("-out") + 1]).write_bytes(b"test-signature")
            return mock.Mock(returncode=0)

        with mock.patch.dict(os.environ, config), mock.patch(
            "p2_app.passes.subprocess.run", side_effect=sign
        ):
            output = build_apple_pass(self.user)
        with ZipFile(BytesIO(output.getvalue())) as archive:
            payload = json.loads(archive.read("pass.json"))
            artwork = archive.read("strip.png")
            signature = archive.read("signature")
        return payload, artwork, signature

    def test_email_is_not_rendered_as_primary_card_name(self):
        payload, artwork, signature = self.build_pass()
        card = payload["storeCard"]
        self.assertEqual(card["primaryFields"][0]["value"], "A+ Mitglied")
        self.assertEqual(card["secondaryFields"][0]["label"], "PUNKTE")
        self.assertEqual(len(card["secondaryFields"]), 1)
        self.assertEqual(card["auxiliaryFields"], [])
        self.assertTrue(any(item["key"] == "number" for item in card["backFields"]))
        self.assertTrue(artwork.startswith(bytes([137, 80, 78, 71])))
        self.assertTrue(signature)

    def test_long_real_name_is_shortened_without_email(self):
        self.user.first_name = "Alexandra"
        self.user.last_name = "Von Beispiel-Musterhoff Langname"
        self.user.save(update_fields=["first_name", "last_name"])
        payload, _, _ = self.build_pass()
        name = payload["storeCard"]["primaryFields"][0]["value"]
        self.assertLessEqual(len(name), 30)
        self.assertTrue(name.startswith("Alexandra"))
        self.assertNotIn("@", name)
