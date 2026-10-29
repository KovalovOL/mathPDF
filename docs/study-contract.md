# Study generation and rendering contract

The current request, document, persistence, and export contract is described in [workspace.md](workspace.md).

## Structured content

A set contains its ID/title, primary document identity, selected original pages, mode, context-document snapshots, item array, notes, and provider/prompt metadata. Each item has a title and question/answer block arrays. Multiple formulas can originate from one page and multiple math blocks can appear in one item.

```json
{
  "kind": "math",
  "latex": "\\sum_{i=1}^{n} a_i",
  "display": true,
  "source": {"document_id": "primary-document-id", "page": 7, "line_start": null, "line_end": null, "quote": null},
  "original_latex": null,
  "change": null
}
```

A text block is `{"kind":"text","text":"Identify this expression."}`. All prose is rendered as text. For an intentional quiz variation, original_latex and change are supplied together; the answer can display the unmodified expression and explain the change. The model's response schema is derived from Pydantic through the OpenAI SDK.

The provider contract also accepts mixed paragraphs as `{"parts":["The coefficient ",{"math":"\\binom{n}{m}"}," counts selections."]}`. They expand into canonical text blocks with locally supplied math delimiters. New answer output uses structured paragraphs/formulas and flashcard questions use one complete prose string; local readers remain tolerant of legacy prose. A prose-only definition can use a compact page-only reference instead of inventing a formula. It expands into optional item-level `source` with the same citation shape, selected-page checks and owner binding as a mathematical block, and appears only in the answer view/export section.

New generation accepts 1–50 requested items and succeeds only with exactly that many validated questions in a single provider request. The completed-result schema has exact array bounds or an explicit insufficient-source result. No model retry or repair call is made; there is no successful partial output. Exact question repeats, missing source formulas and out-of-selection citations are rejected. Flashcard questions ask for recall without answer hints; the central formula belongs to the answer. A front-side formula is not required. Line ranges must be ordered and either have both endpoints or neither. Existing saved sets remain readable. Schema/scope checks do not prove citation accuracy or mathematical correctness.

Each newly generated item supplies `skill` before `question`: `recall`, `meaning`, `conditions`, `application`, `error_diagnosis`, `why_justification`, `counterexample` or `comparison`. Prompt quotas determine the requested difficulty distribution; they do not introduce a classifier or a new validation/retry pass. Problem questions normally vary source inputs, retaining the literal source reference and the changed instance's original expression/edit metadata separately.

New flashcard backs use `from_notes` for source-only content and `explanation` for short AI-added context. Both contain structured blocks. The adapter also builds the existing `answer` array with separate text labels, keeping workspace/export rendering compatible. The live output schema stays strict; its local reader accepts both the new back fields and historical prose/formula shapes in a single response. No renderer changes are required.

## Rendering boundary

`window.MathPDF.renderBlocks(container, blocks, options)` renders every block; `renderMath(container, latex, display)` typesets a single expression. Options control editing, source navigation/labels, and whether citations are links. The renderer is independent of provider and document preparation code. It uses locally served KaTeX HTML plus accessibility MathML, strict errors, disabled trusted HTML commands, and bounded expansion. Invalid math is reported locally while other blocks remain available.

The shared `flashcardSides` helper keeps titles, formula blocks, explanations and citations on the answer side in the workspace and PDF export, including older cards that stored formulas in the question array. Card labels and exported question headings use neutral numbers. The print worker uses the same renderer and fonts with editing disabled and text citations. It waits for fonts and verifies layout before printing. Unsupported math remains readable raw text and never blocks generation. Study formula screenshots are never used. PDF.js canvases preview original PDF pages in the reader and library; study mathematics remains editable typeset text.

The same text/math fragment parser drives rendering and flashcard projection. Delimited inline/display mathematics and recognizable legacy TeX inside a question text block move to the answer view, including unsupported syntax. Surrounding question prose remains on the front. An exact expression already present as an answer formula is not repeated. This projection applies to every provider and old saved sets without changing their stored blocks, citations or variants. Problem question inputs remain visible. It does not detect semantic answer hints expressed entirely in ordinary prose.

## Backward compatibility

Every new release must read all previously supported persisted formats, including saved sets and browser drafts. New study-set payloads include `schema_version: 1`; existing payloads without that field are read as version 1. Reading or displaying an old record does not rewrite it. Explicit saves may add compatible defaults while preserving all content, formulas, source references, variants and metadata.

Evolve formats through compatible defaults or explicit non-destructive upgrades. Keep the historical JSON fixtures in `tests/fixtures/study-sets/` unchanged, adding fixtures for new versions and retaining read/save/render/export coverage for the older ones. Do not remove old readers, silently reinterpret fields or require regeneration of saved content. Breaking read compatibility is allowed only for a major change with the project owner's explicit approval. Approval to implement or deploy a feature does not authorize a compatibility break. Older releases are not required to read newer formats.

The optional `skill`, `from_notes` and `explanation` fields default to `None` when absent and are omitted on serialization when `None`. This preserves the prior normalized item shape and review fingerprint, so opening an old deck resumes its existing round. Empty new section arrays remain explicit. Legacy `answer` blocks, formulas, variants and citations are unchanged; no stored payload migration is performed.

## Prompt boundary

All natural-language LLM instructions are loaded from `formula_lab/prompts/`: system instructions, mode-specific templates, the formula-writing guide, reusable math patterns, context-role instructions, per-attachment labels and comments. Runtime values supply selected-page mapping, file metadata, requested count and user comment. Prompt content hashes accompany each result. Provider adapters add no hidden instruction text. Reusable structures apply across topics without changing source operators, accents, fonts or row/equality order; prompts explicitly distinguish worksheet candidates from true assertions. Source fidelity and mathematical correctness remain unproven by schema compliance or successful typesetting.

## Historical diagnostic routes

Shared diagnostic HTTP routes and the `--pdf` startup option were removed when mandatory Google authentication was introduced. Offline diagnostic Python modules remain separate from the owned document library. No exhaustive formula extraction or storage pass is required by generation.

## Primary references

- [OpenAI file inputs](https://developers.openai.com/api/docs/guides/file-inputs).
- [OpenAI structured output](https://developers.openai.com/api/docs/guides/structured-outputs).
- [KaTeX options](https://katex.org/docs/options).
- [PDF.js examples](https://mozilla.github.io/pdf.js/examples/).
- [Playwright PDF printing](https://playwright.dev/python/docs/api/class-page#page-pdf).
