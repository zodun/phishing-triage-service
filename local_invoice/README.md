# Local Gmail invoice checker

A local, single-user Gradio app for reviewing Gmail emails and PDF invoices.

## Unified workspace

Run both workflows together from the repository root:

```sh
python -m pip install -e . -r local_invoice/requirements-invoice.txt
python local_invoice/workspace_app.py
```

Open http://127.0.0.1:8089. The homepage opens Gmail invoice reminders;
**Inspect pasted email** opens the manual classifier on the same server.
Google and invoice model setup remain available inside the invoice workspace.
`WORKSPACE_PORT` changes the local port. The standalone launcher below remains available.

## Run

Use Python 3.11 or later:

```sh
cd local_invoice
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-invoice.txt
.venv/bin/python invoice_app.py
```

Open http://127.0.0.1:7860 in Safari or another browser. The app must have network
access to Google and your selected AI provider. Its layout expands with the window.

## Setup and use

1. In Account setup, import a Google Desktop OAuth client with the Gmail API enabled.
   Add your account as a test user if your Google consent screen is in testing.
2. Select your AI provider and save its key and model. Configuration and OAuth tokens
   remain in the ignored `.credentials` directory on your computer.
3. Click **Connect Gmail**. Complete Google sign-in if requested.
4. Click **Find invoice emails**, select an email, then click **Check email**.
   Search options and email signature lets you adjust the inbox/date filter and limit.
5. Review the phishing assessment and invoice facts. Eligible overdue invoices have an
   editable reminder that you can copy or download as an `.eml` file.

Search counts messages with a parseable PDF attachment or a direct HTTP(S) URL whose
path ends in `.pdf`. Ordinary marketing links do not qualify. Linked PDFs are not
fetched or verified; link-only emails receive an email check, not invoice extraction.
Search narrows candidates, validates messages, paces requests and retries temporary
Google rate limits. A persistent limit produces a specific retry message.

Phishing warnings emphasize credential requests, payment redirection, deceptive links,
unsafe attachments, and instruction overrides. AI warnings require a defined category
and a quote present in the supplied content. Emailed store receipts, masked card digits,
and marketing content are not sufficient evidence. Quote validation does not prove the
AI interpretation correct. SPF/DKIM/DMARC, domain reputation, and malware scanning are
not implemented. Paid receipts are separate from phishing risk and need no reminder.

## Privacy and limits

Gmail access is read-only. Search does not call AI. **Check email** sends selected
email content and extracted PDF text to the configured provider. The app does not
send emails or create drafts inside Gmail. Keep the server on localhost: the saved
account is shared by the process, not isolated per browser user.

See [the detailed guide](docs/invoice-email.md) for OAuth setup, provider configuration,
PDF limits, and troubleshooting. Never commit keys, OAuth files, real email samples,
or downloaded invoice documents.

## Verify

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests use synthetic documents and mocked Gmail/model transports; no account or API key
is required. The existing FastAPI service in `../app` has its own dependencies and tests.
