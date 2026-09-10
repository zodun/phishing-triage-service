"""Run the invoice workflow without the warranty demo's Azure dependencies."""

from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def create_app():
    import gradio as gr
    from invoice_email.ui import create_invoice_email_tab

    with gr.Blocks(title="Invoice Email", fill_width=True, delete_cache=(3600, 3600)) as app:
        create_invoice_email_tab()
    return app


if __name__ == "__main__":
    port = os.getenv("INVOICE_APP_PORT")
    create_app().launch(
        server_name="127.0.0.1", server_port=int(port) if port else None, share=False, show_error=False, footer_links=[]
    )
