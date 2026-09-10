# Gmail Invoice Email Implementation Plan

**Goal:** Read actual Gmail PDF attachments and produce editable customer reminders.

**Architecture:** Keep Gmail transport, PDF decoding, AI extraction, and reminder
rules separate. Add a Gradio tab and a standalone local launcher using the same UI.

**Tech Stack:** Python, Gradio, Google Gmail API/OAuth, pypdf, Pydantic, OpenAI SDK.

## Tasks

- [x] Add failing standard-library unittest coverage in `tests/test_invoice_email.py`
  for a forwarded invoice, nested MIME bodies, externally stored attachment bytes,
  valid/invalid invoice fields, date/balance eligibility, and per-PDF failures.
  Run `.venv/bin/python -m unittest discover -s tests -v` and observe missing feature.
- [x] Implement `invoice_email/models.py`, `pdf.py`, `gmail.py`, `extraction.py`, and
  `workflow.py` to satisfy those tests. Require customer and invoice facts from the
  attachment, validate dates/amounts, retain evidence, reject missing core fields,
  and qualify any reminder's payment-status language.
- [x] Implement `invoice_email/ui.py` and `invoice_app.py`; add the tab to `main.py`.
  Use local OAuth connection, bounded Gmail search, message/attachment selectors,
  source text preview, editable drafts, and RFC email export. Clear stale outputs
  when the selection changes. Keep email content out of executable HTML/Markdown.
- [x] Add dependency/setup instructions and ignored credential paths. Document the
  desktop OAuth configuration, model credentials, startup command, scanned-PDF
  limitation, and local single-user scope in `docs/invoice-email.md`.
- [x] Run the complete test suite, compile new modules, construct the Gradio UI,
  and smoke-test the local server. Review that no send tools exist, actual bytes
  reach the PDF parser, and incomplete/paid invoices do not create reminders.

No repository-level branch or commit changes: this downloaded project resolves to
a parent Git repository covering the user's home directory. Keep changes confined
to the supplied project.

## Verification results

25 tests pass, including the two regressions identified by independent review
(source controls changing during analysis, and MIME charset decoding). The HTTP
smoke test checks the actual local page/config, no-selection validation, and the
ineligible-export guard. Positive email export is checked by reopening its cached
RFC email file. Python compilation passes. Browser discovery returned no available
browser, so visual testing was unavailable. Live Gmail/model calls await user
configuration and consent; no email was sent.
