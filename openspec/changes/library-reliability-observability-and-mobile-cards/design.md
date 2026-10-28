# Design

## Decisions
- Parse only the required library metadata in Python from opaque TEXT payloads. PostgreSQL JSONB rejects escaped NULs even when the requested metadata is unrelated. Preserve raw payloads and all user content. A malformed payload keeps its library entry with a diagnostic marker rather than hiding the owner's files.
- First ship the library restoration with synthetic SQLite/PostgreSQL regressions, then continue the monitoring and card UX update.
- Use one JSON log record per line with UTC timestamp, level, event, error_code, exception type, safe application stack, request/job/user identifiers and request route. Never log raw exception messages, credentials or document contents. Add bounded frontend screen/action/entity context through existing diagnostics/report boundaries.
- Reports retain their full existing evidence and private bundles; add a computed concise summary, curated steps and a compact timeline. Raw JSON remains available in collapsed advanced details, not as the default view. Historical reports need no rewrite.
- A card flips on tap or Space/Enter. On touch devices prevent text-selection/callout on the card, while preserving links and inner scrolling; dragging to scroll must not flip. Desktop text selection remains usable.
- Remove the Flip button and the in-round review bar. Combine previous/next navigation, current index and answer-only Correct/Incorrect actions in a compact responsive footer. Keep server-side round history and completion summaries. Constrain width and allow answer content to scroll inside the card rather than forcing horizontal page scrolling.

## Compatibility
No persisted study, draft or review format changes. Existing raw reports and bundles stay readable. Library fixes do not replace, sanitize, discard or regenerate saved content.
