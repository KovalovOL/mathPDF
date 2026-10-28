# Reports, roles and the service platform

## Production services

Docker Compose runs five persistent services: `app`, PostgreSQL `db` (17), `garage` (2.5), `reports`, and `admin`. Only the app joins `traefik-public`; it proxies authenticated `/api/reports`, `/admin`, and `/api/admin/*` requests to private services. Database, S3, admin and report ports are not published on the VPS. `bootstrap` and `migrate` are short-lived setup jobs, not additional application servers.

The existing GitHub secrets remain `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, and multiline `APP_ENV`. Keep the Google and OpenAI configuration in `APP_ENV`. No additional infrastructure credentials need to be pasted there: the first bootstrap creates private random credentials in `/opt/mathPDF/.infrastructure/secrets`, and subsequent deployments retain them. Never remove this directory to fix a startup error.

Persistent paths under `/opt/mathPDF`:

| Path | Contents |
| --- | --- |
| `.infrastructure/postgres` | Authoritative production database |
| `.infrastructure/garage` | Private immutable document and report objects plus Garage metadata |
| `.infrastructure/secrets` | Persistent database and object-store credentials (mode 600; directory 700) |
| `.formula-lab/migration-backups` | Consistent original SQLite backup and verified migration manifest |
| `.formula-lab/documents` | Retained original local binaries from before cutover |
| `.formula-lab/object-cache` | Verified, disposable local object cache |
| `.formula-lab/report-spool` | Durable report receipts pending database recovery |
| `.formula-lab/usage-spool` | Paid provider observations pending database recovery |

Both `.formula-lab` and `.infrastructure` are excluded from deployment rsync deletion. Back up the PostgreSQL database, Garage data/metadata and secrets together. The old SQLite backup is a cutover snapshot, not a continuing backup of new PostgreSQL activity. Garage single-node mode supplies persistence on this VPS, not replication to another server.

## Verified cutover and recovery

The inline deployment builds the new image while the old app is running, stops app/admin/report writers, then runs Compose with health checks. The migration must finish successfully before the web services start.

The workflow retains the previous Compose configuration as `.formula-lab/migration-backups/pre-postgres-compose.yaml`. The migration makes a consistent SQLite backup, checks integrity and foreign keys, retains every original local binary, uploads it to private Garage and reads it back to verify SHA-256. It then copies all supported tables transactionally and compares counts and row hashes. Payload strings, IDs, timestamps, session hashes, source references, variants, annotations, folders and archive placement are copied verbatim. It refuses unknown tables, unsupported columns, unowned legacy data, missing binaries, hash mismatches, and an already-populated PostgreSQL target without a completion marker. No partial import is committed. Existing local files and the SQLite source are never removed.

A completion marker is committed with the copied rows. Later deployments detect it and keep PostgreSQL authoritative; they never import a stale SQLite database over post-cutover writes. Owner bootstrap is additive after verification. Missing historical study-set format markers still mean version 1; no regeneration is required.

If a first migration fails, keep the app stopped, inspect `docker compose logs migrate`, correct the cause and rerun `docker compose up -d --wait`. Object uploads can be repeated safely; the database import is transactional. Before accepting any PostgreSQL writes, the previous app image and previous single-app Compose configuration can be restored against the untouched SQLite directory. After accepting new writes, **never roll back to the old SQLite snapshot**: retain PostgreSQL/Garage and deploy a forward fix, or perform an explicitly reviewed reverse migration. Never run `down -v`, delete persistent directories, or truncate a target to get past a migration error.

Useful commands (no credential values):

```sh
cd /opt/mathPDF
docker compose ps -a
docker compose logs --tail=100 migrate app reports admin
docker compose exec db pg_isready -U mathpdf -d mathpdf
```

## Local development

Without PostgreSQL/S3 environment variables, the compatible SQLite/local-file backend remains available. For server storage set `MATHPDF_POSTGRES_HOST`, optional `MATHPDF_POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD_FILE`. `DATABASE_URL` can alternatively specify a full PostgreSQL connection. Keep it private. Set `MATHPDF_S3_ENDPOINT` and `MATHPDF_S3_CREDENTIALS_FILE` for Garage; the JSON file contains `access_key_id`, `secret_access_key`, `bucket`, and `region`.

The main app uses `MATHPDF_ADMIN_URL` and `MATHPDF_REPORTS_URL` for private service routing. Standalone service entry points are `formula_lab.platform_services:admin_app` and `:reports_app` with Uvicorn `--factory`. All services share the same `APP_BASE_URL`, database, managed data directory and private storage credentials. The migration command is `python -m formula_lab.migration` with writers stopped.

## Roles

Google-verified accounts default to `free`. The verified account `sasha.kovalov2008@gmail.com` is bootstrapped as the single `owner`, including an existing migrated account. `admin` and `owner` can open Administration from the account menu. Only the owner can assign `free`, `premium`, or `admin`; every change is audited. Owner privileges cannot be transferred or revoked through these APIs. Role lookup happens for every request, so revocation applies to existing sessions immediately. Premium is an access tier only; billing, checkout and quotas are not introduced by this release.

## Automatic and manual reports

The shared frontend observes 4xx/5xx API responses and failed asynchronous generations. The backend also records authenticated failures and terminal generation failures, including cases where the browser leaves before polling. Server and browser records with the same user/request reference merge into one incident. Report ingestion and diagnostic endpoints do not recursively report themselves.

“Report a problem” in the account menu accepts a comment and an issue category: bug, incorrect content, formatting, slow response, long answer, or other. The report includes authoritative user identity, build, request reference, sanitized request/response JSON, the active file/page/set/item, generation options, viewport, and recent semantic actions. It does not record passwords, cookies, authorization headers, OAuth codes, API keys, or keystrokes. Recognized credentials are removed again on the server, including echoed validation inputs. Avoid entering unrelated confidential information in feedback.

Context is deliberately bounded: 100 recent browser actions, 30 recent requests, 2 MiB server context, bounded nested objects/strings, and up to 12 relevant owner-checked source files. Exceeding limits is explicitly marked. Binary upload bodies are not copied into request logs; source files are collected separately. The server keeps successful mutation/error traces for 14 days. Saved reports and their private source snapshots remain until a retention policy is introduced. Unknown, deleted, foreign or unavailable sources are not guessed or fetched without ownership checks.

The reports container copies immutable source versions and writes a private context object asynchronously. Pending/collecting/retrying/ready states are visible in Administration. When a referenced library revision is deleted before collection finishes, its bytes move to a temporary private diagnostic key until the report snapshot is complete; the library key and normal file access are removed immediately. Temporary storage failures retry with backoff; source versions missing before collection are explicitly marked unavailable. Reports accepted during a database write outage are durably spooled with their original receipt and retried. The browser also retains up to 10 pending automatic reports in user-scoped session storage and retries on reconnect. Packaging does not add an LLM call or delay generation.

Administrators can filter/triage reports, add an internal note, inspect JSON context and download a private ZIP containing the context and available source files. Client-supplied content is rendered as text. Foreign source IDs never grant access to another user's files.

## AI accounting and dashboard

An attempt is committed before each actual OpenAI dispatch. Actual input, cached input, output and reasoning token counts, provider request ID, duration, model, request context and response are recorded before local content validation. A rejected study response therefore still counts as a paid attempt. Completed usage observations are durably spooled and replayed by the reports worker if a temporary database outage interrupts persistence. Generation still makes exactly one model request; no accounting or reporting step regenerates content.

Day/week/month views cover 1/7/30 UTC calendar days including today. Daily averages divide by the full selected number of days, including zero-use days. Users and models have separate breakdowns; user details include all three windows and model totals. Input includes cached tokens; cached input is shown separately, and reasoning tokens are part of output rather than charged twice. Earlier untracked calls have unknown usage and cost; saved-set counts are not used as token estimates.

Costs are USD estimates from actual tokens and an immutable effective tariff selected at dispatch. Cached input gets its own rate. The seed tariff for `gpt-4.1-mini` and `gpt-4.1-mini-2025-04-14`, verified on October 28, 2026, is $0.40 input / $0.10 cached input / $1.60 output per million tokens, from the [official model documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini). The owner can add new effective tariffs without rewriting historical costs. Unknown model prices or unavailable usage remain explicitly unknown and are excluded from known-cost totals; these figures are not invoice reconciliation.
