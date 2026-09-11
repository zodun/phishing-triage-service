"""Gradio controls shared by the full demo and the local invoice-only launcher."""

import tempfile
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from html import escape

import gradio as gr

from .extraction import InvoiceExtractor
from .gmail import connect_gmail, pdf_links
from .models import export_email
from .workflow import Analysis, analyze_message
from .settings import import_google_client, save_model_settings, setup_status, model_configuration
from .phishing import PhishingAssessment, scan_message, combine_assessments


def phishing_view(selection, analyses):
    if selection is None or not analyses:
        return ""
    try:
        index = int(selection)
        if index < 0 or index >= len(analyses):
            return ""
        risk = analyses[index].phishing
    except (TypeError, ValueError):
        return ""
    risk = risk or PhishingAssessment(status="unable_to_assess", reasons=["The phishing check has not completed."])
    note = (
        "This is not a guarantee of safety. Links, sender identity, and payment records have not been independently verified."
        if risk.can_draft
        else "No reminder was created. Verify this message using contact details you already trust."
    )
    return (
        f'<section class="phishing-result {risk.status}" role="status"><h3>{escape(risk.label)}</h3><ul>'
        + "".join(f"<li>{escape(reason)}</li>" for reason in risk.reasons)
        + f"</ul><p>{escape(note)}</p></section>"
    )


def review_result(selection, analyses):
    empty = ({}, "", "", "", "", "", None, False)
    if selection is None or not analyses:
        return empty
    try:
        index = int(selection)
        if index < 0 or index >= len(analyses):
            return empty
        result = analyses[index]
    except (ValueError, TypeError):
        return empty
    facts = result.invoice.model_dump(mode="json") if result.invoice else {}
    risk = result.phishing or PhishingAssessment(
        status="unable_to_assess", reasons=["The phishing check has not completed."]
    )
    risk_text = "\n".join([risk.label, *risk.reasons])
    if result.error:
        return (facts, result.text, risk_text + "\n" + result.error, "", "", "", None, False)
    if not risk.can_draft:
        return (
            facts,
            result.text,
            risk_text + "\nReminder paused. Verify the message independently.",
            "",
            "",
            "",
            None,
            False,
        )
    reminder = result.reminder
    if reminder is None:
        return empty
    status = "\n".join(
        [risk.label, reminder.status, *reminder.warnings, *(result.invoice.notes if result.invoice else [])]
    )
    return (facts, result.text, status, reminder.recipient, reminder.subject, reminder.body, None, reminder.ready)


def save_draft(recipient, subject, body, eligible):
    if not eligible:
        raise ValueError("Select an overdue invoice with verified details before exporting a reminder.")
    raw = export_email(recipient.strip(), subject.strip(), body)
    # Gradio serves and cleans its cached copy. Remove the temporary original in
    # the UI handler after moving it into Gradio's cache.
    with tempfile.NamedTemporaryFile(prefix="invoice-reminder-", suffix=".eml", delete=False) as stream:
        stream.write(raw)
        return stream.name


def _connect():
    if not setup_status()["gmail_ready"]:
        yield "Open Account setup and import your Google client file first.", ""
        return
    yield "Preparing secure Google sign-in…", ""
    links = Queue()
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(connect_gmail, interactive=True, on_authorization=links.put)
    sign_in = ""
    try:
        while not future.done():
            try:
                url = links.get(timeout=0.25)
                sign_in = (
                    '<a class="google-signin" href="'
                    + escape(url, quote=True)
                    + '" target="_blank" rel="noopener noreferrer">Continue with Google ↗</a>'
                    '<p class="signin-help">Choose your account in the new tab, then return here.</p>'
                )
                yield "Waiting for Google sign-in. Use the link below.", sign_in
            except Empty:
                pass
        address = future.result().profile()
        yield f"Connected to {address}", ""
    except ValueError as exc:
        yield str(exc), ""
    except Exception as exc:
        if "timeout" in type(exc).__name__.lower():
            message = "Sign-in timed out. Select Connect Gmail and use the Google link within three minutes."
        elif getattr(getattr(exc, "resp", None), "status", None) == 403:
            message = "Google denied access. In Account setup, enable the Gmail API and add your email as a test user."
        else:
            message = "Sign-in could not finish. Check the Google setup steps and try again. If Google shows an error, check its message."
        yield message, ""
    finally:
        executor.shutdown(wait=False)


