# Application audit — 2026-09-15

## Fixed and verified

- Replaced navy/cyan styling with a shared monochrome palette and restrained amber warnings.
- Added repository links to inspection, invoice review, and setup pages.
- Corrected hosted Google setup instructions and callback URL; retained local instructions locally.
- Routed workspace model-setup buttons to the functioning setup guide instead of an inactive settings panel.
- Failed provider extraction now clears the reassuring assessment and reports an incomplete review.
- Corrected setup-page overflow at phone widths.
- Configured the production Google callback and invoice provider in Vercel.

Validation: 16 API/classifier tests, 72 invoice/OAuth tests, 8 browser-script tests;
Ruff and mypy; WebKit layout checks at 390, 768, and 1440 pixels for
/invoices/, /inspect, and /help. External Google and paid model calls were not exercised.

## Outstanding release blockers

1. Production has no GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, or DEEPSEEK_API_KEY.
   Add those privately in Vercel, register the exact callback in Google Cloud,
   and redeploy. Never paste secrets into chat or commit them.
2. OAuth pending state, account sessions, and Gradio analysis state are held in
   process memory. Vercel can restart or route requests to different instances.
   A durable shared session store and a workflow backend without instance-local
   Gradio queue/state are required for reliable cloud inbox processing.
3. Complete a real, authorized Gmail login → attached PDF → extracted invoice →
   reviewed draft → downloaded .eml acceptance test after those blockers are resolved.

This audit does not certify that every possible defect is eliminated. The hosted
interface is available for review; live cloud mailbox workflows are not release-ready.
