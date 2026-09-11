import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from invoice_email.settings import import_google_client, save_model_settings, setup_status
from invoice_email.gmail import connect_gmail
from invoice_email.ui import _connect


CLIENT = {
    "installed": {
        "client_id": "example.apps.googleusercontent.com",
        "client_secret": "test-client-secret",
        "project_id": "test-project",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(
            os.environ,
            {
                "GMAIL_CLIENT_SECRET_FILE": str(self.root / "private/client.json"),
                "GMAIL_TOKEN_FILE": str(self.root / "private/token.json"),
                "INVOICE_MODEL_CONFIG_FILE": str(self.root / "private/model.json"),
            },
            clear=True,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def upload(self, data):
        path = self.root / "upload.json"
        path.write_text(json.dumps(data))
        return str(path)

    def test_missing_setup_is_reported_before_connect(self):
        state = setup_status()
        self.assertFalse(state["gmail_ready"])
        self.assertFalse(state["model_ready"])
        self.assertIn("Google", state["summary"])

    def test_imports_desktop_client_with_private_permissions(self):
        import_google_client(self.upload(CLIENT))
        output = Path(os.environ["GMAIL_CLIENT_SECRET_FILE"])
        self.assertEqual(json.loads(output.read_text()), CLIENT)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertTrue(setup_status()["gmail_ready"])

    def test_rejects_wrong_client_type_and_external_oauth_endpoints(self):
        bad = json.loads(json.dumps(CLIENT))
        bad["installed"]["token_uri"] = "https://attacker.example/token"
        mixed = dict(
            CLIENT, web={"auth_uri": "https://attacker.example/auth", "token_uri": "https://attacker.example/token"}
        )
        for data in ({"web": CLIENT["installed"]}, mixed, bad, {}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                import_google_client(self.upload(data))
        self.assertFalse(Path(os.environ["GMAIL_CLIENT_SECRET_FILE"]).exists())

    def test_saved_model_settings_are_private_and_used_by_extractor(self):
        from invoice_email.extraction import InvoiceExtractor

        save_model_settings("openai", "test-api-key", "gpt-4.1-mini", "")
        self.assertTrue(setup_status()["model_ready"])
        self.assertNotIn("test-api-key", json.dumps(setup_status()))
        with patch("openai.OpenAI") as client:
            extractor = InvoiceExtractor.from_env()
            self.assertEqual(extractor.model, "gpt-4.1-mini")
            self.assertEqual(client.call_args.kwargs["api_key"], "test-api-key")

    def test_azure_requires_https_endpoint(self):
        with self.assertRaises(ValueError):
            save_model_settings("azure", "key", "model", "http://example.com")

    def test_deepseek_uses_its_own_endpoint_and_key(self):
        from invoice_email.extraction import InvoiceExtractor

        save_model_settings("deepseek", "test-deepseek-key", "deepseek-v4-flash", "")
        self.assertTrue(setup_status()["model_ready"])
        with patch("openai.OpenAI") as client:
            extractor = InvoiceExtractor.from_env()
        self.assertEqual(client.call_args.kwargs["base_url"], "https://api.deepseek.com")
        self.assertEqual(client.call_args.kwargs["api_key"], "test-deepseek-key")
        self.assertEqual(extractor.model, "deepseek-v4-flash")

    def test_missing_setup_connect_is_actionable_in_app(self):
        updates = list(_connect())
        self.assertIn("Account setup", updates[-1][0])
        self.assertNotIn("docs/", updates[-1][0])

    def test_sign_in_exposes_google_link_without_launching_another_browser(self):
        import_google_client(self.upload(CLIENT))
        flow = Mock()
        flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?state=test", "test")

        def run(**kwargs):
            flow.authorization_url()
            self.assertFalse(kwargs["open_browser"])
            return Mock(to_json=lambda: "{}")

        flow.run_local_server.side_effect = run
        publish = Mock()
        with (
            patch("google_auth_oauthlib.flow.InstalledAppFlow.from_client_config", return_value=flow),
            patch("googleapiclient.discovery.build"),
            patch("google_auth_httplib2.AuthorizedHttp"),
        ):
            connect_gmail(interactive=True, on_authorization=publish)
        publish.assert_called_once_with("https://accounts.google.com/o/oauth2/auth?state=test")


class WorkspaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_invoice_search_keeps_check_email_visible_and_explains_next_step(self):
        from invoice_app import create_app

        app = create_app()
        props = {item["props"].get("elem_id"): item["props"] for item in app.config["components"]}
        self.assertIn("invoice-message-results", props)
        self.assertTrue(props["invoice-message-results"]["visible"])
        status = next(
            item["props"] for item in app.config["components"] if item["props"].get("elem_id") == "workflow-status"
        )
        self.assertIn("Find invoice emails", status["value"])
        search = next(fn for fn in app.fns.values() if fn.name == "_search")
        begin = app.fns[search.trigger_after]
        self.assertIn("Searching", begin.fn()[-1]["value"])

    async def test_missing_model_setup_is_available_on_invoice_step(self):
        from invoice_app import create_app

        with patch(
            "invoice_email.ui.setup_status",
            return_value={"gmail_ready": True, "model_ready": False, "summary": "Model needed"},
        ):
            app = create_app()
        props = {item["props"].get("elem_id"): item["props"] for item in app.config["components"]}
        self.assertFalse(props["invoice-reading-setup"]["visible"])
        self.assertIn("AI key", props["invoice-reading-help"]["value"])

    async def test_workspace_has_setup_and_distinct_reading_and_writing_areas(self):
        from invoice_app import create_app

        app = create_app()
        ids = {item["props"].get("elem_id") for item in app.config["components"]}
        self.assertTrue({"invoice-sidebar", "invoice-reader", "invoice-composer", "account-setup"}.issubset(ids))

    async def test_first_screen_shows_only_connection_step(self):
        from invoice_app import create_app

        app = create_app()
        props = {item["props"].get("elem_id"): item["props"] for item in app.config["components"]}
        self.assertTrue(props["step-connect"]["visible"])
        self.assertFalse(props["step-invoice"]["visible"])
        self.assertFalse(props["step-review"]["visible"])
        self.assertFalse(props["account-setup"]["open"])

    async def test_only_successful_connection_advances_to_invoice(self):
        from invoice_app import create_app

        app = create_app()
        connection = next(fn for fn in app.fns.values() if fn.name == "_connect")
        transition = next(fn for fn in app.fns.values() if fn.trigger_after == connection._id and len(fn.outputs) == 4)
        failure = transition.fn("Sign-in could not finish.")
        success = transition.fn("Connected to person@example.com")
        self.assertTrue(failure[0]["visible"])
        self.assertFalse(failure[1]["visible"])
        self.assertFalse(success[0]["visible"])
        self.assertTrue(success[1]["visible"])

    async def test_read_failure_stays_on_invoice_step(self):
        from invoice_app import create_app

        app = create_app()
        analysis = next(fn for fn in app.fns.values() if fn.name == "_analyze")
        transition = next(fn for fn in app.fns.values() if fn.trigger_after == analysis._id and len(fn.outputs) == 5)
        result = transition.fn([])
        self.assertTrue(result[1]["visible"])
        self.assertFalse(result[2]["visible"])


if __name__ == "__main__":
    unittest.main()
