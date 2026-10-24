# Editable formula prototype: feasibility report

Date: 2026-10-24. This report describes an implemented local experiment, not a completed platform integration or a universal PDF fidelity guarantee.

**Scope after the workflow revision:** This is historical evidence for the optional source-font diagnostic renderer. The primary flow now sends complete selected PDF pages to an LLM and renders its TeX output. These measurements do not validate LLM transcription or KaTeX typography. The earlier single-selection workbench and its browser script have been replaced; all page candidates can now be inspected without saving them. See [the current contract](study-contract.md).

## Input and implementation

The supplied `main.pdf` has SHA-256 `9e2c6389508da9cd771a0c52ceb06ee621bc2a5d410c99ca96668b5718b9d9b3` and 59 pages. The experiment reads source text operations and source fonts, records a presentation group, and renders it as selectable HTML text with CSS rules. Embedded Type 1 fonts are converted into OpenType fonts. Formula content contains no bitmap, PDF crop, canvas, or SVG glyph path. The original PDF viewer is a separate comparison reference.

The reusable representation is a JSON presentation tree with text nodes, source font/glyph identities, baseline positions, sizes, thin rules, and source provenance. It is not yet a semantic equation tree. A sign variant changes one identified node and records its source formula and transformation; all unrelated nodes are preserved.

Browser baseline rounding was an observed source of error. The renderer measures the actual browser baseline and scales individual positions and font sizes at the requested display scale, avoiding scale-amplified layout rounding.

## Coverage audit

The full document audit completed with:

| Measure | Observed result |
| --- | --- |
| Pages processed | 59 |
| Extracted text nodes | 56,975 |
| Source font/encoding profiles converted | 18, with no font-conversion warnings |
| Proposed formula regions | 322 heuristic candidates, not a verified formula count |
| Pages with unmapped source glyphs | 5, 29, 42, 47, 48, 51 |
| Graphics classified outside the supported text/thin-rule model | 191 regions across the document |

The remaining unmapped glyphs are horizontal-brace tip components in `txexs` and an `a19` drawing glyph in `LINE10`. The prototype leaves them explicitly unsupported instead of assigning an unreliable Unicode meaning. Unsupported graphics are checked against the selected formula region; an unrelated diagram elsewhere on the page does not by itself invalidate a formula.

Candidate detection is not a complete formula detector. It can miss inline expressions, combine adjacent expressions, or include surrounding punctuation. Explicit PDF-coordinate selection is available. No candidate precision/recall score has been measured.

Audit command:

```sh
uv run --extra dev python scripts/scan_pdf.py --pdf main.pdf
```

The detailed local audit is written to `artifacts/scan.json`.

## Browser and source comparison

The browser checks ran in desktop Chrome on macOS using Playwright 1.62.1. They exercised a simple membership expression, a fraction with large delimiters and number-set symbols, indexed sum/product notation with large operators, and a multiline derivation with fractions. All four cases loaded their source fonts, produced text nodes, and contained zero image/canvas/SVG elements inside formula content.

Source-reference images were generated with PDFium for QA only. Both source and browser samples used 4 pixels per PDF point. The comparison threshold classified grayscale values below 160 as ink. The coverage column is the smaller of the two directional ink-coverage scores allowing one neighboring pixel, equivalent to 0.25 PDF point at that scale. It is not pixel equality or a semantic correctness score.

| Case | Source page | Text nodes | CSS rules | Raw ink-mask IoU | Symmetric ink coverage within 1 px | Mean grayscale absolute difference (0-255) |
| --- | --- | --- | --- | --- | --- | --- |
| Membership | 4 | 3 | 0 | 0.8374 | 1.0000 | 5.600 |
| Fraction and delimiters | 4 | 15 | 1 | 0.7388 | 1.0000 | 4.945 |
| Sum/product and indices | 7 | 38 | 0 | 0.8107 | 1.0000 | 2.731 |
| Multiline fractions | 15 | 93 | 4 | 0.7241 | 1.0000 | 3.499 |

The samples preserve the tested source glyph shapes and presentation closely, with every thresholded ink pixel within one pixel of the other rendering. They are not pixel-identical. PDFium/browser rasterization, crop sampling, and the omission of Type 1 hint programs during outline conversion can contribute to the remaining differences; their individual contributions were not isolated.

The real UI was also checked at desktop and 390-pixel mobile widths. The test created a plus-to-minus variant, confirmed that the original rendered text remained unchanged, checked stored lineage, and reopened the workbench with saved records present. No browser page errors or document-wide horizontal overflow were observed. Wide formulas intentionally scroll inside their formula panel.

Evidence can be regenerated with the commands in the README. Local outputs include `artifacts/browser/workbench.png`, `mobile.png`, per-formula browser and PDF reference PNGs, `results.json`, and `comparison.json`. Reference and screenshot images are test artifacts only; they are not used to display study formulas.

## Automated checks

Nineteen Python tests passed. They cover source-font Unicode coverage, source-coordinate preservation, fraction rules, unsupported fonts, source-graphic and clipping warnings, invalid selections, original immutability, variant lineage, unchanged nodes, unsupported edits, document isolation, atomic persistence round-trips, restart behavior, review state, JSON export, font serving, and file-route boundaries.

The suite emits one upstream Starlette deprecation warning about its current HTTPX test-client integration. It did not cause a failure. Browser checks passed for the four representative formula cases and the real sign-edit flow. The documented `uv run formula-lab --pdf main.pdf --port 8765` command served the local workbench and original PDF.

## Integration decision

The experiment demonstrates a working editable HTML presentation mechanism and a traceable sign change using the supplied source typography. It is suitable for user review and further mechanism work as an independent package.

It does not yet fulfill a universal exact-fidelity promise for every formula or PDF. Before production integration:

1. Resolve compound-brace glyph assembly and unsupported notation cases or establish an explicit correction workflow.
2. Improve candidate boundaries and inline-formula detection; retain source-review controls.
3. Define mathematical structure for transformations beyond a targeted sign edit. The presentation tree alone does not provide algebraic reasoning, arbitrary edits, or general reflow.
4. Repeat fidelity acceptance on the supported browser/device set and additional PDFs. Do not equate a four-case visual result with coverage of all extracted candidates.
5. Integrate the formula records and associated font assets with the platform's database, private storage, identity, and generation boundaries.

All extraction records start unverified. Human acceptance is recorded as a review state; it is not an automatic claim of universal fidelity. A record with unresolved extraction warnings cannot be marked accepted through the workbench API.
