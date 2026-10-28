# Library names, generation allowances and flashcard progress

## Names

Use **Rename** in a library item's action menu or in its workspace toolbar. A file rename preserves its actual extension, identifier, binary, annotations, visual cache and library placement. Study sets keep their identifier, source snapshots, formulas, variants and progress. Historical payloads are updated only at the title field; versionless content stays versionless. Renaming an unsaved generated set changes its draft title until Save is used.

Concurrent renames include the previously displayed name. A stale rename returns a conflict rather than overwriting the newer name. Reopen the library or workspace to refresh it.

## Daily free generation allowance

- The initial global default is **200,000 input plus output tokens per 24-hour UTC day**. Cached input is part of input and is counted once. Already recorded actual usage within the current day counts.
- The allowance applies to the `free` role. `premium`, `admin` and `owner` are exempt. Roles are rechecked when reserving usage, so a stale session cannot bypass a role change.
- Ordinary user screens show a prominent **remaining percentage**, a bar explicitly labeled with the **used percentage** and the reset countdown (00:00 UTC). Administration shows actual tokens, pending reservations and configurable limits. In Overview, edit the global default; in a user's detail dialog, edit the daily override. An empty override inherits the default. Zero disables further free generation. Changes are audited and do not rewrite usage history.
- Before the single provider request, a transaction reserves a local input estimate plus the existing maximum output allowance. Concurrent dispatches cannot spend the same remaining allowance. Requests that cannot fit are rejected before contacting the provider. No additional model call, truncation of the requested set or retry is added.
- The input estimate uses selected PDF page counts and prompt size; it is **not exact provider PDF/vision token accounting**. Reported actual input/output replaces the reservation before content validation. Actual usage may exceed the estimate; all reported usage is counted, the percentage clamps to zero, and subsequent requests are blocked. This is not a provider-enforced hard billing ceiling.
- Provider rejections known to be unbilled release the hold. Timeouts, interrupted requests and unknown billing retain an estimated hold until actual usage is reconciled or that UTC day ends. The UI identifies pending or unconfirmed holds. Administrators can adjust allowances; unknown usage is not fabricated as actual usage.
- Known paid usage survives temporary database outages in the existing durable spool. A late unknown observation cannot erase known counts. Content rejected locally still consumes the tokens the provider reported.

Every free allowance resets at **00:00 UTC**, exactly 24 hours after the previous reset, regardless of daylight-saving changes in a user's timezone. The page refreshes its allowance at the boundary and updates the countdown while open.

Historical `generation_limits.monthly_tokens` values remain intact. A nullable `daily_tokens` column holds new settings; when absent, the old configured amount is explicitly adopted as the daily amount. Legacy `monthly_tokens` API inputs remain accepted. Existing reservations are counted by the attempt dispatch timestamp, including historical month-keyed reservations from the current day. Usage and reservation rows are never reset or deleted.

When a request cannot fit, a dedicated dialog distinguishes exhausted, insufficient and disabled allowance. It shows remaining usage and reset timing, and offers **Adjust request** without losing files, page ranges, item count or comments. Expected quota limits do not create automatic bug reports; real 4xx/5xx failures and manual reports continue to work.

The policies live in `formula_lab/quotas.py`; actual usage observations stay in `formula_lab/usage.py`. Future provider adapters must reserve through `Usage.start` before dispatch and settle through `Usage.finish`. The OpenAI adapter continues to make exactly one provider request.

## Flashcard self-assessment

Flip a card, then choose green **Correct** or red **Incorrect** below it. A successful rating advances to the first unreviewed card. The front of the card does not show these controls or reveal the answer. The platform stores one immutable answer per card and round, with account ownership checks. Repeating a request cannot count a card twice.

After all cards are rated, a summary shows correct/incorrect counts, percentage, change from the previous completed round and recent score history. **Practice again** creates another round; **Review cards** browses the completed deck without changing its answers. The API returns the latest 30 completed rounds for the same content revision, and the UI graphs the latest 10. Earlier rounds remain stored.

Reloading or using another device resumes the current round. A pending rating is kept in account-scoped browser storage until acknowledged, with a Retry action after a connection failure. If another device already rated that card differently, **Use saved progress** explicitly adopts the server's saved result.

Review records live in separate `review_rounds` and `review_answers` tables, not in canonical study JSON. Renaming decks or source files does not reset progress. Editing card content creates a separate content history, retaining older rounds. Unsaved generated sets can be reviewed; saving the same set identifier later retains that progress. Deleting a deck removes its library entry; historical review rows remain private to its account and are not reassigned to another deck.

## Compatibility and verification

All schema additions are non-destructive. Existing study-set and browser-draft format versions remain unchanged; historical compatibility fixtures are unchanged.

Regression coverage includes owner isolation, legacy renames, stale-name conflicts, allowance inheritance, role changes, daily rollover, actual usage and cached tokens, unknown holds, simultaneous reservations, review retry idempotency, content revisions, progress after renaming, browser retry/resume/summary and percentage-only meters. Real PostgreSQL/Garage integration uses disposable synthetic databases. Browser previews use synthetic users and documents and a deterministic local provider, with no external AI calls.

### Verified release

Release `6d00751af3c9239caa63ac57d2ea4b2fd3f39749` deployed successfully in [Actions run 40716268180](https://github.com/KovalovOL/mathPDF/actions/runs/40716268180) on 28 October 2026. Production health returned HTTP 200, build `4f8b78711124`; all five persistent services were healthy. Post-deployment hashes matched all 5 document rows, 31 study-set rows, 12 folders and 31 placement rows; the annotation-edit table stayed empty. All 5 private document binaries verified against their stored SHA-256 values. The requested administrator grant remained present with its audit entry. The seeded default was 200,000 tokens, and all four additive quota/review tables were present.

The final suite passed 145 tests, with 4 infrastructure checks skipped by default; all 4 passed separately against real local PostgreSQL/Garage (149 passing checks in total). Desktop and 390-pixel browser checks confirmed answer-only grading controls, resume after reload, completion summaries, rename, percentage display, global allowance editing and individual overrides. A deterministic fixture's locally rejected response still reduced the displayed allowance from 100% to 97.5%, confirming paid invalid output is accounted for.
