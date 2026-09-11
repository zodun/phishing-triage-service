# Invoice Email workspace

A person reviewing invoices at a desk in daylight needs a readable document workspace, clear progress, and one next action.

Use a 216px pale neutral rail for the product identity and the actual three-step workflow. At 800px and below, it becomes a compact header and horizontal progress list. Main content is white, left-aligned, and bounded to a comfortable reading width. Avoid outer cards and marketing headlines.

Use system sans-serif typography: 24px page title, 18px section headings, 14px body and inputs, 12–13px secondary text. Retain the blue primary action and current-step highlight. Controls use 6px corners, a clear border, and 40px desktop / 44px mobile targets. Status colors always accompany text.

Connection and setup controls are compact, with secondary configuration in disclosures. The review screen groups recipient, subject, and message into an email document. Source material remains accessible below the draft. Existing phishing and eligibility rules determine whether the composer appears.

Load workspace CSS in a style element through Gradio's launch-level `head` option. Gradio 6's CSS scoping rewrites root selectors inside media queries, so these application-level layout rules must remain unscoped. HTML components carry semantic content only. Use a system-font Base theme to avoid external font loading and conflicting decorative defaults. Respect reduced motion and provide visible keyboard focus.
