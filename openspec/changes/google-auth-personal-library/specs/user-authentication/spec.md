## Purpose

Authenticate learners with Google and protect all personal application resources with revocable server-side sessions.

## ADDED Requirements

### Requirement: Verified Google sign-in
The system SHALL authenticate through Google's authorization code flow with state, PKCE, nonce, and server-side ID-token verification. It SHALL identify users by Google's stable subject and require a verified email. Credentials SHALL come from environment variables.

#### Scenario: Successful sign-in
- **WHEN** Google returns a valid code for an unexpired browser-bound transaction
- **THEN** the server verifies the identity, creates or updates the user, and issues an opaque application session cookie

#### Scenario: Invalid callback
- **WHEN** state, transaction cookie, nonce, issuer, audience, signature, or expiration is invalid
- **THEN** sign-in fails without creating a session

### Requirement: Mandatory private access
The system SHALL require an active session for application pages, APIs, uploaded files, and exports. Only login, OAuth entry/callback, and non-private static assets SHALL be public. Missing configuration SHALL never enable anonymous access.

#### Scenario: Anonymous visitor
- **WHEN** an unauthenticated visitor opens the home page
- **THEN** the system redirects to the English Google sign-in page

#### Scenario: Anonymous API request
- **WHEN** an unauthenticated caller requests a private API
- **THEN** the server returns HTTP 401 without private content

### Requirement: Revocable browser sessions
The system SHALL store hashes of opaque session tokens and enforce expiration. Cookies SHALL be HttpOnly, SameSite=Lax, and Secure on HTTPS. Unsafe requests SHALL require the trusted application origin. Logout SHALL revoke the session. Private responses SHALL disable caching.

#### Scenario: Logout
- **WHEN** the signed-in user submits logout from the application origin
- **THEN** the server revokes the session, clears its cookie, and returns the browser to login

#### Scenario: Cross-origin mutation
- **WHEN** a request attempts to change application data from an untrusted origin
- **THEN** the server rejects it without changing data
