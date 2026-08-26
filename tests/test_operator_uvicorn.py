from __future__ import annotations

import re
import socket
import threading
import time
import unittest
from pathlib import Path
from typing import Any

import httpx
import uvicorn

from perfect_catalog.operator_api import OperatorAuthenticator, create_operator_app


class _Gateway:
    def close(self) -> None: pass
    def plans(self, *, limit: int = 100) -> list[dict[str, Any]]: return []
    def intake_submissions(self, **_: Any) -> dict[str, Any]:
        return {"items": [], "filtered_count": 0}


class RealUvicornLoginTests(unittest.TestCase):
    def test_real_localhost_get_cookie_csrf_post_and_redirect(self) -> None:
        gateway = _Gateway()
        app = create_operator_app(
            gateway,  # type: ignore[arg-type]
            OperatorAuthenticator("uvicorn-qa", "temporary-123", pbkdf2_iterations=1),
            intake_root=Path("scratch/uvicorn-login-test"),
        )
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(server.started, "Uvicorn no inició en localhost")
        base_url = f"http://127.0.0.1:{port}"
        try:
            with httpx.Client(base_url=base_url, follow_redirects=False) as client:
                page = client.get("/operator/login")
                self.assertEqual(page.status_code, 200)
                cookie = client.cookies.get("pc_operator_login")
                self.assertTrue(cookie)
                self.assertIn("HttpOnly", page.headers["set-cookie"])
                match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
                self.assertIsNotNone(match)
                response = client.post(
                    "/operator/login",
                    data={"csrf_token": match.group(1), "access_code": "temporary-123"},
                    headers={"Origin": base_url},
                )
                self.assertEqual(response.status_code, 303)
                self.assertEqual(response.headers["location"], "/operator")
                self.assertTrue(client.cookies.get("pc_operator_session"))
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            listener.close()
        self.assertFalse(thread.is_alive(), "Uvicorn no se detuvo limpiamente")


if __name__ == "__main__":
    unittest.main()
