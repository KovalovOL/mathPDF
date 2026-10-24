# Design

## Context

FastAPI currently serves a single unauthenticated workspace backed by SQLite and local managed uploads. Document hashes are globally unique; study sets have no owner. `/` opens the workspace. Deployment already writes `APP_ENV` into `.env` on `/opt/mathPDF` and routes HTTPS through Traefik. Existing workspace interactions must remain usable.

## Goals / Non-Goals

Goals: mandatory verified Google login, private owner-scoped storage and APIs, personal home, reopening existing files/sets, and explicit one-time deletion of legacy material.

Non-goals: Garage migration, sharing, organizations, Google Drive permissions, practice analytics, new LLM behavior, or redesigning the PDF viewer.

## Decisions

### Google identity and application sessions

Use `httpx` for the authorization-code exchange and Google's `google-auth[requests]` verifier for ID tokens. Generate state, nonce, and S256 PKCE values. Store the short-lived transaction in SQLite, bound to a separate opaque HttpOnly browser cookie, and consume it once. Verify nonce and verified email after signature, issuer, audience, and expiry verification. Use Google `sub` as the identity key; do not retain Google access/refresh tokens.

Use independent opaque application sessions with only their SHA-256 hashes stored in SQLite. Sessions expire after 30 days and logout revokes them. This avoids browser-readable JWTs and a separate signing secret. Cookies are HttpOnly, SameSite=Lax, host-only, and Secure in production. Concurrent sign-ins use the latest browser transaction.

References: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), [Google token verifier](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html), [PKCE](https://www.rfc-editor.org/info/rfc7636/).

### Trusted deployment origin and request boundary

Default origin is `https://mathpdf.site`, yielding the registered `/auth/google/callback`. An optional `APP_BASE_URL` supports loopback HTTP development; arbitrary HTTP origins are rejected. Credentials come from `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. No credentials means unavailable sign-in, never anonymous access.

Middleware denies private requests without a live session. Public routes are login, OAuth entry/callback, and non-private static assets. Private HTML remains guarded even under `/static`. Unsafe methods require a matching trusted Origin and reject cross-site fetches. Private responses disable caching; OAuth responses use no-referrer. Disable application access logs containing callback query codes. Remove shared legacy diagnostic HTTP endpoints from this app.

### Owner-scoped repository

SQLite adds users, sessions, OAuth transactions, and non-null ownership foreign keys on documents/study sets. Every repository method requires an owner ID supplied by the authenticated request, including generation context and export validation. Duplicate hashes are unique per owner; files live below `documents/<owner-id>/`. Foreign IDs return generic 404 responses. Upserts cannot replace another owner's set.

### Migration

On detecting the unowned schema, remove its managed document files and reset legacy document/study-set tables before creating owned tables. The user explicitly authorized this deletion. Never adopt records for the first sign-in. Later starts retain owned records. Repository PDFs outside managed storage are untouched. Stop the old process before running this migration locally.

### Library and workspace

Serve new English login and library pages. Home reuses the existing blue/white/gray CSS, shows useful file/set metadata, upload/download actions, and the account menu. `/workspace?document=<id>` and `/workspace?set=<id>` validate ownership before serving the existing interface. A shared account script handles identity, logout, and API 401 redirects. Prefix local storage preferences with the authenticated user ID. Preserve the PDF resize/render implementation.

## Risks / Trade-offs

- Legacy deletion is intentionally irreversible; it is limited to the old managed library and occurs once.
- Google consent configuration and production credentials are external prerequisites. The user is adding them to `APP_ENV`; local OAuth additionally needs a registered loopback callback.
- SQLite sessions add a small lookup per request; this fits the current single-server deployment and permits immediate logout.
- Authentication is incomplete until exercised with a real Google account. Static/manual observations must distinguish implemented behavior from live login/deployment evidence.
- Existing offline diagnostic modules may remain, but their global source data is no longer exposed by the private web app.
