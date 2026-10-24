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

The service rejects citations outside the selected primary document/pages, missing question formulas on flashcards, and more items than requested. Empty output needs an explanation. Line ranges must be ordered and either have both endpoints or neither. Schema/scope checks do not prove citation accuracy or mathematical correctness.

## Rendering boundary

`window.MathPDF.renderBlocks(container, blocks, options)` renders every block; `renderMath(container, latex, display)` typesets a single expression. Options control editing, source navigation/labels, and whether citations are links. The renderer is independent of provider and document preparation code. It uses locally served KaTeX HTML plus accessibility MathML, strict errors, disabled trusted HTML commands, and bounded expansion. Invalid math is reported locally while other blocks remain available.

The print worker uses the same renderer and fonts with editing disabled and text citations. It waits for fonts and verifies layout before printing. Study formula screenshots are never used. PDF.js canvases belong only to the original document reader.

## Prompt boundary

All natural-language LLM instructions are loaded from `formula_lab/prompts/`: system instructions, mode-specific templates, context-role instructions, and per-attachment labels. Runtime values supply selected-page mapping and file metadata. Prompt content hashes accompany each result. Provider adapters add no hidden instruction text.

## Historical diagnostic routes

With an explicit `--pdf` argument, `GET /api/pages/{page}/formulas` returns all heuristic source-font candidates for that diagnostic PDF without saving them. These source-inspection routes are enabled only for that optional startup mode, separate from generation and absent from the normal workspace UI. Normal startup requires no PDF. Explicit-save/review/variant/export APIs continue to support older local diagnostic records in the optional mode. No exhaustive formula extraction or storage pass is required by generation.

## Primary references

- [OpenAI file inputs](https://developers.openai.com/api/docs/guides/file-inputs).
- [OpenAI structured output](https://developers.openai.com/api/docs/guides/structured-outputs).
- [KaTeX options](https://katex.org/docs/options).
- [PDF.js examples](https://mozilla.github.io/pdf.js/examples/).
- [Playwright PDF printing](https://playwright.dev/python/docs/api/class-page#page-pdf).
