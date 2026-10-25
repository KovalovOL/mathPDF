# Tasks

## 1. PDF reading

- [x] 1.1 Add selectable PDF.js text layers with resize, rotation, cancellation, and pruning support; inspect layer lifecycle and JavaScript syntax.
- [x] 1.2 Add ready-handshaked page citation navigation and brief cancellable scrolling; inspect cross-frame validation and document reader limitations. Remove fragment highlighting per the revised user preference.

## 2. Study quality

- [x] 2.1 Add external planning prompts and provider-neutral structured learning plans; inspect count, source-page, and goal-slot validation and document the additional planning request.
- [x] 2.2 Generate missing goal slots in order and reject exact/near duplicates across batches; inspect repair bounds, ordering, compatibility, and count enforcement.
- [x] 2.3 Add strict local KaTeX preflight, prose/math boundary validation, and conservative legacy TeX-line rendering; inspect renderer parity, cleanup, and syntax.

## 3. Integration

- [x] 3.1 Review the complete diff, run static syntax and strict OpenSpec validation, and record the scope of checks without making paid generation requests.
- [x] 3.2 Commit and push the change using the existing deployment workflow; observe the deployment result and record any remaining limitations.

## 4. Production generation recovery

- [x] 4.1 Handle incomplete provider responses before JSON parsing, shorten plans/batches, and return rejected candidates with renderer diagnostics for repair; inspect bounds and safe logs.
- [x] 4.2 Accept renderer-validated delimited math in prose, enforce the selected source scope, and avoid rejecting distinct planned activities as paraphrases; inspect validation and renderer parity.
- [x] 4.3 Add owner-scoped background generation jobs with progress, cancellation, expiration and browser deadlines; inspect ownership, cleanup and terminal UI states.
- [x] 4.4 Update documentation, run static checks, deploy the fix, and inspect the production container state and deployment result.

## 5. API failure diagnostics

- [x] 5.1 Add correlated HTTP/job/provider logs and safe unexpected-error JSON responses; inspect request context propagation and redaction.
- [x] 5.2 Add browser JSON/content-type diagnostics, bounded authenticated error reports, and versioned uncached application assets; inspect telemetry ownership and asset serving.
- [x] 5.3 Document log commands and diagnostic limits, run static checks, deploy, and inspect live response headers and container logs.

## 6. Renderer regression recovery

- [x] 6.1 Initialize the validation browser in standards mode and check known-valid math before provider requests; add real-renderer regression tests.
- [x] 6.2 Reproduce generation through the local API and browser with the real configured provider, checking exact counts and rendered formulas.
- [ ] 6.3 Deploy the verified fix and record test results and live renderer checks.