def _search(query, limit):
    from googleapiclient.errors import HttpError

    try:
        messages = connect_gmail().search(query, limit)
        choices = [(f"{m.date} | {m.subject} | {m.sender}", m.id) for m in messages]
        if not messages:
            return gr.update(choices=[], value=None), (
                "No emails with a valid PDF attachment or direct PDF link matched your search. "
                "Open Search options below to widen the date range or search outside your inbox, then try again."
            )
        return gr.update(choices=choices, value=None), (
            f"Found {len(messages)} email(s) with a valid PDF attachment or a direct PDF link "
            "(up to your maximum). Linked files are not downloaded or verified. Select an email to check."
        )
    except ValueError as exc:
        return gr.update(choices=[], value=None), str(exc)
    except HttpError as exc:
        try:
            reasons = {item.get("reason") for item in json.loads(exc.content).get("error", {}).get("errors", [])}
        except (ValueError, TypeError, AttributeError):
            reasons = set()
        if exc.resp.status == 429 or reasons & {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}:
            message = (
                "Google is temporarily limiting Gmail requests. Automatic retries did not finish the search. "
                "Wait a minute, then click Find invoice emails again. Your saved connection does not need setup again."
            )
        elif exc.resp.status == 401:
            message = "Gmail sign-in has expired. Go back to connection and click Connect Gmail."
        elif exc.resp.status == 403:
            message = "Google denied Gmail access. Go back to connection and reconnect; check Gmail API permissions if it continues."
        else:
            message = "Google could not complete this search. Please try again shortly."
        return gr.update(choices=[], value=None), message
    except Exception:
        return gr.update(
            choices=[], value=None
        ), "Gmail search failed. Check the connection and search terms, then retry."


def _analyze(message_id, signature):
    empty = ("", [], gr.update(choices=[], value=None))
    try:
        if not message_id:
            raise ValueError("Select a Gmail message first.")
        if not setup_status()["model_ready"]:
            raise ValueError("Add your AI key using “Add my AI key” below, then click Check email again.")
        extractor = InvoiceExtractor.from_env()
        mailbox = connect_gmail()
        message = mailbox.get_message(message_id)
        if not message.attachments and pdf_links(message):
            risk = scan_message(message)
            if risk.can_draft:
                risk = combine_assessments(risk, extractor.assess_phishing("", message))
            result = Analysis(
                "Email with PDF links",
                phishing=risk,
                error="Email checked. The linked PDF has not been downloaded or verified. "
                "A PDF attachment is needed to read invoice details and prepare a reminder.",
            )
            return (
                message.body,
                [result],
                gr.update(choices=[("Email with PDF links", "0")], value="0"),
                "Email checked; linked PDF content has not been assessed.",
                *review_result("0", [result]),
            )
        if not message.attachments:
            return (
                message.body,
                [],
                gr.update(choices=[], value=None),
                "This message contains no PDF attachments.",
                *review_result(None, []),
            )
        if len(message.attachments) > 10:
            raise ValueError("This email has more than 10 PDFs. Forward the relevant invoices in smaller batches.")
        results = analyze_message(mailbox, message, extractor, signature=signature)
        choices = [(f"{i + 1}. {r.filename}", str(i)) for i, r in enumerate(results)]
        count = sum(r.reminder is not None and r.reminder.ready for r in results)
        return (
            message.body,
            results,
            gr.update(choices=choices, value="0"),
            f"Read {len(results)} PDF attachment(s); {count} reminder(s) ready for review.",
            *review_result("0", results),
        )
    except ValueError as exc:
        gr.Warning(str(exc))
        return (*empty, str(exc), *review_result(None, []))
    except Exception:
        return (
            *empty,
            "Unable to read this email. Check Gmail/model configuration and retry.",
            *review_result(None, []),
        )


