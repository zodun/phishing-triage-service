# Gmail invoice reminders

The user approved a dedicated Invoice Email tab on 2026-09-09.

## Flow

The local, single-user app connects to Gmail using a desktop OAuth client and
read-only access. The user searches messages, selects one, and processes its PDF
attachments. Message bodies and attachment text are displayed for review.
An Azure OpenAI or OpenAI model extracts structured invoice fields from each PDF.
The customer comes from the invoice's bill-to section, never automatically from
the email sender. Document and email text are untrusted data, not agent commands.

For each invoice, the app shows customer, recipient, invoice number, currency,
balance, due date, source evidence, and review warnings. Deterministic validation
decides whether a payment reminder is appropriate. A positive balance with a past
due date produces an editable reminder, qualified because a historical invoice
cannot establish current payment status. Paid, future-due, non-invoice, ambiguous,
and incomplete documents do not automatically produce overdue reminders. An
absent recipient can be entered by the user after verification. The app offers an
editable subject/body and an email-file download. It has no sending capability.

## Components

- `invoice_email/gmail.py`: OAuth, message search, MIME body parsing, attachment retrieval.
- `invoice_email/pdf.py`: bounded PDF text extraction and readable failures for scans,
  encrypted, malformed, empty, and oversized documents.
- `invoice_email/extraction.py`: configured model client and structured extraction.
- `invoice_email/models.py`: invoice schema, validation, and reminder construction.
- `invoice_email/workflow.py`: per-attachment processing with isolated failures.
- `invoice_email/ui.py`: connection, search, review, edit, and download controls.
- `invoice_app.py`: standalone local launcher, independent of warranty/Azure demos.
- `main.py`: adds the same tab to the existing app.

## Limits and verification

PDFs require a text layer; image-only or partly image-only PDFs are flagged for OCR
instead of being interpreted from the email body. Attachments are processed in
memory with file/page/text limits. OAuth tokens are stored in a private ignored
directory, and the app is intended for one user on loopback, not public hosting.
Only selected message text and PDFs are submitted to the configured AI provider.
Unit tests cover MIME nesting, attachment encodings, invoice eligibility, prompt
boundaries, unreadable PDFs, partial failures, and the email export. An integration
test uses a real generated PDF through a fake Gmail transport and fake model response.
Live Gmail/model verification requires the user's OAuth consent and configured keys.
