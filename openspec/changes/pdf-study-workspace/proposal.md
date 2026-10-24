# Proposal

## Why

University mathematics notes are difficult to turn into reusable study material by hand. This change introduces a personal web workspace for storing lecture PDFs and creating grounded practice material from selected pages, with the visual fidelity of mathematical notation treated as a core requirement.

## What Changes

- Add Google-based account sign-in and a user-owned PDF library.
- Let users upload, preview, download, and select a PDF or a page range for study.
- Generate two kinds of study material from selected source pages: formula quiz cards and complete mathematical problems.
- Let users work through generated material and reveal or check answers.
- Provide full-document browsing, file/result tabs, a horizontally movable pane divider, and physical flip cards.
- Attach PDF, TXT/Markdown, and image context with per-PDF ranges chosen immediately before generation.
- Save generated study sets and export their questions and answers as formatted PDFs.
- Represent formulas as editable mathematical text rendered in HTML with the source PDF's notation and formatting preserved.
- Support deliberate formula modifications for quizzes, such as a changed sign, while retaining the original formula and recording the transformation.
- Send complete selected PDF pages to the model and render structured text/math output, including multiple formulas per page and per study item.
- Keep page references and optional model-reported lines for formulas actually used; do not require storing all formulas discovered in a PDF.
- Put text-generation providers behind an application interface so the provider can be changed later.
- Keep all LLM system prompts and task/instruction templates in separate, version-controlled files.

## Capabilities

### New Capabilities

- `user-authentication`: Sign in with Google and access a user's own library and study material.
- `pdf-library`: Store and manage PDFs, preview and download them, and select source pages.
- `study-content`: Generate and practice formula cards and problem sets using editable source formulas and traceable quiz variants.

### Modified Capabilities

None.

## Impact

- Proposed backend: Python and FastAPI, serving both the API and frontend assets.
- Proposed frontend: HTMX, Alpine.js, and Pico CSS.
- Proposed persistence: SQLite for application metadata and an S3-compatible object store such as Garage for PDF binaries.
- Proposed generation: an LLM abstraction with OpenAI as the initial provider.
- Formula handling uses editable TeX and HTML/MathML output. PDF screenshots and crops are not study-formula content. The original PDF viewer is independent.
- Source references retain the PDF and original page, with optional model-reported lines and a source quote. A quiz variant retains the original expression and its intentional modification within the study item.
- Source notation and typography remain the fidelity target. Correct TeX rendering alone does not prove identical PDF typography or accurate transcription; unchecked output must remain identified.
- Prompt loading and version tracking belong to the generation layer; provider adapters receive already composed messages.
- The local workspace now provides managed documents, context attachments, SQLite study sets, tabbed practice, and PDF printing. This platform change still covers account isolation, Garage integration, and deployment. The supplied `main.pdf` is a 59-page digital document; scans and handwritten notes remain outside version one.
