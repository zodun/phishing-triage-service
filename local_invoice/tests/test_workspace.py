"""Both workflows remain reachable on one origin."""
import unittest
from fastapi.testclient import TestClient
from workspace_app import create_workspace


class WorkspaceTests(unittest.TestCase):
    def test_homepage_and_inspector_are_connected(self):
        with TestClient(create_workspace()) as client:
            home = client.get("/", follow_redirects=False)
            self.assertEqual(home.status_code, 307)
            self.assertEqual(home.headers["location"], "/invoices/")
            self.assertEqual(client.get("/invoices/").status_code, 200)
            manual = client.get("/inspect")
            self.assertEqual(manual.status_code, 200)
            self.assertIn('href="/invoices/"', manual.text)
            self.assertIn('id="email-form"', manual.text)
            self.assertEqual(client.get("/healthz").status_code, 200)
