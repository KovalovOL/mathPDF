# Verification

## Scope

Verified on 2026-10-26 with disposable local owner data and the existing isolated component/API harnesses. The local provider was deterministic and made no OpenAI request. Production user documents and sessions were not accessed.

## Automated checks

- `UV_CACHE_DIR=/private/tmp/mathpdf-uv-cache uv run --frozen --extra dev pytest -q`: **110 passed** in 23.73 seconds. One pre-existing Starlette/httpx deprecation warning remains.
- The existing historical study-set/draft fixtures remain unchanged and readable. The new annotation table is additive; ordinary documents use optional original IDs and revision-zero defaults.
- API tests cover immutable originals, one copy per original, repeated saves with the same ID, restart/reopen, stale revisions, owner isolation, malformed/bounded input, annotated source/context preparation, original/copy deletion and context-only preservation.
- PDF tests inspect both text and rendered pixels for vector highlights/ink on nonzero crop boxes at rotations 0, 90, 180 and 270 degrees. The original bytes, page boxes and rotation are retained; annotation output does not rasterize the page.
- Isolated browser checks cover pen input, selected-text highlights, complete-gesture erasing, Undo/Redo, Ctrl+S, Meta+Z, hidden tools, failed saves retaining dirty marks, subsequent successful saves, and actual PDF.js inverse coordinates after resizing on all four rotations.
- Parent bridge checks cover filename-specific unsaved context choices, Cancel, original-ID routing, waiting for a successful copy save, and rejecting failed saves without completing preparation.
- JavaScript syntax checks, whitespace checks and strict OpenSpec validation passed.

## Manual browser observations

- Drew and highlighted source pages in the retained viewer. Existing text stayed selectable; marks survived width changes and reopening the saved copy.
- Used the generation choices: Cancel started no job, Use original kept dirty notes open, and Save and use edited copy created the copy before generating from its ID.
- Cmd+S updated the same copy. Undo after a save made the layer dirty; Redo restored the saved state. Closing dirty notes presented Save and close / Discard changes / Cancel; Cancel retained the page and history.
- The library displayed one Edited copy badge. Opening annotation tools on its original opened that copy. Repeated saves retained seven fixture documents (six originals and one copy).
- At 320 x 568 and 390 x 844, the toolbar had no page-level horizontal overflow, kept touch-sized controls and expanded the reading area. Hiding tools restored the normal source/practice layout and retained page 7. Desktop viewport restored afterward.
- Inspected the saved PDF with Poppler: highlights and blue ink aligned with original text/math; the page remained readable and selectable. Internal proof images and desktop/phone UI screenshots are ignored local artifacts under `artifacts/`.

## Observed limits

The new interaction was checked in Chromium and an emulated phone viewport; this is not a physical iPhone, stylus or native Safari verification. Highlight selection depends on the source text layer. Erasing removes whole marks. Undo history is bounded and belongs to the current open viewer. Unsaved notes are not automatically persisted across reloads; leaving warns first. Digital signatures remain applicable only to the untouched original. These limits are documented in `docs/annotations.md`.

## Delivery

Feature commit `9b475d0324f17b75ec1c3f47862f52cf4ce2be4e` deployed through the existing workflow: [run 40250177099](https://github.com/KovalovOL/mathPDF/actions/runs/40250177099), successful. After container replacement, the public `/api/me` returned the expected unauthenticated 401 with build `4f5dcef6cb2a`, matching the local implementation. The annotation toolbar, annotation controller, geometry/history module, PDF viewer and stylesheet returned 200 with hashes matching the committed local assets. No production account or document was opened for this check.

## Follow-up: leave confirmation, palette and centered questions

- Full regression: **112 passed** in 22.38 seconds, with the same pre-existing deprecation warning. The new isolated tests cover Cancel, save failure/retry, waiting for saves, explicit discard, unload protection, account leave approval, trusted-Origin sign-out and server-error recovery. Swatch selection preserves an existing selection and reports its pressed state.
- Actual local UI: home navigation listed both a dirty PDF and an unsaved two-card fixture set. Cancel retained both; Save and leave saved both before opening the library, which displayed the new set and updated copy. Sign-out also displayed the guard; Cancel retained the session, and Save and leave saved the remaining notes and reached the login screen.
- The previous native form submission received an origin-check rejection during sign-out review. The account menu now sends sign-out through the existing same-origin request helper with a 15-second deadline, then clears the visual cache and navigates to login. Server origin checks remain unchanged. A failed request reports an inline error and restores unload protection.
- Visually checked horizontally centered front questions and the five swatches on desktop, including keyboard activation. At 320 x 568 the palette remained visible with no page-level horizontal overflow; the viewport override was reset afterward. Ignored UI proof files: `artifacts/ui/workspace-polish.png` and `artifacts/ui/save-before-leaving.png`.
- No persisted format or mathematical rendering contract changed. Browser close/reload uses the native warning, whose text and actions are controlled by the browser; saving from that event is not promised. All work and generation used disposable local fixtures with no real LLM call.

Follow-up commit `c89dff20ccb956cab5faebf3ccf83b64894e9ae7` deployed successfully in [run 40251841222](https://github.com/KovalovOL/mathPDF/actions/runs/40251841222). The unauthenticated `/api/me` returned 401 with build `ec3a6933ba43`, matching local code. `leave-guard.js`, `account.js`, `annotation-toolbar.js`, `app.js`, `home.js` and `style.css` returned 200 with exact matching hashes. Local verification tabs and the disposable fixture server were closed afterward.
