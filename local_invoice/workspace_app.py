"""Launch the Gmail invoice workflow and manual inspector on one local origin."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
load_dotenv(ROOT / ".env")


def create_workspace():
    import gradio as gr
    from fastapi.routing import APIRoute
    from starlette.responses import RedirectResponse

    from app.main import app
    from invoice_app import create_app
    from invoice_email.appearance import workspace_css

    async def home():
        return RedirectResponse("/invoices/", status_code=307)

    app.router.routes.insert(0, APIRoute("/", home, methods=["GET"]))
    app.state.invoice_workspace = True
    return gr.mount_gradio_app(
        app,
        create_app(workspace=True),
        path="/invoices",
        server_name="127.0.0.1",
        footer_links=[],
        show_error=False,
        head="<style>" + workspace_css() + "</style>",
        theme=gr.themes.Base(
            primary_hue="blue",
            neutral_hue="slate",
            font=["-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
            font_mono=["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        ),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        create_workspace(),
        host="127.0.0.1",
        port=int(os.getenv("WORKSPACE_PORT", "8089")),
    )
