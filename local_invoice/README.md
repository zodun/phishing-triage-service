# Local Gmail invoice checker

A local, single-user Gradio app for reviewing Gmail emails and PDF invoices.

## Unified workspace

Run both workflows together from the repository root:

```sh
python -m pip install -e . -r local_invoice/requirements-invoice.txt
python local_invoice/workspace_app.py
```

Open http://127.0.0.1:8089. The homepage opens Gmail invoice reminders;
**Email inspection** opens the manual classifier on the same server.
Google and invoice model credentials are configured on the server.
`WORKSPACE_PORT` changes the local port. `invoice_app.py` also launches this unified workspace.

## Read a PDF without Gmail

Open **Or upload a PDF invoice**, choose a text-based PDF, and select
**Read PDF & prepare reminder**. The developer must configure invoice reading on the server. Google credentials are not required for this path. Optional email context
is assessed with the document; sender identity and delivery headers are not verified.
Scanned PDFs still require OCR before upload. Review the extracted facts before
copying or downloading a reminder. The app never sends the email automatically.

## Use the app

1. Select **Continue with Google** and approve read-only Gmail access.
2. Select **Find invoice emails**, choose a message, then **Check this email**.
3. Review the email check, invoice details and editable reminder. Copy or download
   the draft when ready. The app never sends email automatically.

Installation credentials are configured by the developer as described below.

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
send emails or create drafts inside Gmail. Keep the server on localhost: Google tokens are bound to a browser session. This remains a local workspace,
not a public multi-tenant document hosting service.

See [the detailed guide](docs/invoice-email.md) for OAuth setup, provider configuration,
PDF limits, and troubleshooting. Never commit keys, OAuth files, real email samples,
or downloaded invoice documents.

## Verify

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests use synthetic documents and mocked Gmail/model transports; no account or API key
is required. The existing FastAPI service in `../app` has its own dependencies and tests.

## Google sign-in for the unified workspace (developer setup)

End users now use **Continue with Google**. They do not upload credentials or enter
provider keys. Configure these server environment variables before launching:

```sh
GOOGLE_CLIENT_ID=your-web-client-id
GOOGLE_CLIENT_SECRET=your-web-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:8089/auth/google/callback
INVOICE_MODEL_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-provider-key
INVOICE_MODEL=deepseek-chat
```

Use an ignored `local_invoice/.env` or your process environment; never commit these
values. OpenAI is also supported with `INVOICE_MODEL_PROVIDER=openai`, `OPENAI_API_KEY`,
and an appropriate `INVOICE_MODEL`. See the provider configuration in `settings.py`.

In Google Cloud, enable Gmail API, configure the consent screen, and create an
OAuth client of type **Web application**. Register `GOOGLE_REDIRECT_URI` exactly
as an authorized redirect URI (including host, port and path). Add your Gmail as
a test user while the consent screen is in testing. Request only
`https://www.googleapis.com/auth/gmail.readonly`. For a published installation,
complete Google's required consent/verification process and use HTTPS.
[Google's web-server authorization guide](https://developers.google.com/identity/protocols/oauth2/web-server)
describes this configuration.

Launch `python local_invoice/workspace_app.py`. Keep this local app on loopback.
OAuth states are single use, bound to an HttpOnly browser cookie, and expire after
10 minutes. Access/refresh tokens remain server-side in memory; browser sessions
expire after 7 days, or on server restart. Valid access tokens are refreshed without
another sign-in. Disconnect deletes the local session; Google account permissions
can also be removed in the user's Google account settings. This implementation is
for one server process; a multi-worker deployment requires a shared secure session
store. The launcher disables access logs so callback authorization codes are not
written to request URLs in logs.

Manual integration checks: with a configured Google web client, approve and deny
consent; verify account selection, return to Choose Email, search, PDF review,
reminder download, reconnect after revocation, and disconnect. Automated tests use
mocked Google responses and cannot confirm your Cloud Console configuration.
