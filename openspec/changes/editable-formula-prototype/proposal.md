# Proposal

## Why

The platform needs an editable renderer for mathematical content returned by an LLM. The existing source-font experiment is useful for comparison, but generation must accept complete selected PDF pages without requiring an exhaustive formula extraction or storage pass.

## What Changes

- Render every mathematical block in a structured LLM response as editable mathematical text, including multiple formulas on the same page or card.
- Add selected-page PDF input, two study modes, an OpenAI provider behind an interface, and external prompt resources.
- Keep page references and optional model-reported line references only for formulas actually used in study material.
- Show all detected page candidates when the optional source inspection is opened; do not save candidates automatically.
- Replace the decorative workbench with a minimal English interface for generation, PDF comparison, formula editing, and answer reveal.
- Preserve the existing source-font extraction and explicit-save APIs as optional diagnostic tools. Their earlier measurements do not establish fidelity of LLM transcription.

## Capabilities

### New Capabilities

- `editable-formulas`: Render and edit source-linked mathematical output, with optional PDF layout inspection.

### Modified Capabilities

None. The existing `pdf-study-workspace` change remains the platform integration plan and is reconciled with this workflow.

## Impact

- FastAPI still serves one configured local PDF; Google accounts and the private file library remain in the platform change.
- Add a local HTML/MathML typesetter and canonical TeX for LLM output. The source-font presentation format remains available separately.
- Selected pages are copied into an in-memory PDF, preserving page content rather than creating formula screenshots.
- Generated responses are transient in this prototype. No exhaustive formula catalog is required.
- Correct rendering of TeX does not prove faithful transcription or identical PDF typography. Unchecked output must remain identified as unchecked.
