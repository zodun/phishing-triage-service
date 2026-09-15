# PhishGuard reference implementation

The user supplied a dark PhishGuard inspection screen and requested that design
for the UI. Apply its navy/cyan palette, compact inspection panels, shield identity,
Geist typography, JetBrains Mono labels, and mobile action/navigation arrangement.
Use real application state rather than the reference's fictional incident scores,
header authentication, sandbox findings, or quarantine controls.

Both interfaces now use the reference palette and typography. The classifier uses
a top brand bar, layered message/assessment panels, and mobile action dock. The
invoice app keeps its working three-step navigation and uses matching dark fields,
uploads, disclosures, composer, and status states. Fonts and licenses are bundled
locally; no Tailwind runtime or external font requests are needed.

Validation: all 80 automated tests pass, lint/format/type checks pass, and WebKit
interaction/layout checks pass from 320 to 1440px for classification, invoice setup,
and a fictional invoice draft. Live preview retains fake-model mode for the
classifier; no real Gmail or model calls are made during visual verification.
