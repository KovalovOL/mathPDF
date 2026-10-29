# Proposal

## Why

Practice generation currently permits copied source exercises with changed constants, and requires source transcription before task design. Learners need new analogous problems that transfer the same source-supported method without merely rehearsing the notes.

## What Changes

- Design problems from a target skill and source-supported method before selecting a new statement.
- Distinguish literal source references, generated problem inputs and derived solution steps throughout prompts and provider output.
- Require substantive novelty; renamed objects, paraphrases and numerical substitutions alone do not qualify.
- Add explicit origin metadata and bounded local checks without additional provider calls. Document the limits of semantic novelty detection.
- Preserve historical study sets, citations, intentional variants, browser drafts and exports.
- Follow-up after evaluating 180 v2 flashcards: strengthen one-target questions, semantic deduplication, source-grounded reasoning and concept coverage. This adds a flashcard prompt correction without changing schemas or promising measured improvements before retesting.

## Capabilities

### New Capabilities

- `analogous-practice-problems`: Original source-grounded practice, transparent provenance and bounded novelty validation.

### Modified Capabilities

None. The canonical spec inventory is empty; related historical change deltas remain unchanged. This capability supplements their single-request generation and compatibility requirements.

## Impact

Affected areas: `formula_lab/prompts/`, provider schemas and expansion in `providers.py`, canonical blocks and validation in `study.py`, shared rendering/export and compatibility tests. No automatic repair requests, deployment, historical migrations or flashcard redesign are included. Prompt adherence and semantic novelty require a reviewed evaluation corpus; local checks alone cannot guarantee them.
