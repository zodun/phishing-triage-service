"""Vercel entry point for the complete PhishGuard workspace."""

import os
import sys
from pathlib import Path

# Serverless deployments only provide writable temporary storage.
os.environ.setdefault("GRADIO_TEMP_DIR", "/tmp/phishguard-gradio")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "false")
sys.path.insert(0, str(Path(__file__).parent / "local_invoice"))

from workspace_app import create_workspace  # noqa: E402

app = create_workspace()
