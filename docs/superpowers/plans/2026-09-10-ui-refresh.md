# UI refresh implementation plan

Goal: Improve both existing interfaces while preserving classification and invoice eligibility rules.

Design: People reviewing email at a desk need readable, calm working surfaces. Retain blue actions, neutral surfaces, system fonts, and labeled risk colors. The classifier uses adjacent input and results on desktop, stacked on mobile. Invoice Email uses a centered, three-step workspace with progressive setup. Preserve system dark mode on the classifier; use a consistent light workspace for invoice document review.

- [x] Classifier: rebuild app/web/index.html layout with a persistent result placeholder, semantic form, live status, explicit errors, keyboard focus, and wrapping evidence. Reject empty input, prevent duplicate submissions, validate HTTP responses, and invalidate results on edits.
- [x] Invoice app: consolidate local_invoice/invoice_email/workspace.css; eliminate obsolete sidebar selectors; constrain reading width; improve stepper, setup, field focus, and narrow layouts. Refine appearance.py and UI labels without changing provider, Gmail, or drafting rules.
- [x] Verify: exercise classifier success, failure, edits, and duplicate submissions; run Python suites for both apps; lint edited files; inspect rendered pages if a browser is available.

Validation: 8 Node UI tests, 15 service tests (94% coverage), 57 invoice tests, HTTP invoice smoke test, Ruff lint/format, and mypy all passed. No Gmail or live model calls were made. A connected browser was unavailable, so visual rendering and viewport checks remain for review.
