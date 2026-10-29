# Design

## Context

See proposal.md for motivation. `load_prompts` places study-system, formula-guide and math-patterns in system instructions; mode and difficulty instructions are task content. Therefore mode-only edits cannot resolve system-level transcription constraints. `Formula` currently mixes source transcription, generated inputs and derived steps under the same page-bearing shape. `CompactItem.expand` binds all formula blocks to the primary document. `collect_study` validates count, source ownership and exact question fingerprints in one request. Historical study-quality deltas prohibit automatic repair calls. Canonical specs are empty, so this proposal adds a focused capability without rewriting historical deltas.

## Goals / Non-Goals

**Goals:** Resolve conflicting instructions; represent mathematical origin explicitly; make the narrow validation guarantees testable; retain old payloads.

**Non-Goals:** A general proof checker, guaranteed semantic novelty detector, extra model review calls during generation, flashcard redesign, or migration of historical records.

## Decisions

### Remove answer-only character loss risk after v3 visual review

The seven supplied flashcard PDFs contain 130 cards; the two level-1 labels are separate runs and Numbers changes to pages 22–25 with 20 cards. Missing levels and Pigeonhole are not inferred. Visual review shows broken induction operators and glyph-code fragments in prose, while other formulas on the same pages render correctly. Without provider JSON, the exact origin of every corruption cannot be proven. A concrete schema conflict is reproducible: Paragraph parts currently use the plain-English character whitelist, excluding plus signs and mathematical Unicode from source sentences. Replace paragraph text with a length-bounded unrestricted string, retaining the front-only prose constraint. Keep explicit math fragments preferred and do not repair historical data by guessing. Verify schema and expansion preservation, renderer/export behavior and legacy compatibility. Tighten prompt solution checks against false proof tasks, changing the statement mid-solution and unfinished induction steps. Measure v3 using unchanged evaluator prompts; treat formatting-corrupted scores and changed page coverage as limitations, not clean causal effects.

### Follow up measured flashcard regressions

The v2 evaluation with gpt-4o-mini found Sets Level 2 atomicity at 45% versus 100% in v1; Numbers duplicates at 16.7% versus 10%; Proofs source fidelity at 64.3% versus 76.8%; and reduced coverage in Numbers and Pigeonhole Principle. Compound questions and proof-local references are directly observable in the evaluated fronts. Add one-target rules, expected-answer deduplication, a silent concept inventory and a front-only context check to flashcard prompts, coordinating shared system, difficulty and guide instructions. Keep quotations exact and demand reasons for inferences without eliminating useful explanations to improve a judge score. Text extraction can lose mathematical content, so source-fidelity scores alone are not proof of hallucination. Coverage comparisons also depend on the changed Sets page range. No schema or validator changes are required for this follow-up. The updated generation must be retested on the same source selections before reporting quality gains.

### Separate transcription from task creation

Update all six relevant prompt files together. Select skill and method first for problems; select a literal reference only when it supports that method. Allow page-only references. Replace the coefficient-substitution example with a source-supported transfer example and contrasting rejected copies. Restrict literal-transcription rules to quotes, reference formulas and true variant originals. Generated givens and derivations may be new, but must use the selected source's methods, conventions and prerequisites. This resolves the instruction hierarchy rather than relying on a stronger mode-level prohibition.

### Add compatible origin metadata

Extend provider mathematical entries with origin values `source`, `generated` and `derived`; generated and derived entries use the page as method support. Keep `variant` for direct edits only; original analogous tasks may use null. Extend canonical math blocks with optional origin metadata and carry it through provider expansion, save/load, workspace display and export. Missing origin means legacy/unspecified; do not infer generated status or rewrite old payloads. Preserve source document ownership/page validation for every support link. Standalone blocks receive explicit metadata; inline fragments inherit the enclosing generated question or solution context. Bump the write schema version if the existing version contract requires it, while keeping the version-1 reader and fixtures intact.

Alternative rejected: overloading `variant.original` with a theorem that was never edited; that misrepresents lineage. A separate reference object per expression is unnecessary because the existing source link can carry method support when paired with origin.

### Require a novelty account without trusting it as proof

Add problem-level metadata containing the target method in words, novelty category (`new_configuration`, `inverse_task`, `construction`, `error_analysis`, `new_claim`, `copy`, `numerical_only`, `rename_only`) and a brief substantive-change account. Persist it as optional metadata, shown with answers rather than as a question hint. Require it for strict new problem output; permissive historical readers default it to absent. Reject explicit disallowed categories in the new generation path, alongside existing exact-duplicate checks. Do not use fragile numeric-stripping or keyword matching as a semantic rejection rule. This is a bounded guard, not verification of the model's claim.

### Evaluate substantive transfer separately

Create an offline, source-linked corpus for induction, proof methods, numbers and pigeonhole problems. Include copied, renamed, numerical-only, genuinely analogous and out-of-scope candidates with reviewed expected labels. Review novelty, method fidelity, complete givens, correctness and difficulty separately. Every accepted corpus example must pass all five; preserve individual failures rather than hiding them in an average. Report v2 versus proposed prompts on identical pages, counts, difficulty and model settings. Live generation is an explicitly invoked evaluation and is not part of default tests or automatic retries.

## Risks / Trade-offs

- Model metadata may be false → expose the narrow validation guarantee and use reviewed semantic evaluation.
- Strict novelty may reduce feasible counts on short excerpts → return insufficient source, preserving the one-request contract.
- New provenance fields could alter old review fingerprints → default to absent, omit absent fields on serialization and verify saved progress fixtures.
- Generated links could look like literal quotations → distinguish method-support links in both workspace and PDF export.
- Existing historical deltas strongly favor transcription → document the scoped source/generated distinction and regression-test assembled system and mode prompts.

## Migration Plan

Implement reader compatibility and origin propagation before enabling strict new output. Keep historical fixtures unchanged; add new fixtures. Validate workspace, save/reopen and PDF export. Rollback the generation prompt/schema together if needed; never delete new saved fields or user content. No deployment or automatic archival is part of this planning change.
