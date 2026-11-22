"""Offline tests for the final acceptance staging preflight (no external HTTP)."""
import os
import unittest
from unittest.mock import patch

from check_remote_staging_ready import StrictRedirects, check_origin, main


class Response:
    status = 200

    def geturl(self):
        return "https://preview.aplus.example.org/"

    def close(self):
        pass


class Opener:
    def open(self, request, timeout):
        assert timeout <= 15
        assert request.full_url == "https://preview.aplus.example.org/"
        return Response()


class StagingPreflightTests(unittest.TestCase):
    def test_successful_live_https_origin(self):
        with patch("check_remote_staging_ready.urllib.request.build_opener",
                   return_value=Opener()):
            self.assertEqual(check_origin("https://preview.aplus.example.org"),
                             "preview.aplus.example.org: HTTP 200")

    def test_placeholder_hostname_rejected_before_request(self):
        with self.assertRaisesRegex(ValueError, "placeholder"):
            check_origin("https://preview.example.test")

    def test_cross_hostname_redirect_rejected(self):
        req = __import__("urllib.request", fromlist=["Request"]).Request(
            "https://preview.aplus.example.org/")
        with self.assertRaisesRegex(ValueError, "redirected"):
            StrictRedirects().redirect_request(
                req, None, 302, "redirect", {}, "https://app.a-esthetic.de/")

    def test_insecure_redirect_rejected(self):
        req = __import__("urllib.request", fromlist=["Request"]).Request(
            "https://preview.aplus.example.org/")
        with self.assertRaisesRegex(ValueError, "redirected"):
            StrictRedirects().redirect_request(
                req, None, 302, "redirect", {}, "http://preview.aplus.example.org/")

    def test_no_staging_origin_rejected(self):
        with patch.dict(os.environ, {"STAGING_APP_URL": "", "STAGING_BOOK_URL": ""}):
            with self.assertRaisesRegex(ValueError, "remote staging"):
                main()


if __name__ == "__main__":
    unittest.main()
