# Proposal

## Why

The PDF reader currently paints pages without selectable text. Study generation can repeat the same learning goal and expose malformed TeX, making the material harder to use and trace back to its source.

## What Changes

- Add a selectable PDF.js text layer while preserving stable resizing and lazy rendering.
- Animate citation navigation to the original source page.
- Generate the complete varied, progressively ordered set in one provider request, with no separate planning call.
- Supply a detailed external formula-writing guide and render formulas on display with a readable raw-text fallback, without blocking the set or requesting model repairs.
- Safely render unambiguous standalone TeX lines in older saved material.
- Keep flashcard fronts question-only; show answer formulas, titles, explanations and source citations after flipping, including older cards and PDF exports.
- Separate inline math from prose in provider output, reuse a source-preserving LaTeX pattern guide, and recover unambiguous older TeX fragments locally without model retries.
- Use a compact provider response to reduce output tokens; retain exact counts, bounded owner-scoped progress, cancellation, and clear terminal failures.

## Capabilities

### New Capabilities

- `pdf-reading`: Selectable document text and animated source-page navigation.
- `study-quality`: Source-grounded progressive study sequences and mathematical formatting validation.

### Modified Capabilities

None. Main specifications have not yet been populated.

## Impact

The PDF iframe, workspace messaging, shared math renderer, generation models, provider abstraction, and external prompt files change. The existing Playwright/Chromium dependency remains for PDF export; no new runtime dependency is needed. Each generation makes exactly one provider request, with SDK retries disabled. Existing saved sets remain readable.
