# Design

## Decisions
- A quota day is exactly 24 hours from 00:00 UTC to the next 00:00 UTC, independent of local daylight-saving changes. Count requests by their dispatch timestamp. Historical usage is retained; only the active daily window contributes to the limit.
- Add nullable daily_tokens to generation_limits. Preserve monthly_tokens and historical rows unchanged. Read daily_tokens when present, otherwise explicitly adopt the prior configured amount as the new daily allowance. New admin edits write daily_tokens. Legacy monthly_tokens API inputs remain accepted as deprecated aliases.
- Count pending historical reservations by the linked attempt timestamp, not their historical month key; old unconfirmed calls from today still reserve allowance. Settlement, actual paid usage and concurrency protection remain transactional.
- A used-portion bar has explicit Used and Left labels, a prominent remaining percentage and a countdown to 00:00 UTC. Refresh at the reset boundary, on account visibility and generation completion; hide meters for exempt roles.
- QuotaExceeded carries a safe structured code, reason, remaining allowance and estimated required percentage. Background job snapshots preserve the same typed failure. A dedicated dialog explains exhausted, insufficient or disabled allowance, offers Adjust request and keeps source pages, item count and comments intact. No generic HTTP/reference toast or automatic bug report for this expected quota state; real failures remain reportable.
- No extra provider requests, changes to math rendering, study-set formats or saved review progress.

## Compatibility
Historical monthly settings and reservations remain readable, with original values/keys retained. Migration imports both old four-column and new five-column settings rows exactly. Existing study and browser-draft fixtures remain unchanged.
