import http.cookiejar
import json
import threading
import unittest
import urllib.request

from x20.service import start_test_server


class _BrowserClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def get(self, path: str) -> tuple[dict[str, object], object]:
        with self.opener.open(f"{self.base_url}{path}", timeout=5) as response:
            return json.load(response), response.headers

    def post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.opener.open(request, timeout=5) as response:
            return json.load(response)


class MultiUserServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server, self.thread = start_test_server()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_two_browsers_keep_symbol_and_profile_independent(self) -> None:
        alice = _BrowserClient(self.base_url)
        bob = _BrowserClient(self.base_url)
        alice_initial, headers = alice.get("/api/snapshot")
        bob_initial, _ = bob.get("/api/snapshot")

        self.assertEqual(alice_initial["symbol"], "AAPL")
        self.assertEqual(bob_initial["symbol"], "AAPL")
        self.assertEqual(len(alice.cookies), 1)
        self.assertEqual(len(bob.cookies), 1)
        self.assertNotEqual(next(iter(alice.cookies)).value, next(iter(bob.cookies)).value)
        self.assertIn("HttpOnly", headers.get("Set-Cookie", ""))
        self.assertIn("SameSite=Lax", headers.get("Set-Cookie", ""))

        results: dict[str, dict[str, object]] = {}
        barrier = threading.Barrier(2)

        def update_alice() -> None:
            barrier.wait()
            results["alice"] = alice.post("/api/symbol", {"symbol": "MSFT"})

        def update_bob() -> None:
            barrier.wait()
            results["bob"] = bob.post(
                "/api/profile",
                {"shares": 7, "entry_price": 90, "portfolio_value": 5000},
            )

        first = threading.Thread(target=update_alice)
        second = threading.Thread(target=update_bob)
        first.start()
        second.start()
        first.join(timeout=5)
        second.join(timeout=5)

        self.assertEqual(results["alice"]["symbol"], "MSFT")
        self.assertEqual(results["bob"]["symbol"], "AAPL")
        self.assertEqual(results["alice"]["investor"]["profile"]["shares"], 0.0)
        self.assertEqual(results["bob"]["investor"]["profile"]["shares"], 7.0)

        alice_after, _ = alice.get("/api/snapshot")
        bob_after, _ = bob.get("/api/snapshot")
        self.assertEqual(alice_after["symbol"], "MSFT")
        self.assertEqual(bob_after["symbol"], "AAPL")
        self.assertTrue(alice_after["session"]["isolated"])
        self.assertTrue(bob_after["session"]["isolated"])

    def test_health_check_does_not_allocate_a_user_session(self) -> None:
        client = _BrowserClient(self.base_url)
        health, headers = client.get("/api/health")
        self.assertTrue(health["ok"])
        self.assertTrue(health["multi_user"])
        self.assertEqual(health["active_sessions"], 0)
        self.assertIsNone(headers.get("Set-Cookie"))


if __name__ == "__main__":
    unittest.main()
