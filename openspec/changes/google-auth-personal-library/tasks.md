# Tasks

## 1. Owned persistence

- [x] 1.1 Add users and owner-scoped document/set persistence with a one-time authorized legacy reset; review schema, all repository queries, and migration paths for owner isolation and restart preservation.
- [x] 1.2 Scope generation preparation and saved/exported source/context validation to the authenticated owner; review every repository call and document the data boundary.

## 2. Google authentication

- [x] 2.1 Add dependencies and implement browser-bound Google OAuth/OIDC transactions, verified identities, and revocable hashed sessions; verify dependency resolution, syntax, and callback/session error paths by code review.
- [x] 2.2 Require authentication and trusted-origin mutations throughout FastAPI, remove shared diagnostic HTTP routes, and document environment/callback setup; observe anonymous login/API behavior and review route coverage.
- [x] 2.3 Accept the existing deployment's ClientID and ClientSecter credential names as compatibility aliases, document precedence, and observe sign-in availability after redeployment without printing secrets.

## 3. Personal library and workspace

- [x] 3.1 Build English login/home/account UI with owned uploads, downloads, and saved sets in the existing visual style; inspect responsive markup and observe the login page in the browser.
- [x] 3.2 Integrate owned file/set workspace links, account-specific preferences, identity/logout, and expired-session handling; review existing tab, viewer, generation, save, and export flows for compatibility.

## 4. Integration review

- [x] 4.1 Run static syntax checks and strict OpenSpec validation, review the final diff for secrets and ownership gaps, and record manual observations plus any live Google/deployment limitations.
