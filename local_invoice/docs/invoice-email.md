# Gmail invoice reminders

This workflow reads actual Gmail messages and PDF attachment bytes, extracts the
invoice customer and payment details, and prepares an editable reminder. You can
download it as an `.eml` file to open in a compatible mail client, or copy the
recipient, subject and body into Gmail.

## Start the standalone app

Use Python 3.11 or later. From this project directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-invoice.txt
.venv/bin/python invoice_app.py
```

Open the local URL printed in the terminal (normally `http://127.0.0.1:7860`; the
app chooses the next available port if that port is occupied).

## Connect your Gmail account

The **Account setup** accordion walks through Google configuration and lets you
import the downloaded Desktop app client JSON directly. Setup status identifies
missing Google/model settings before you try to connect.

1. Create or select a project in the [Google Cloud console](https://console.cloud.google.com/).
2. Enable the **Gmail API** and configure the Google Auth Platform consent screen.
3. For an external app in testing, add your Gmail address as a test user.
4. Create an OAuth client with application type **Desktop app** and download its JSON.
5. In **Account setup**, upload the JSON under **Choose the file you downloaded from Google** and click
   **Save Google file**. Alternatively, copy it to `.credentials/gmail-client.json`.
6. Click **Connect Gmail** on the connection step. Click the **Continue with Google** link
   that appears and finish sign-in within three minutes. It opens in your current
   browser, including Safari. Return to the app when sign-in completes. The callback
   uses a temporary localhost port on the computer running the app.

The app requests `gmail.readonly`, following Google's
[Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python).
It does not request send permission. The download is a local email draft, not a
draft saved in your Gmail account. A private token file is saved at
`.credentials/gmail-token.json` so you can reconnect without signing in every time.
Both credential files are ignored by Git. Keep custom paths outside version control
as well. To change accounts, remove the saved token and reconnect. You can revoke
access in your Google account's third-party connections settings.

Desktop sign-in is for one user running the app locally. Do not publish this app
or expose its port publicly: it uses the connected account for the whole process.
A hosted multi-user version would require per-user OAuth and token storage.

## Configure invoice extraction

For DeepSeek, choose **DeepSeek** under **Your AI service** and
save your DeepSeek API key. The app uses `deepseek-v4-flash` through DeepSeek's
[official OpenAI-compatible API](https://api-docs.deepseek.com/). Advanced options
let you change the model. For environment-based setup, use
`INVOICE_MODEL_PROVIDER=deepseek`, `DEEPSEEK_API_KEY`, and optionally `INVOICE_MODEL`.

Enter the provider, API key, model/deployment, and optional Azure
endpoint under **Account setup → 2. Set up invoice reading**. Click **Save and continue**. These settings are stored with owner-only permissions in
`.credentials/invoice-model.json`; the API key is cleared from the input after
saving. Saved settings take precedence over environment variables. Saving validates
the configuration format; credentials are checked by the provider when reading an invoice.

The `.env` configuration below remains available as an alternative.

Create `.env` in this project directory. For an OpenAI account:

```dotenv
INVOICE_MODEL_PROVIDER=openai
OPENAI_API_KEY=your-key
INVOICE_MODEL=gpt-4.1-mini
```

Or use the existing Azure OpenAI settings:

```dotenv
INVOICE_MODEL_PROVIDER=azure
OPENAI_AGENTS_ENDPOINT=https://your-resource.openai.azure.com/
OPENAI_AGENTS_API_KEY=your-key
OPENAI_AGENTS_API_VERSION=2024-08-01-preview
INVOICE_MODEL=your-deployment-name
```

Use a deployment that supports chat completions with JSON output. Selected email content (including sender, reply address, subject, links, and body)
and extracted PDF text are passed to the configured AI provider when you click
**Check email**. Search results alone do not trigger model calls.

Optional `.env` settings:

```dotenv
GMAIL_CLIENT_SECRET_FILE=.credentials/gmail-client.json
GMAIL_TOKEN_FILE=.credentials/gmail-token.json
INVOICE_APP_PORT=7860
```

Restart after changing `.env`. Settings saved through the interface apply immediately.

## Connection troubleshooting

- **Google setup needed:** download a Desktop OAuth client from Google Cloud and
  import it in Account setup. A Gmail address/password alone cannot replace this file.
- **Wrong client type:** create a Desktop app client, not a Web app or service account.
- **Google is temporarily limiting requests:** automatic retries have been exhausted.
  Wait a minute before searching again; reconnecting does not reset the rate limit.
- **Access blocked / permission denied:** enable the Gmail API and add your Gmail address to the
  consent screen's test users. Check any error shown by Google during sign-in.
- **Timed out:** click Connect Gmail again and use the sign-in link within three minutes.
- **Invoice model settings missing:** add your OpenAI, DeepSeek, or Azure OpenAI credentials
  in Account setup; Gmail sign-in alone does not configure invoice extraction.

## Use the workflow

The interface shows one step at a time:

- **Connect Gmail:** finish one-time setup if needed, then choose your Google account.
- **Choose an invoice:** click **Find invoice emails**, choose a message, and click
  **Check email**. Use **Search options and email signature** to change the date range or search scope.
- **Review your email:** check the invoice summary and customer, then edit the message.
  Copy it into Gmail or use **Download email draft**. The original document is under
  **See the original invoice**.

To process another message, use **Choose another invoice**. A failed sign-in stays
on the connection screen; a failed email read stays on the invoice screen.

If an email contains multiple PDFs, **PDF to review** lets you choose each one.
Editing any draft field clears the old download so you can regenerate it with your
changes. The app reads the customer from the invoice, not the forwarding address.

The reminder names the customer, invoice, stated balance, and due date. Its wording
accounts for payments made after the invoice was issued. It does not add late fees,
bank instructions, or legal threats. Missing recipient addresses remain blank for
you to verify and enter. Missing core invoice details, ambiguous dates/currency,
paid invoices, and dates that have not passed prevent automatic reminder generation.

## What the search includes

The count includes messages with a parseable PDF attachment or a direct HTTP(S)
link whose path ends in `.pdf`. Shopping and unsubscribe links do not qualify.
Linked files are not downloaded or verified. An email with only a PDF link can
receive an email check, but invoice extraction requires an attachment.

## PDF and processing limits

- Up to 50 search results, 10 PDF attachments per selected email, 15 MB and 30 pages
  per PDF, and 100,000 extracted characters per PDF.
- PDFs need a text layer. Image-only scans and blank/unreadable pages are flagged
  for OCR; encrypted or malformed files are flagged for replacement. The parser
  cannot extract text from images, as explained in the
  [pypdf text extraction documentation](https://github.com/py-pdf/pypdf/blob/main/docs/user/extract-text.md).
- Each PDF should contain one invoice. Split combined invoice bundles first.
- A failed attachment is reported independently; the other PDFs can still produce
  reminders. Check all attachments in the selector for errors.
- The current date uses the machine's local timezone. Extraction can make mistakes;
  quotes are provided for review, and payment status must be checked against your records.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests include a real PDF through a fake Gmail transport/model, nested MIME parts,
forwarded invoice recipients, extraction refusal, missing/invalid fields, invoice
eligibility, PDF failures, UI construction, and editable email export. Live Gmail
and model calls require your configured credentials and Google consent.
