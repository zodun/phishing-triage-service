"""Local setup, validated before sign-in; secrets never appear in status output."""

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from .gmail import _configured_path


def _write_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".setup-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_google_client(path=None):
    path = Path(path) if path else _configured_path("GMAIL_CLIENT_SECRET_FILE", ".credentials/gmail-client.json")
    if not path.is_file():
        raise ValueError("Google setup is needed. Open Account setup below and import your Desktop OAuth client JSON.")
    if path.stat().st_size > 64_000:
        raise ValueError("This file is too large to be a Google OAuth client file.")
    try:
        data = json.loads(path.read_text())
    except (ValueError, UnicodeError):
        raise ValueError("Choose the original JSON file downloaded from Google Cloud.") from None
    if not isinstance(data, dict) or "web" in data or not isinstance(data.get("installed"), dict):
        raise ValueError(
            "Choose a Desktop app OAuth client. Web app clients and service-account files do not work here."
        )
    client = data["installed"]
    if (
        not isinstance(client.get("client_id"), str)
        or not client["client_id"].endswith(".apps.googleusercontent.com")
        or not client.get("client_secret")
    ):
        raise ValueError("This Google client file is incomplete. Download the Desktop app JSON again.")
    if client.get("auth_uri") not in (
        "https://accounts.google.com/o/oauth2/auth",
        "https://accounts.google.com/o/oauth2/v2/auth",
    ) or client.get("token_uri") not in (
        "https://oauth2.googleapis.com/token",
        "https://accounts.google.com/o/oauth2/token",
    ):
        raise ValueError("The client file must use official Google sign-in endpoints.")
    return {"installed": client}


def import_google_client(upload_path):
    if not upload_path:
        raise ValueError("Choose your Google Desktop OAuth client JSON first.")
    data = read_google_client(upload_path)
    destination = _configured_path("GMAIL_CLIENT_SECRET_FILE", ".credentials/gmail-client.json")
    if destination.exists():
        try:
            previous = read_google_client(destination)
        except ValueError:
            previous = None
        if previous and previous["installed"]["client_id"] != data["installed"]["client_id"]:
            token = _configured_path("GMAIL_TOKEN_FILE", ".credentials/gmail-token.json")
            if token.exists():
                raise ValueError(
                    "A different Google client is already signed in. Remove its saved Gmail token before switching clients."
                )
    _write_private(destination, data)
    return "Google client saved. Select Connect Gmail to sign in."


def model_configuration():
    path = _configured_path("INVOICE_MODEL_CONFIG_FILE", ".credentials/invoice-model.json")
    if path.exists():
        try:
            config = json.loads(path.read_text())
            if not isinstance(config, dict):
                raise ValueError()
            return config
        except (ValueError, UnicodeError):
            raise ValueError("Saved model settings could not be read. Save them again in Account setup.") from None
    provider = os.getenv("INVOICE_MODEL_PROVIDER", "azure").lower()
    return {
        "provider": provider,
        "api_key": os.getenv("DEEPSEEK_API_KEY", "")
        if provider == "deepseek"
        else os.getenv("OPENAI_API_KEY", "")
        if provider == "openai"
        else os.getenv("OPENAI_AGENTS_API_KEY") or os.getenv("EVAL_MODEL_API_KEY", ""),
        "model": os.getenv("INVOICE_MODEL")
        or (
            "deepseek-v4-flash"
            if provider == "deepseek"
            else "gpt-4.1-mini"
            if provider == "openai"
            else os.getenv("OPENAI_AGENTS_DEPLOYMENT", "gpt-4.1")
        ),
        "endpoint": os.getenv("OPENAI_AGENTS_ENDPOINT") or os.getenv("EVAL_MODEL_ENDPOINT", ""),
        "api_version": os.getenv("OPENAI_AGENTS_API_VERSION", "2024-08-01-preview"),
    }


def save_model_settings(provider, api_key, model, endpoint):
    if provider not in ("openai", "azure", "deepseek"):
        raise ValueError("Choose OpenAI, DeepSeek, or Azure OpenAI.")
    if not api_key or not api_key.strip() or not model or not model.strip():
        raise ValueError("Enter your API key and model or deployment name.")
    if provider == "azure":
        parsed = urlparse(endpoint.strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise ValueError(
                "Azure requires your HTTPS resource endpoint, for example https://your-resource.openai.azure.com/."
            )
    config = {
        "provider": provider,
        "api_key": api_key.strip(),
        "model": model.strip(),
        "endpoint": endpoint.strip() if provider == "azure" else "",
        "api_version": os.getenv("OPENAI_AGENTS_API_VERSION", "2024-08-01-preview"),
    }
    _write_private(_configured_path("INVOICE_MODEL_CONFIG_FILE", ".credentials/invoice-model.json"), config)
    return "Model settings saved locally. They will be checked when you read an invoice."


def setup_status():
    try:
        read_google_client()
        gmail_ready = True
    except (ValueError, OSError):
        gmail_ready = False
    try:
        model = model_configuration()
        model_ready = bool(
            model.get("api_key")
            and model.get("model")
            and (
                model.get("provider") in ("openai", "deepseek")
                or (model.get("provider") == "azure" and model.get("endpoint"))
            )
        )
    except (ValueError, OSError):
        model_ready = False
    missing = []
    if not gmail_ready:
        missing.append("Google client file")
    if not model_ready:
        missing.append("invoice model settings")
    return {
        "gmail_ready": gmail_ready,
        "model_ready": model_ready,
        "summary": "Setup needed: " + " and ".join(missing) + "."
        if missing
        else "Setup files are ready. Connect Gmail to continue.",
    }
