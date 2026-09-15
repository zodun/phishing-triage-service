"""Smoke-test an already-running local app without reading Gmail or calling AI.

Run: .venv/bin/python tests/smoke_invoice_http.py http://127.0.0.1:7861
"""

import json
import sys
from urllib.request import urlopen

from gradio_client import Client


def main():
    url = sys.argv[1].rstrip("/")
    with urlopen(url + "/", timeout=10) as response:
        assert response.status == 200
    with urlopen(url + "/config", timeout=10) as response:
        config = json.load(response)
    assert config["title"] == "PhishGuard — Invoice Reminders"
    labels = {component["props"].get("label") for component in config["components"]}
    assert {"Message", "To", "PDF to review"}.issubset(labels)
    client = Client(url, verbose=False, analytics_enabled=False)
    try:
        result = client.predict(None, "Accounts Receivable", api_name="/_analyze")
        assert "Select a Gmail message first." in str(result), result
        try:
            client.predict("customer@example.com", "Test", "Test body", api_name="/download_draft")
        except Exception as exc:
            assert "Select an overdue invoice" in str(exc), str(exc)
        else:
            raise AssertionError("Export should fail without an eligible invoice")
    finally:
        client.close()
    print("PASS: HTTP page/config, analysis validation, and ineligible export guard. No Gmail or model calls made.")


if __name__ == "__main__":
    main()
