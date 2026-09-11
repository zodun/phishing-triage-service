# PhishGuard invoice review

Use the user's supplied PhishGuard HTML as the visual reference: dark navy canvas
(#0f131d), layered inspection surfaces (#171b26, #1c1f2a), deepest inset fields
(#0a0e18), cyan primary actions (#4cd7f6 with #003640 text), pale body text
(#dfe2f1), and coral warning states. Geist carries the body and headings;
JetBrains Mono carries compact technical labels. Fonts are bundled locally under
their included SIL Open Font Licenses.

Retain the tested desktop workflow rail and compact mobile step navigation. Main
content shows the actual connection, invoice selection, and review workflow.
Group the draft into an email document. Show real phishing findings and invoice
facts; the reference's simulated SOC metrics, authentication verdicts, sandbox
results, and quarantine actions are not service capabilities.

Use 6–8px corners, compact disclosures, clear focus rings, 40px desktop and 44px
mobile controls, and visible labeled status colors. Preserve browser zoom and
native scrolling. The classifier also adopts the reference's mobile action dock
and bottom navigation using its actual inspection, assessment, and API links.

Load global CSS through Gradio's launch-level HTML head to avoid its selector
rewriting inside media queries. Disable default presentation CSS on custom HTML
components. Preserve phishing and drafting eligibility rules, read-only Gmail
access, and reduced-motion behavior.
