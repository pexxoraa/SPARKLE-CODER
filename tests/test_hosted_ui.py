"""Exercise the real HTTP boundary between a hosted UI and the loopback engine."""
import http.client
import unittest
from urllib.parse import parse_qs, urlsplit

import test_web
from sparkle_coder.web import website_origin


class HostedUITests(unittest.TestCase):
    setUp = test_web.WebTests.setUp
    close = test_web.WebTests.close
    request = test_web.WebTests.request
    api = test_web.WebTests.api

    def pair(self, origin="https://sparkle.example"):
        status, body, _ = self.request("/api/hosted-ui", {"url": origin}, headers={"Origin": self.server.origin})
        self.assertEqual(status, 200, body)
        values = parse_qs(urlsplit(body["url"]).fragment)
        self.assertEqual(values["engine"], [self.server.origin])
        token = values["token"][0]
        self.assertNotEqual(token, self.server.token)
        return {"Origin": origin, "Sec-Fetch-Site": "cross-site", "X-Sparkle-Token": token}

    def preflight(self, origin, method="POST", headers="content-type,x-sparkle-token"):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            client.request("OPTIONS", "/api/projects", headers={"Origin": origin,
                           "Access-Control-Request-Method": method, "Access-Control-Request-Headers": headers,
                           "Access-Control-Request-Private-Network": "true"})
            response = client.getresponse()
            response.read()
            return response.status, dict(response.getheaders())
        finally:
            client.close()

    def test_pairing_requires_local_origin_and_authentication(self):
        for headers, auth in (({}, True), ({"Origin": self.server.origin}, False),
                              ({"Origin": "https://sparkle.example"}, True)):
            status, _, _ = self.request("/api/hosted-ui", {"url": "https://sparkle.example"}, headers=headers, auth=auth)
            self.assertIn(status, (401, 403))
        self.assertIsNone(self.server.hosted_origin)

    def test_paired_website_can_create_read_and_download_a_project(self):
        headers = self.pair()
        status, project, cors = self.request("/api/projects", {"name": "Hosted project"}, headers=headers)
        self.assertEqual(status, 200, project)
        self.assertEqual(cors["Access-Control-Allow-Origin"], "https://sparkle.example")
        root = self.app.project(project["id"])[1].root
        (root / "example.txt").write_text("Saved on this device")
        status, data, _ = self.request(f"/api/projects/{project['id']}/download?path=example.txt", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(data, "Saved on this device")
        status, body, _ = self.request("/api/hosted-ui", {"url": "https://another.example"}, headers=headers)
        self.assertEqual(status, 403, body)

    def test_exact_origin_and_separate_token_are_both_required(self):
        paired = self.pair()
        for headers in ({**paired, "X-Sparkle-Token": self.server.token},
                        {**paired, "X-Sparkle-Token": ""},
                        {**paired, "Origin": "https://sparkle.example.attacker.example"},
                        {"X-Sparkle-Token": paired["X-Sparkle-Token"]}):
            status, _, _ = self.request("/api/state", headers=headers)
            self.assertIn(status, (401, 403))

    def test_preflight_only_allows_the_paired_site_and_expected_headers(self):
        self.assertEqual(self.preflight("https://sparkle.example")[0], 403)
        self.pair()
        status, headers = self.preflight("https://sparkle.example")
        self.assertEqual(status, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "https://sparkle.example")
        self.assertEqual(headers["Access-Control-Allow-Private-Network"], "true")
        self.assertNotIn("Access-Control-Allow-Credentials", headers)
        for origin, method, requested in (("https://evil.example", "POST", "x-sparkle-token"),
                                          ("https://sparkle.example", "DELETE", "x-sparkle-token"),
                                          ("https://sparkle.example", "GET", "authorization")):
            self.assertEqual(self.preflight(origin, method, requested)[0], 403)

    def test_repairing_and_disconnecting_revoke_previous_website_access(self):
        first = self.pair()
        second = self.pair()
        self.assertEqual(self.request("/api/state", headers=first)[0], 401)
        self.assertEqual(self.request("/api/state", headers=second)[0], 200)
        status, body, cors = self.request("/api/disconnect-hosted-ui", {}, headers=second)
        self.assertEqual(status, 200, body)
        self.assertEqual(cors["Access-Control-Allow-Origin"], "https://sparkle.example")
        self.assertEqual(self.request("/api/state", headers=second)[0], 403)
        self.assertEqual(self.request("/api/state")[0], 200, "The local app remains usable")

    def test_website_address_rejects_credentials_paths_and_insecure_remote_hosts(self):
        self.assertEqual(website_origin("https://SPARKLE.example:443/"), "https://sparkle.example")
        for value in ("http://sparkle.example", "https://user:pass@sparkle.example", "https://sparkle.example/path",
                      "https://sparkle.example/?token=secret", "https://sparkle.example/#token=secret",
                      "https://*.example", "https://sparkle.example:invalid", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                website_origin(value)