def create_invoice_email_tab(workspace=False):
    from .appearance import HEADER, SETUP_GUIDE

    configured = setup_status()
    try:
        selected_provider = model_configuration().get("provider", "openai") if configured["model_ready"] else "openai"
        selected_model = (
            model_configuration().get("model", "gpt-4.1-mini") if configured["model_ready"] else "gpt-4.1-mini"
        )
    except ValueError:
        selected_provider, selected_model = "openai", "gpt-4.1-mini"
    header = HEADER
    if workspace:
        header = header.replace(
            '<p class="rail-description">Invoice review</p>',
            '<nav class="workspace-navigation" aria-label="Workspace">'
            '<a href="/invoices/" aria-current="page">Gmail &amp; invoices</a>'
            '<a href="/inspect">Inspect pasted email ↗</a></nav>',
        )
    gr.HTML(header, elem_id="invoice-header", apply_default_css=False)
    analyses = gr.State([])
    eligible = gr.State(False)
    setup_from_invoice = gr.State(False)
    gr.HTML(
        '<div class="simple-intro"><h1>Invoice reminders</h1>'
        "<p>From an invoice in your inbox to a reviewed payment reminder.</p></div>",
        elem_id="invoice-intro",
        apply_default_css=False,
    )
    steps = gr.HTML(_step_heading(1), elem_id="invoice-sidebar", apply_default_css=False)

    with gr.Column(elem_id="invoice-shell"):
        with gr.Column(elem_id="step-connect", visible=True) as step_connect:
            gr.Markdown("## Connect your email\nWe’ll look for invoice attachments in your Gmail account.")
            setup_hint = gr.Markdown(_setup_explanation(configured))
            start_setup = gr.Button(
                "Start one-time setup",
                variant="primary",
                visible=not (configured["gmail_ready"] and configured["model_ready"]),
            )
            connect = gr.Button("Connect Gmail", variant="primary", visible=configured["gmail_ready"])
            connection_status = gr.Textbox(
                label="Connection",
                elem_id="connection-status",
                interactive=False,
                lines=2,
                placeholder="You’ll choose your Google account in a new tab.",
            )
            sign_in_link = gr.HTML("", apply_default_css=False)
            with gr.Accordion("Account setup — only needed once", open=False, elem_id="account-setup") as setup_panel:
                gr.Markdown(
                    "This local app needs permission to read Gmail and an AI account to read invoices. "
                    "These settings are saved on this computer. If you have an IT person, they can do this part for you."
                )
                with gr.Accordion(
                    "1. Set up Gmail access", open=not configured["gmail_ready"], elem_id="google-setup"
                ) as google_panel:
                    gr.HTML(SETUP_GUIDE, apply_default_css=False)
                    client_file = gr.File(
                        label="Choose the file you downloaded from Google",
                        file_types=[".json"],
                        type="filepath",
                        height=140,
                    )
                    import_client = gr.Button("Save Google file", variant="primary")
                    import_status = gr.Textbox(label="Gmail setup", interactive=False)
                with gr.Accordion(
                    "2. Set up invoice reading",
                    open=configured["gmail_ready"] and not configured["model_ready"],
                    elem_id="ai-setup",
                ) as ai_panel:
                    gr.Markdown(
                        "The AI reads the invoice and finds the customer and amount. "
                        "Choose the service your key belongs to and paste the key below."
                    )
                    provider = gr.Dropdown(
                        label="Your AI service",
                        choices=[("OpenAI", "openai"), ("DeepSeek", "deepseek"), ("Azure OpenAI", "azure")],
                        value=selected_provider,
                    )
                    api_key = gr.Textbox(label="API key", type="password", placeholder="Paste your key here")
                    with gr.Accordion("Advanced options — usually no changes needed", open=False):
                        model = gr.Textbox(label="Model or deployment", value=selected_model)
                        endpoint = gr.Textbox(label="Azure resource endpoint", visible=selected_provider == "azure")
                    save_model = gr.Button("Save and continue", variant="primary")
                    model_status = gr.Textbox(label="Invoice reading setup", interactive=False)
                    gr.Markdown(
                        "Your key stays on this computer. Invoice text is sent to the AI provider when you ask us to read it."
                    )
                setup_summary = gr.Textbox(
                    label="What’s left to set up", value=configured["summary"], interactive=False
                )
            gr.Markdown("**You stay in control.** The app reads email and writes drafts. It does not send them.")

        with gr.Column(elem_id="step-invoice", visible=False) as step_invoice:
            gr.Markdown("## Choose an invoice\nFind a recent email with a PDF attachment or a direct PDF link.")
            search = gr.Button("Find invoice emails", variant="primary")
            status = gr.Textbox(
                label="Search and review status",
                elem_id="workflow-status",
                interactive=False,
                value="Click Find invoice emails, select an email below, then click Check email.",
                lines=3,
            )
            with gr.Column(visible=True, elem_id="invoice-message-results"):
                message_choice = gr.Dropdown(
                    label="Email with PDF attachment or link",
                    choices=[],
                    interactive=True,
                    info="Click Find invoice emails to populate this list, then choose one.",
                )
                analyze = gr.Button("Check email", variant="primary")
            with gr.Column(visible=not configured["model_ready"], elem_id="invoice-reading-setup") as reading_setup:
                gr.Markdown(
                    "**One step left: add your AI key.**\n\n"
                    "Gmail gives us access to the attachment. The AI reads it and prepares your reminder. "
                    "Add the key once, then return to this invoice.",
                    elem_id="invoice-reading-help",
                )
                reading_setup_button = gr.Button("Add my AI key")
            with gr.Accordion("Search options and email signature", open=False):
                query = gr.Textbox(
                    label="Gmail search",
                    value="in:inbox newer_than:90d",
                    info="The default looks in your inbox from the last 90 days.",
                )
                limit = gr.Slider(1, 50, value=20, step=1, label="Maximum messages")
                signature = gr.Textbox(label="Your email signature", value="Accounts Receivable")
            back_connect = gr.Button("← Back to connection")

        with gr.Column(elem_id="step-review", visible=False) as step_review:
            gr.Markdown(
                "## Review the assessment\nCheck the findings and invoice details. Eligible reminders appear below for you to edit."
            )
            phishing_status = gr.HTML("", elem_id="phishing-status", apply_default_css=False)
            invoice_choice = gr.Dropdown(label="PDF to review", choices=[], interactive=True, visible=False)
            invoice_summary = gr.Textbox(
                label="Invoice at a glance", interactive=False, lines=2, elem_id="invoice-summary"
            )
            review_status = gr.Textbox(label="Review notes", lines=2, interactive=False, elem_id="review-status")
            with gr.Column(elem_id="invoice-composer") as composer:
                recipient = gr.Textbox(label="To", placeholder="Customer’s email address", elem_id="draft-recipient")
                subject = gr.Textbox(label="Subject", elem_id="draft-subject")
                copy_options = (
                    {"buttons": ["copy"]} if int(gr.__version__.split(".")[0]) >= 6 else {"show_copy_button": True}
                )
                body = gr.Textbox(label="Message", lines=12, elem_id="draft-message", **copy_options)
                gr.Markdown(
                    "**Ready?** Copy the subject and message into Gmail, or download the draft to open in an email app."
                )
                export = gr.Button("Download email draft", variant="primary")
                download = gr.File(label="Your email file", interactive=False, elem_id="draft-download", height=80)
            with gr.Accordion("See the original invoice", open=False, elem_id="invoice-reader"):
                source = gr.Textbox(label="Text read from the PDF", lines=10, interactive=False)
                with gr.Accordion("Original email", open=False):
                    email_body = gr.Textbox(label="Email body", lines=6, interactive=False)
                with gr.Accordion("Extraction details", open=False):
                    facts = gr.JSON(label="Invoice details and supporting quotes")
            back_invoice = gr.Button("← Choose another invoice")

    review_outputs = [facts, source, review_status, recipient, subject, body, download, eligible]
    work_controls = [
        connect,
        search,
        query,
        limit,
        message_choice,
        analyze,
        signature,
        invoice_choice,
        recipient,
        subject,
        body,
        export,
        import_client,
        client_file,
        provider,
        api_key,
        model,
        endpoint,
        save_model,
        back_connect,
        back_invoice,
    ]
    work_controls.append(reading_setup_button)

    def run_locked(button, fn, inputs, outputs):
        def begin():
            updates = [gr.update(interactive=False) for _ in work_controls]
            if fn is _analyze:
                updates.append(
                    gr.update(
                        value="Checking for phishing, then reading the invoice if no warning signs are found…",
                        interactive=False,
                    )
                )
            elif fn is _search:
                updates.append(
                    gr.update(
                        value="Searching Gmail and verifying PDF attachments and links. This can take a moment…",
                        interactive=False,
                    )
                )
            return updates

        lock = button.click(
            begin, outputs=work_controls + ([status] if fn in (_analyze, _search) else []), queue=False, api_name=False
        )
        work = lock.then(fn, inputs, outputs, concurrency_limit=1, concurrency_id="invoice-workflow")
        work.then(
            lambda: [gr.update(interactive=True) for _ in work_controls],
            outputs=work_controls,
            queue=False,
            api_name=False,
        )
        return work

    stage_outputs = [step_connect, step_invoice, step_review, steps]

    def show_step(number):
        return (
            gr.update(visible=number == 1),
            gr.update(visible=number == 2),
            gr.update(visible=number == 3),
            _step_heading(number),
        )

    connection = run_locked(connect, _connect, None, [connection_status, sign_in_link])
    connection.then(
        lambda message: show_step(2 if message.startswith("Connected to ") else 1), connection_status, stage_outputs
    )
    run_locked(search, _search, [query, limit], [message_choice, status])
    message_choice.change(lambda: ([], *review_result(None, [])), outputs=[analyses, *review_outputs])
    analysis_event = run_locked(
        analyze, _analyze, [message_choice, signature], [email_body, analyses, invoice_choice, status, *review_outputs]
    )
    analysis_event.then(
        lambda results: (*show_step(3 if results else 2), gr.update(visible=len(results) > 1)),
        analyses,
        [*stage_outputs, invoice_choice],
    )

    def summary(selection, results):
        if selection is None or not results:
            return ""
        try:
            result = results[int(selection)]
        except (ValueError, IndexError, TypeError):
            return ""
        value = result.invoice
        if value is None:
            return "We could not read this invoice. See the message above."
        amount = " ".join(part for part in (value.currency, value.amount_due) if part)
        return (
            f"{value.customer_name or 'Customer not found'} · Invoice {value.invoice_number or 'number not found'}\n"
            + f"Amount: {amount or 'not found'} · Due: {value.due_date or 'date not found'}"
        )

    invoice_choice.change(review_result, [invoice_choice, analyses], review_outputs).then(
        summary, [invoice_choice, analyses], invoice_summary
    )
    # Re-analysis can keep attachment selection "0" unchanged, so refresh the
    # summary explicitly even when the dropdown does not emit a change event.
    analysis_event.then(summary, [invoice_choice, analyses], invoice_summary)

    def show_assessment(selection, results):
        values = review_result(selection, results)
        return phishing_view(selection, results), gr.update(visible=values[7])

    analysis_event.then(show_assessment, [invoice_choice, analyses], [phishing_status, composer])
    invoice_choice.change(show_assessment, [invoice_choice, analyses], [phishing_status, composer])

    def download_draft(to, title, content, ready):
        try:
            original = save_draft(to, title, content, ready)
            try:
                return download.move_resource_to_block_cache(original)
            finally:
                Path(original).unlink(missing_ok=True)
        except ValueError as exc:
            raise gr.Error(str(exc)) from None

    export.click(download_draft, [recipient, subject, body, eligible], download)
    for control in (recipient, subject, body):
        control.input(lambda: None, outputs=download)

    start_setup.click(lambda: gr.update(open=True), outputs=setup_panel, queue=False)
    back_connect.click(lambda: show_step(1), outputs=stage_outputs, queue=False)
    reading_setup_button.click(
        lambda: (*show_step(1), gr.update(open=True), gr.update(open=True), gr.update(open=False), True),
        outputs=[*stage_outputs, setup_panel, ai_panel, google_panel, setup_from_invoice],
        queue=False,
    )
    back_invoice.click(
        lambda: (*show_step(2), [], *review_result(None, [])),
        outputs=[*stage_outputs, analyses, *review_outputs],
        queue=False,
    )
    provider.change(
        lambda value: (
            gr.update(visible=value == "azure"),
            {"openai": "gpt-4.1-mini", "deepseek": "deepseek-v4-flash", "azure": ""}[value],
            gr.update(
                label={"openai": "OpenAI API key", "deepseek": "DeepSeek API key", "azure": "Azure API key"}[value]
            ),
        ),
        provider,
        [endpoint, model, api_key],
    )

    def setup_updates():
        current = setup_status()
        ready = current["gmail_ready"] and current["model_ready"]
        return (
            _setup_explanation(current),
            gr.update(visible=not ready),
            gr.update(visible=current["gmail_ready"]),
            gr.update(open=not ready),
        )

    def save_google(path):
        try:
            message = import_google_client(path)
            return (
                message,
                setup_status()["summary"],
                None,
                gr.update(open=False),
                gr.update(open=True),
                *setup_updates(),
            )
        except (ValueError, OSError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Could not save the file on this computer."
            return message, setup_status()["summary"], None, gr.update(), gr.update(), *setup_updates()

    def save_ai(provider_value, key, deployment, resource):
        try:
            message = save_model_settings(provider_value, key, deployment, resource)
            return message, setup_status()["summary"], "", *setup_updates()
        except (ValueError, OSError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Could not save your settings on this computer."
            return message, setup_status()["summary"], "", *setup_updates()

    setup_controls = [setup_hint, start_setup, connect, setup_panel]
    run_locked(
        import_client,
        save_google,
        client_file,
        [import_status, setup_summary, client_file, google_panel, ai_panel, *setup_controls],
    )
    saved_model = run_locked(
        save_model,
        save_ai,
        [provider, api_key, model, endpoint],
        [model_status, setup_summary, api_key, *setup_controls],
    )

    def finish_model_setup(return_to_invoice):
        ready = setup_status()["model_ready"]
        stage = show_step(2) if ready and return_to_invoice else (gr.update(), gr.update(), gr.update(), gr.update())
        return (*stage, gr.update(visible=not ready), False if ready else return_to_invoice)

    saved_model.then(finish_model_setup, setup_from_invoice, [*stage_outputs, reading_setup, setup_from_invoice])


def _step_heading(number):
    labels = ("Connect Gmail", "Choose invoice", "Review draft")
    return (
        '<ol class="simple-steps" aria-label="Invoice review progress">'
        + "".join(
            f'<li class="{"current" if i == number else "complete" if i < number else ""}"'
            f"{' aria-current=step' if i == number else ''}><span>{i}</span>{label}</li>"
            for i, label in enumerate(labels, 1)
        )
        + "</ol>"
    )


def _setup_explanation(configured):
    if configured["gmail_ready"] and configured["model_ready"]:
        return "Everything is set up. **Connect Gmail** to choose your account."
    if configured["gmail_ready"]:
        return (
            "**Google is ready. Connect Gmail to choose your account.**\n\n"
            "Before reading invoices, use one-time setup to add your AI account key."
        )
    return (
        "**This app needs a one-time setup before you can connect.**\n\n"
        "We’ll guide you through the Google permission file and the key used to read invoices. "
        "You only need to do this once on this computer."
    )
