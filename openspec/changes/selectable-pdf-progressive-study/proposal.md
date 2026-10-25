# Proposal

## Why

The PDF reader currently paints pages without selectable text. Study generation can repeat the same learning goal and expose malformed TeX, making the material harder to use and trace back to its source.

## What Changes

- Add a selectable PDF.js text layer while preserving stable resizing and lazy rendering.
- Animate citation navigation and highlight a uniquely matched source quotation when available.
- Plan a varied sequence of learning goals before generating items, ordered from easier to harder.
- Reject repeated questions, raw TeX in prose, and formulas that fail the application's KaTeX renderer; repair rejected items within the existing bounded generation budget.
- Safely render unambiguous standalone TeX lines in older saved material.

## Capabilities

### New Capabilities

- `pdf-reading`: Selectable document text and source navigation with optional quotation highlights.
- `study-quality`: Source-grounded progressive study sequences and mathematical formatting validation.

### Modified Capabilities

None. Main specifications have not yet been populated.

## Impact

The PDF iframe, workspace messaging, shared math renderer, generation models, provider abstraction, and external prompt files change. The existing Playwright/Chromium dependency supplies KaTeX validation; no new runtime dependency is needed. Planning adds one model request in the normal case. Existing saved sets remain readable.
