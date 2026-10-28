# Verification

## Local regression and service checks

- The full suite passed: 137 tests; three opt-in real infrastructure tests are run separately.
- All three real PostgreSQL 17 / Garage 2.5 integration tests passed against isolated databases and synthetic PDFs: populated migration, empty migration/post-cutover writes, and hash-mismatch/transactional retry.
- Historical fixture files were not changed. Migration compares raw table values and canonical JSON without parsing or normalization, retains original source files, checks every durable object's SHA-256, and preserves Google session hashes, folders, archives and annotation revisions.
- The complete production Compose stack was built and started in an isolated local project. Five persistent services became healthy; bootstrap and migration exited successfully. The setup jobs were tested on an empty data directory without using production secrets.
- API checks cover free-user denial, owner-only role grants, immediate revocation in existing sessions, immutable owner access, origin checks, private report ownership, usage/cached-discount arithmetic, unknown usage/prices and durable replay after outages.
- Report checks cover server/browser enrichment in both arrival orders, automatic validation failures, nested/echoed credential removal, deduplication, source ownership, private bundles, storage retry, and source snapshots after library deletion.
- An isolated 390 px browser component test covers automatic 400/500/failed-job reports, exact active item/page context, categorized comments, no recursive reporting, credential removal and queued retry across reload/reconnect.

## Manual browser observations

The app, admin and reports services were run on loopback against real PostgreSQL/Garage with deterministic local fixtures. No external LLM call was made.

- Administration renders in the existing gray/white/blue MathPDF style.
- A four-call synthetic sample shows 13,500 tokens, including 2,000 cached input tokens, and $0.00852 estimated cost. Day/week/month views show the expected daily averages (13,500 / 1,928.57 / 450 tokens).
- A categorized manual report submitted through the account menu appeared in Administration with its exact comment, sanitized library context and ready private source collection.
- Report details show private bundle download and triage controls. The form fits a 390 × 844 phone viewport without horizontal overflow.
- Preview screenshot: `/private/tmp/mathpdf-admin-preview.png` (synthetic fixture data).

## Production cutover

Preflight (October 28, 2026): three users, four documents, 30 study sets, 12 folders, 30 placement records and four active/retained sessions. Four managed binaries total 1,263,812 bytes. The configured owner account exists. Final counts and hashes must be verified from the stopped-writer migration snapshot, because users can continue working before cutover.

Deployed commit `1fcd9015f10fa90238f96014c5ffebcfdf76cc50` successfully through [Actions run 40706702411](https://github.com/KovalovOL/mathPDF/actions/runs/40706702411). Live build: `6daba318442b`.

- All five persistent services report healthy; bootstrap and migration exited successfully.
- The migration copied and verified 84 source rows and four durable object hashes. An independent post-cutover check on the VPS matched every source row hash in all eight legacy tables, including opaque JSON and session hashes. Counts remained three users, four documents, 30 sets, 12 folders, 30 placements, four sessions and one OAuth flow.
- The consistent SQLite backup, previous Compose configuration and all four original local binaries remain on the VPS. Verification inspected data locally and returned only counts/boolean hash results; no production content or credentials were exported.
- Owner bootstrap is correct: one owner for the configured email and two default-free users. No artificial production users, AI calls or reports were added.
- Anonymous direct admin/report service requests returned 401. Public HTTPS `/health` returned 200 with the expected build, Google configuration is present, `/api/me` returned 401 and `/admin` redirected to login.
- The deployed sign-in page was also confirmed in the browser. Administrative UI/role mutation behavior was verified locally with synthetic sessions; no production Google session was impersonated.
- Production AI accounting starts with this release; earlier calls remain explicitly untracked rather than estimated from saved content.
