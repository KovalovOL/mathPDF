# Proposal

## Why
An owner-scoped library listing fails on valid stored JSON that PostgreSQL JSONB cannot represent. Current diagnostics are difficult to interpret, and flashcard controls waste mobile space and permit accidental text selection.

## What Changes
- Restore library visibility without converting or rewriting canonical saved content.
- Emit safe JSON backend logs with stable error identities, request/user correlation and concise UI context; present a readable report summary before optional raw details.
- Remove the redundant Flip button and review progress bar, combine navigation and grading controls, prevent accidental touch selection and fit narrow screens.

## Impact
Library metadata projection, diagnostics/report presentation, shared frontend context and flashcard layout/interaction. Saved study formats, sources, variants, review results and daily limits remain compatible.
