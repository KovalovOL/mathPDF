# Tasks

Current user-selected scope: update the prompts using the initial v1/v2 evaluation and the reported numerical-substitution failure. Work on task 2.1 only in this pass. Provider schemas, origin metadata, semantic novelty validation and live comparative evaluation remain pending; prompt edits do not establish those behaviors.

Follow-up scope: the completed evaluation of 180 v2 cards now authorizes task 2.4, targeting measured flashcard regressions. Existing problem changes remain in place. v2 PDFs predate these prompt edits and are not an evaluation of the updated prompts.

v3 follow-up scope: evaluate the seven supplied flashcard PDFs (130 cards), inspect the three problem PDFs and correct the demonstrated answer schema conflict and solution-check instructions in task 2.5. Preserve existing output formats and do not claim that a prompt guarantees future correctness.

## 1. Compatible provenance representation

- [ ] 1.1 Add optional source/generated/derived origin and problem novelty metadata to canonical readers; verify unchanged historical fixtures and review fingerprints in study compatibility tests, and document defaults in docs/study-contract.md.
- [ ] 1.2 Extend strict problem output and provider expansion while retaining permissive legacy parsing; verify page-only methods, generated inputs, derived steps and literal variants in provider tests without network calls.
- [ ] 1.3 Carry metadata through save/reopen, workspace answers and PDF export with distinct method-support wording; verify old and new round-trip fixtures and desktop/mobile rendered output, and document the display behavior.

## 2. Method-first generation and bounded checks

- [x] 2.1 Align study-system, problems, formula-guide, math-patterns, comment and difficulty prompts; replace numerical-only examples and verify the assembled problem instructions distinguish transcription from generated givens while flashcard behavior remains unchanged.
- [ ] 2.2 Reject explicit copy/numerical-only/rename-only novelty declarations only on new problem generation, preserving count, ownership and exact-duplicate checks; verify clear failure without partial output or a second provider call in test_single_request.py and document the semantic limits.
- [ ] 2.3 Verify complete solutions, method-selection questions without hints, insufficient source and source-supported difficulty through provider fixtures tied to the specification scenarios.
- [x] 2.4 Align flashcard, shared system, difficulty and final-review instructions with the observed v2 regressions in atomicity, duplicates, source fidelity, self-contained proof questions and coverage; document the limits of text-based judging and verify existing provider/compatibility tests and strict OpenSpec validation.
- [x] 2.5 Remove the answer paragraph character whitelist while preserving constrained fronts and legacy reads; strengthen formula-encoding, difficulty and complete-proof instructions, verify operator preservation with schema/renderer tests, inspect a rendered example and run provider, math and compatibility tests plus strict OpenSpec validation.

## 3. Source-linked quality evaluation

- [ ] 3.1 Deliver reviewed fixtures for induction, proof methods, numbers and pigeonhole tasks, with source pages and expected copy/numerical-only/analogous/out-of-scope labels; verify all five rubric dimensions and document why each candidate passes or fails.
- [ ] 3.2 Deliver an offline evaluation command and report format for novelty, method fidelity, givens, correctness and difficulty; verify expected labels against the fixed corpus and record that metadata checks do not establish semantic originality.
- [ ] 3.3 Document and exercise a comparison using identical source excerpts, count, level and model settings for v2 and proposed prompts; preserve per-item results and configuration. Keep paid live generation opt-in, with one call per set and no automatic repairs; verify the offline path runs without credentials.

## 4. Integration verification

- [ ] 4.1 Run the focused provider, single-request, persistence, compatibility and export checks followed by the repository-required suite; record results and verify that no historical fixture or persisted user data was rewritten.
- [ ] 4.2 Validate the OpenSpec change strictly and reconcile each acceptance scenario with its test or reviewed evaluation evidence before marking implementation complete.

## Workflow follow-up

- v3 verification: 83 provider, real-renderer and historical-compatibility tests passed. A separate rendered example preserved induction plus/inequality and membership fragments, with zero math fallbacks. Evaluation covered the supplied 130 cards, not a new full generation after the fix. The comparison workbook records changed source ranges and missing sets; manual problem findings are not presented as automatic metric scores.
- Follow-up verification: 75 provider and compatibility tests passed, strict OpenSpec validation passed. The 180-card evaluation concerns earlier v2 PDFs, not the new prompts; generation-quality improvement remains unmeasured until retesting.
- Review implementation and evaluation evidence before explicitly archiving this change.
- Prompt update verification: 75 tests passed in test_single_request.py and test_study_compatibility.py, using the installed Chrome via MATHPDF_CHROMIUM_EXECUTABLE. Template substitution and strict OpenSpec validation also passed. Context citation instructions and docs/study-contract.md were aligned. No paid generation or claim of improved semantic novelty was made; all other tasks remain pending.
