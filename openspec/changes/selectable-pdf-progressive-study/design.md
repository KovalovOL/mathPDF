# Design

## Context

See proposal.md for motivation. The reader uses vendored PDF.js 6.4.299 and retains the old canvas during resize renders. Generation requests batches of five, repairs invalid items, and enforces the final count. KaTeX is shared by the UI and Chromium PDF export. Prompts live in separate English files.

## Goals / Non-Goals

**Goals:** Preserve the stable reader geometry; make citations useful when model line numbers are unavailable; keep progression consistent across repairs; detect formatting failures before presenting new material.

**Non-Goals:** OCR, arbitrary PDF editing, proof of mathematical correctness, and a guarantee of pixel-identical reconstructed formulas. Older corrupted mixed prose/math blocks cannot always be reconstructed automatically.

## Decisions

1. Add the PDF.js TextLayer above each canvas, with its matching CSS scale and rotation rules. Render text independently and cancel obsolete text work during resize/pruning. Retain the old canvas until replacement is ready. Preserve pages participating in an active selection. A canvas alone cannot provide selection.
2. Use bounded citation quotations to match normalized PDF text, preserving character offsets for DOM ranges. Highlight only unique matches; otherwise navigate to the page. Do not infer physical rows from model line numbers. Keep a viewer-ready handshake so quotations are delivered after an iframe finishes loading.
3. Use a short cancellable animation for explicit citation jumps, respecting reduced motion. Resize anchor restoration remains immediate. A global smooth-scroll rule would interfere with resizing.
4. Add a provider-neutral planning call returning numbered learning goals with topics, activities, source pages, and a rationale for increasing challenge. Generate missing goal slots in batches and return items sorted by slot. Optional item identifiers preserve old saved-set compatibility. Prompt-only instructions inside isolated batches would restart progression.
5. Reject exact and conservative near-duplicates with the same formula signature. Validate plan coverage and variety. Keep the existing exact-count and timeout behavior. Model-assessed difficulty and semantic uniqueness remain imperfect.
6. Preflight candidate formulas using local KaTeX in the existing Chromium runtime, with the same strict settings as the shared renderer. Block external network access. Reject raw TeX in prose and obvious exercise prose in math blocks. Feed safe rejection codes into external repair prompts.
7. Add a conservative legacy renderer for standalone TeX lines; retain ordinary paragraphs and escape all generated prose. No arbitrary provider HTML is executed.

## Risks / Trade-offs

- [Text extraction order and glyph mappings vary] → Match only unique quotations; fall back to a page without asserting a line match.
- [Planning adds latency and cost] → One planning pass normally, at most two; share the existing total deadline and record attempts.
- [Difficulty and paraphrase detection are heuristic] → Use explicit learning goals plus conservative duplicate checks, without claiming mathematical proof.
- [Chromium validation can fail operationally] → Return an actionable error rather than silently accepting unvalidated formulas; reuse the already installed browser.
- [Text overlays consume memory] → Prune distant pages except active selections and cancel stale render work.

## Migration Plan

Deploy with the existing workflow. No database migration is required: new goal identifiers are optional for persisted sets. Rollback restores the previous assets and generator; new metadata is backward compatible.
