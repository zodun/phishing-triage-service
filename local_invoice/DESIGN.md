# Invoice Email workspace

## Context

A user at a desk in daylight reads invoice documents and edits correspondence in
Safari. A bright working surface with a darker navigation area keeps text readable
and gives the application stronger hierarchy.

## Visual system

Retain the existing project's blue accent family. Use an ink/navy sidebar, cool
neutral page background, white document surfaces, and a clear blue primary action.
Represent tokens with OKLCH. Use system sans-serif typography, compact form labels,
generous reading space, and 10–12px panel radii. Status colors have text labels.

## Structure

A compact header and a centered, three-step flow: Connect Gmail, Choose an invoice,
Review your email. Show only the current step. One-time setup is collapsed until
requested; after configuration the first screen has a single Connect Gmail action.
Search options, source documents, and extraction JSON are secondary disclosures.
The review step prioritizes the editable message and a plain-text invoice summary.

## Interaction

Show onboarding when credentials are absent. Provide direct Google setup links,
client JSON import, model configuration, and an explicit Google sign-in link.
Lock source controls during processing. Use 160ms state transitions with reduced
motion support. No fabricated dashboard statistics or decorative animations.
