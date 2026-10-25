# Proposal

## Why

The PDF reader currently paints pages without selectable text. Study generation can repeat the same learning goal and expose malformed TeX, making the material harder to use and trace back to its source.

## What Changes

- Add a selectable PDF.js text layer while preserving stable resizing and lazy rendering.
- Animate citation navigation to the original source page.
- Generate the complete varied, progressively ordered set in one provider request, with no separate planning call.
- Supply a detailed external formula-writing guide and validate the single returned set locally without automatic model repair requests.
- Safely render unambiguous standalone TeX lines in older saved material.
- Use a compact provider response to reduce output tokens; retain exact counts, bounded owner-scoped progress, cancellation, and clear terminal failures.

## Capabilities

### New Capabilities

- `pdf-reading`: Selectable document text and animated source-page navigation.
- `study-quality`: Source-grounded progressive study sequences and mathematical formatting validation.

### Modified Capabilities

None. Main specifications have not yet been populated.

## Impact

The PDF iframe, workspace messaging, shared math renderer, generation models, provider abstraction, and external prompt files change. The existing Playwright/Chromium dependency supplies KaTeX validation; no new runtime dependency is needed. Each generation makes exactly one provider request, with SDK retries disabled. Existing saved sets remain readable.
