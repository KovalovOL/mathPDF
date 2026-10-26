# Verification

## Automated checks

- Final full regression suite: **121 passed in 24.68 seconds**. One pre-existing Starlette/httpx deprecation warning remains. Frozen historical fixtures were not edited.
- Dedicated API checks cover owner isolation, foreign destinations, compatible root/active defaults, unchanged historical payloads after organization, retained placement after canonical save and restart, cycles, maximum depth, duplicate sibling names, stale folder-removal revisions, safe reparenting and atomic collision rollback.
- Explicit source deletion still removes archived primary-source sets. SQLite triggers remove orphan organization entries in the same deletion transaction.
- Isolated Chromium library harness verifies native HTML drag-to-folder, independent source/set placement, archive and restore to the saved folder, and a Move dialog's empty-string root destination.
- Five difficulty levels reach the shared provider prompt; default 3 and invalid-value rejection are covered. Single-provider-request and frozen historical-format suites remain applicable.
- JavaScript syntax checks, whitespace checks and strict OpenSpec validation pass.

## Local browser verification

Used only the existing disposable local fixture service on 127.0.0.1:8766. No production accounts, private documents or external LLM calls were used.

- Created Linear algebra; moved Mathematics 6.pdf and Practice with source notes into it. Separate Files and Study sets lists and primary-source grouping remained correct.
- Archived and restored the file, preserving its folder. Independently archived/restored a saved set. Counts and saved paths updated.
- On a 320 × 568 viewport, created a nested Week 1 folder, renamed it Week 01 and moved it to root. Reviewed the folder-removal warning and cancelled; removal behavior is covered by isolated API tests.
- Difficulty has five native radios with visible selected state, English labels and a live description. Keyboard arrows selected level 4. Generated exactly two fixture cards in one request, saved Level 4 recall, and confirmed Level 4 in the workspace and source group. The fixture provider verifies transport/persistence, not real-model answer quality.
- Phone library width remained 320 with no horizontal overflow; controls and menus retained touch targets. The original cached file-preview module remains in use.
- The in-app browser's native drag gesture did not move an item; the same production drag handler passed a real Chromium drag check in the isolated harness. Move dialogs were verified in the app on desktop and phone.

Screenshots: artifacts/ui/study-difficulty.png, study-difficulty-phone.png, organized-library.png and organized-library-phone.png (local ignored proof artifacts).

## Quality limits

Explanation depth, source fidelity and difficulty progression are explicit prompt requirements. The application does not mathematically prove generated answers or perform extra model calls to grade them. Flashcard word/paragraph targets guide writing without truncating canonical content. Existing global payload/token/time limits still apply to long problem solutions.

## Deployment

Pending final integration checks and the existing main-branch deployment workflow.
