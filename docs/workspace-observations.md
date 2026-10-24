# Workspace implementation observations

Date: 2026-10-24. These are manual implementation observations, not automated regression coverage.

## Google authentication and personal library (2026-10-24)

- Started the account-aware application with the local loopback origin after stopping the old process. The authorized legacy migration produced owned document/set schemas and removed all three old managed uploads and old saved sets. Read-only inspection showed zero users, sessions, documents, sets, and managed binaries. The repository's `main.pdf` remains present.
- Reloading `/` redirected the browser to the English sign-in page. Direct navigation to `/static/index.html` also redirected to login; private HTML cannot bypass the entry route. Navigating to `/api/documents` showed `{"detail":"Sign in to continue."}`. The middleware's unauthenticated API response is HTTP 401.
- The sign-in page uses the existing white/gray/blue style. Local Google credentials are absent, so the button is disabled with an availability message. The project owner confirmed that production client credentials were added to GitHub's `APP_ENV` secret before push.
- Reviewed all application repository calls for required server-supplied owner IDs, including source/context preparation, preview/download, saved-set retrieval/upsert, and export validation. Reviewed callback state/PKCE/nonce handling, official ID-token verification, cookie attributes, session expiry/revocation, and unsafe request origin checks. These are code-review observations, not evidence of a completed Google exchange or cross-account runtime exercise.
- Home/library markup and account UI provide uploads, file downloads, saved-set links, and sign-out. Workspace URLs select an owned file or set and restore a selected set's source PDF. Browser preferences include the account ID. Stale account-bound API requests are rejected after an account switch; restored browser-history pages reload.
- Python compilation, JavaScript syntax checks, dependency resolution, strict OpenSpec validation, and diff whitespace checks succeeded. No automated tests or live LLM requests were added or run for this change.

Live Google sign-in, authenticated library interactions, two-account isolation in a running browser, and production deployment were not exercised locally. The library/workspace integration was reviewed in code. Local live sign-in additionally requires a registered loopback callback and local Google credentials. Earlier observations below describe previous revisions and their former unowned data, which the authorized migration has now removed.

- The supplied 59-page PDF is available as a complete continuous document. The reader showed lazily rendered pages, and a page-7 jump kept all other pages accessible.
- Generation settings opened after reading, with an independent single-page range (7–7), mode/count, and context-file controls.
- The exported PDF was added locally as `Study examples.pdf`. Its tab opened as a two-page document, and switching back restored the primary document at page 7. Generation settings independently selected primary pages 5–7 and only page 2 of the example. This selection was canceled without another model request.
- A live two-item request returned one source-grounded card. The service permits fewer items with explanatory notes. An earlier response failed validation; invalid content was reported rather than displayed. The implementation now normalizes redundant unchanged-original metadata and retains safe validation diagnostics.
- The generated card had multiple mathematical blocks on its answer side. Flipping exposed the answer while making the question face inert and inaccessible; source links remained interactive.
- The set was explicitly saved as `Families of sets · page 7`, then restored after reloading the workspace.
- Dragging the separator changed its accessible value from 50 to 55 and caused PDF canvases to adapt to the new pane width. Compact viewports retain two panes down to 640px; smaller screens stack them.
- PDF export completed through the application. The delivered example has two A4 pages, selectable text on both pages, and zero raster images. Both rendered pages were visually inspected: union/intersection/product notation and scripts were present without clipping or missing-glyph boxes.
- The renderer also formats explicit inline TeX delimiters when a provider puts them inside prose. It continues to treat other prose as text rather than trusted HTML.

## Limits of these observations

No automated tests were added or run for this revision. Every upload format, multi-attachment model request, long-set print pagination, and browser combination has not been exercised manually. Schema/range validation, local upload handling, persistence, and print failure paths are implemented, but these observations are not a substitute for future regression coverage.

The example is model-generated and remains unchecked source material in its metadata. Source quotations, explanations, and notation should still be reviewed; successful rendering and PDF printing do not prove mathematical correctness or exact source typography.

## Workspace refinements (2026-10-24)

- Added a local SVG favicon and confirmed the page references it.
- Closed a saved PDF tab and reopened it from Open saved files at its previous page. Closed all three document tabs, observed the empty reader, and confirmed all three files remained in the library.
- Reloaded the workspace with saved-file tab state retained. The selected tab and its close control are kept within the horizontally scrollable tab strip.
- Opened generation settings and entered a plain-text comment with no context files selected. The optional field displayed the comment; the dialog was canceled without a model request. Request/schema/template/set-save propagation was inspected in code.
- Narrowed and widened the Fit width reader at page 30 and partway down a page. The same text at the top remained visible; existing canvases stayed present while their replacements rendered.
- After the learner reported intermittent blank previews that recovered on interaction, added explicit outer-workspace viewport notifications, a final two-frame layout/visible-page redraw, and a delayed missing-canvas recheck. Repeated divider drags then showed the PDF after release without moving into, clicking, or scrolling the PDF.

No automated tests or additional live model requests were run for these refinements. Unfinished-upload cancellation, upload-completion races, and cross-browser repaint behavior have code paths but were not exhaustively exercised manually. The intermittent repaint report was not reproduced in the controlled preview; the extra synchronization removes dependence on pointer/scroll events rather than establishing coverage across browsers.

## Upload-first startup and study-set closing (2026-10-24)

- Started the application without `--pdf` against a separate empty data directory. The workspace displayed Upload PDF, no document tabs, no placeholder PDF toolbar, and disabled generation until a PDF is available.
- Restarted the existing local workspace without a source argument. The migration hid the former bundled sample from Open saved files; Vectors.pdf and Study examples.pdf remained available, and saved study sets were retained.
- Closed a saved Vectors flashcard set, reloaded, and observed that its tab remained closed. It was still listed in Saved sets and reopened successfully.
- Opened a source link from an older saved card. The retained sample document opened at page 7 even though it was hidden from the file library.
- Study-set tabs display independent close buttons. Draft closing offers Save and close, Close without saving, and Cancel. Save cancellation/failure and save-before-close ordering were inspected in code; no additional paid generation was used to create a draft for manual inspection.
- JavaScript syntax checking and Python AST parsing completed successfully. No automated tests or live model requests were added or run for this change. Browser-specific save-dialog races and failed-save behavior were not exhaustively exercised manually.
