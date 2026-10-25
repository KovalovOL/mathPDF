# Design

## Context

See proposal.md for motivation. The reader uses vendored PDF.js 6.4.299 and retains the old canvas during resize renders. Generation uses small batches, repairs invalid items, and enforces the final count. KaTeX is shared by the UI and Chromium PDF export. Prompts live in separate English files.

## Goals / Non-Goals

**Goals:** Preserve the stable reader geometry; make citations useful when model line numbers are unavailable; keep progression consistent across repairs; detect formatting failures before presenting new material.

**Non-Goals:** OCR, arbitrary PDF editing, proof of mathematical correctness, and a guarantee of pixel-identical reconstructed formulas. Older corrupted mixed prose/math blocks cannot always be reconstructed automatically.

## Decisions

1. Add the PDF.js TextLayer above each canvas, with its matching CSS scale and rotation rules. Render text independently and cancel obsolete text work during resize/pruning. Retain the old canvas until replacement is ready. Preserve pages participating in an active selection. A canvas alone cannot provide selection.
2. Use source-page citations with a viewer-ready handshake and settled viewport measurement. Following the user's revised preference, remove quotation matching and row highlighting. Keep the text layer for selection/copying, independently of source navigation.
3. Use a short cancellable animation for explicit citation jumps, respecting reduced motion. Resize anchor restoration remains immediate. A global smooth-scroll rule would interfere with resizing.
4. Add a provider-neutral planning call returning numbered learning goals with topics, activities, source pages, and a rationale for increasing challenge. Generate missing goal slots in batches and return items sorted by slot. Optional item identifiers preserve old saved-set compatibility. Prompt-only instructions inside isolated batches would restart progression.
5. Reject exact and conservative near-duplicates with the same formula signature. Validate plan coverage and variety. Keep the existing exact-count and timeout behavior. Model-assessed difficulty and semantic uniqueness remain imperfect.
6. Preflight candidate formulas using local KaTeX in the existing Chromium runtime, with the same strict settings as the shared renderer. Block external network access. Reject raw TeX in prose and obvious exercise prose in math blocks. Feed safe rejection codes into external repair prompts.
7. Add a conservative legacy renderer for standalone TeX lines; retain ordinary paragraphs and escape all generated prose. No arbitrary provider HTML is executed.

## Risks / Trade-offs

- [Text extraction order and glyph mappings vary] → Retain the original page canvas and use the text layer for selection; source navigation requires only the original page number.
- [Planning adds latency and cost] → One planning pass normally, at most two; share the existing total deadline and record attempts.
- [Difficulty and paraphrase detection are heuristic] → Use explicit learning goals plus conservative duplicate checks, without claiming mathematical proof.
- [Chromium validation can fail operationally] → Return an actionable error rather than silently accepting unvalidated formulas; reuse the already installed browser.
- [Text overlays consume memory] → Prune distant pages except active selections and cancel stale render work.

## Migration Plan

Deploy with the existing workflow. No database migration is required: new goal identifiers are optional for persisted sets. Rollback restores the previous assets and generator; new metadata is backward compatible.

## Production recovery

The VPS container remained running without OOM/restarts, while generation exhausted recovery and its log showed truncated JSON. Existing logs did not record item rejection codes. Inspect provider completion status before schema parsing, keep plans concise, and use two-item batches (one after truncation). Replacements receive the actual rejected candidate and renderer diagnostic, rather than a generic code alone. Log phases, counts and rejection codes without source content or secrets.

The plan's supporting pages are guidance within the user's selected primary pages, not a narrower authorization boundary. Validate citations against the full selected primary scope. Correctly delimited prose mathematics already supported by the shared renderer can pass the same strict preflight. Near-duplicate wording checks apply within the same planned activity; exact duplicates remain prohibited across all activities.

Keep job state in memory for this single-process deployment: reserve the existing global generation lock at creation, bind jobs to their owner, expose short create/status/cancel endpoints, and expire completed results after 15 minutes. Cancel pending tasks on shutdown. Restarted jobs are lost explicitly, never shown as successful. No queue service, worker, migration, or new dependency is needed. Keep the synchronous endpoint for compatibility; the workspace uses jobs with per-request and overall deadlines.

The affected user requested ten flashcards. They explicitly revised source navigation to page references with smooth scrolling, without fragment highlighting. New generation sets quotation and line fields to null, reducing output overhead while retaining old-set compatibility.
