"""Run the invoice workflow without the warranty demo's Azure dependencies."""

from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def create_app(workspace=False):
    import gradio as gr
    from invoice_email.ui import create_invoice_email_tab

    with gr.Blocks(
        title="PhishGuard — Invoice Reminders", fill_width=True, delete_cache=(3600, 3600)
    ) as app:
        create_invoice_email_tab(workspace=workspace)
    return app


if __name__ == "__main__":
    import uvicorn
    from workspace_app import create_workspace

    uvicorn.run(create_workspace(), host="127.0.0.1", port=int(os.getenv("WORKSPACE_PORT", "8089")), access_log=False)
