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
    import gradio as gr
    from invoice_email.appearance import workspace_css

    port = os.getenv("INVOICE_APP_PORT")
    create_app().launch(
        server_name="127.0.0.1",
        server_port=int(port) if port else None,
        share=False,
        show_error=False,
        footer_links=[],
        head="<style>" + workspace_css() + "</style>",
        theme=gr.themes.Base(
            primary_hue="blue",
            neutral_hue="slate",
            font=["-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
            font_mono=["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        ),
    )
