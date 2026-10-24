# Proposal

## Why

Generation currently asks for "up to" a count, accepts short sets, and exposes formula-validation failures. Learners need exactly the requested number of usable items, clear waiting feedback, and recognizable files on home.

## What Changes

- Add lazy first-page PDF thumbnails, image previews, and plain-text excerpts to the private file library.
- Accept 1–50 requested items, including 15 flashcards; return success only with exactly that many validated, non-duplicate items.
- Generate small batches with bounded repair/top-up requests for invalid or missing items; retain source/formula validation and an explicit insufficient-source failure instead of fabricated or partial success.
- Enforce each OpenAI batch's count in its structured response schema, with a separate insufficient-source result.
- Keep all new LLM instruction and repair text in external prompt files.
- Show an accessible animated generation status with requested count and elapsed time, and restore controls after success or failure.

## Capabilities

### New Capabilities

- `library-previews`: Private, lazy file previews on the personal library.
- `study-generation`: Exact requested counts, formula-valid batches, bounded recovery, and truthful waiting feedback.

### Modified Capabilities

None are archived in main specs. This change supersedes the earlier allowance for successful short generation results while retaining source fidelity and ownership boundaries.

## Impact

- Study schemas, provider contract, OpenAI response schema, prompts, generation orchestration, and API limits.
- Library preview module using the already vendored PDF.js and owner-protected file endpoint; no thumbnail storage service.
- Workspace status UI, count input, documentation, and metadata compatibility with existing saved sets.
