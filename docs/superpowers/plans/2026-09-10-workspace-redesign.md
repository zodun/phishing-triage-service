# Workspace redesign

The first UI revision preserved a landing-page structure and excessive Gradio field framing. The user requested a substantial redesign with a specialist design partner.

Design review: use a compact navigation rail, a white task canvas, tightly related type sizes, and restrained blue actions. Remove marketing copy, floating panel stacks, and decorative icon tiles. The classifier becomes an editor with an adjacent inspector. Invoice Email retains its real three-step workflow and uses a grouped email composer.

Implementation: revise app/web/index.html; redesign local_invoice/invoice_email/{ui.py,appearance.py,workspace.css}; configure theme and CSS in local_invoice/invoice_app.py. Preserve API behavior, safe text rendering, Gmail permissions, and invoice eligibility.

Verification: render desktop/mobile initial, setup, and result states with WebKit; exercise samples and classification; inspect a fictional invoice fixture; run Node regressions, both Python suites, HTTP smoke checks, lint, and type checks. No live Gmail or model calls are needed for design validation.

Completed validation: WebKit initial and result renders, real sample classification, fictional invoice connection/search/review flow, and no clipped content at 320, 390, 768, 1024, and 1440px. All 80 automated tests, HTTP invoice smoke test, Ruff, mypy, and diff checks passed. The classifier preview runs with simulated AI results; invoice visual fixtures are isolated from Gmail.
