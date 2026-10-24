# Proposal

## Why

The deployed workspace currently shares one unauthenticated document and study-set repository. Learners need mandatory Google sign-in and a personal library before opening the existing document/practice workspace.

## What Changes

- **BREAKING**: Require a valid application session for the library, workspace, private files, and APIs.
- Sign in through Google OAuth authorization code flow with PKCE, state, nonce, and server-verified OpenID Connect identity; use revocable application sessions in HttpOnly cookies.
- Bind documents and saved study sets to their authenticated owner, including source/context generation and PDF export checks.
- Serve the personal library at `/`, with the account menu at the top right, owned files, and saved flashcard/problem sets.
- Open the existing workspace at `/workspace` when choosing a file or saved set; retain its visual language and interactions.
- Delete pre-authentication uploads and saved sets once during migration, as explicitly requested by the user. Retain subsequent owned data across deployments.
- Load Google credentials from environment variables and use the configured callback `https://mathpdf.site/auth/google/callback`.

## Capabilities

### New Capabilities

- `user-authentication`: Mandatory Google identity and secure, revocable application sessions.
- `pdf-library`: Account-owned uploads and authorization of every file use.
- `personal-library`: Account home with owned files/saved sets and entry into the reading workspace.

### Modified Capabilities

None of these capabilities have been archived into main specs. The broader `pdf-study-workspace` proposal remains responsible for future Garage and practice-progress integration.

## Impact

- Add Google token verification and direct HTTP client dependencies.
- Add SQLite users, OAuth transactions, sessions, ownership constraints, and a one-time legacy-data reset.
- Update FastAPI routing, authorization, storage calls, generation preparation, and private response caching.
- Add login/home/account UI and scope browser preferences by account.
- Keep the existing single-job deployment and local managed file storage.
