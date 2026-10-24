# Design

## Context

See proposal.md. The source-font experiment renders PDF glyph operations as HTML. The user clarified that the main integration boundary is LLM mathematical output. Selected PDF pages can go directly to the model; a complete extracted formula inventory is unnecessary.

## Goals / Non-Goals

**Goals:** Render multiple editable mathematical blocks; retain references for used formulas; accept complete selected pages; provide a minimal English generation and practice UI; preserve optional source inspection.

**Non-Goals:** Google login and private library integration in this prototype, OCR, symbolic algebra, mandatory formula cataloging, or an unsubstantiated guarantee of exact source typography.

## Decisions

### Treat structured study content as the rendering boundary

An item has question and answer blocks. A block is plain text or TeX math; an item and a response can contain multiple math blocks. Math blocks retain a PDF page, optional line range and source quote, and optional original TeX plus a description of an intentional quiz change. Preserve the source version when the learner previews a local edit.

Use locally served KaTeX HTML/MathML output for supported TeX. Preserve alignment, fractions, scripts, font variants, and delimiters in the TeX rather than normalizing notation. Treat prose as text, display unsupported-math errors locally, disable trusted HTML commands, and never inject model-supplied HTML. KaTeX mathematical decorations are not screenshots of PDF formulas.

Rendered TeX and source fidelity are separate concerns. Keep the original PDF visible and describe transcriptions as unchecked. The original requirement for source notation and formatting remains a target; generic typesetting alone does not establish identical PDF fonts or spacing. The earlier source-font report applies only to that separate experiment.

### Pass complete selected pages through a provider interface

Copy selected original pages into an in-memory PDF with pypdf. Do not extract page text or discover formulas as a prerequisite. A generation service owns selection limits, original-page mapping, content validation, and response metadata. An OpenAI adapter sends PDF input through the Responses API with structured output; another provider can implement the same interface.

All natural-language LLM instructions live under `formula_lab/prompts/`, including system instructions and mode-specific task templates. Load and hash resources before composing runtime data. Credentials are loaded server-side from the environment or `.env`. Limit selected pages and output size; do not silently retry billable requests.

### Keep citations lightweight and honest

Validate citations against original selected PDF page numbers. Lines are nullable and explicitly model-reported, since ordinary PDFs need not have stable line numbers. Request a source quote to help locate the expression. Never invent a line when uncertain or claim that scope validation proves citation correctness.

Only formulas included in a response carry these references. No formula catalog or mandatory save/review operation stands between PDF input and generation.

### Keep optional source inspection separate

The PDFMiner/FontTools presentation module remains available for investigating typography. Page inspection displays every heuristic candidate without saving it. Detection can miss or merge regions and is not a complete formula inventory. Legacy explicit-save, review, and variant APIs remain compatible; the main UI no longer exposes a saved-formula catalog.

### Minimize the interface

Use English for labels, errors, titles, placeholders, and accessibility text. Keep document preview/download, page selection, mode/count, generation status, study items, source links, answer reveal, formula editing, and optional rendering inspection. Remove the decorative hero, badges, section numbers, slogans, and redundant footer.

## Risks / Trade-offs

- LLM transcription can change notation -> Keep output unchecked, source links visible, and TeX editable.
- Generic fonts can differ from the PDF -> Do not claim exact fidelity; retain the source-font investigation.
- Model line references can be inaccurate -> Label them as model-reported and allow null lines.
- Unsupported TeX can affect one expression -> Keep a local error and its source without hiding other formulas.
- Provider timeout or invalid output -> Return a clear error without partial or fabricated success.

## Migration Plan

Retain local diagnostic records and APIs. The new study flow does not write to the formula store. Platform integration will persist study sets in SQLite and obtain PDFs through Garage. No public deployment or authentication is introduced here.
