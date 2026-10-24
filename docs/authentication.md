# Google authentication and private libraries

## Configuration

Add these lines to the complete multiline GitHub Actions secret `APP_ENV`, keeping the existing OpenAI settings:

```dotenv
GOOGLE_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

The workflow writes `.env` on `/opt/mathPDF` before recreating the container. The production origin defaults to `https://mathpdf.site`; no domain environment variable is needed. Register this exact **Authorized redirect URI** for the Google web client:

```text
https://mathpdf.site/auth/google/callback
```

Only `openid email profile` are requested. No Drive permissions or Google offline access are requested. For a Google consent screen in Testing mode, add the intended accounts as test users; publishing the consent screen is managed in Google Cloud. See [Google's server-side OpenID Connect flow](https://developers.google.com/identity/openid-connect/openid-connect).

For local development, use the ignored project `.env` (see `.env.example`) and set:

```dotenv
APP_BASE_URL=http://127.0.0.1:8765
```

Register `http://127.0.0.1:8765/auth/google/callback` on a development web client, then restart the server. Use the same hostname in the browser. HTTP is accepted only for loopback origins. There is no anonymous login bypass. Missing Google credentials disable sign-in while private pages/APIs remain protected.

## Login and sessions

`GET /auth/google/login` creates a 10-minute, one-use SQLite transaction with state, nonce, and S256 PKCE. A separate opaque HttpOnly cookie binds it to the browser. The callback consumes the transaction, exchanges the code server-side, and verifies Google's signed ID token, issuer, audience, expiration, nonce, and verified email. Accounts are keyed by Google `sub`, so email changes do not create a new account. [Google's verifier](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html) performs ID-token verification.

Application sessions last 30 days. Their random tokens are stored only as SHA-256 hashes in SQLite; the browser receives an HttpOnly, SameSite=Lax, host-only cookie, with Secure and the `__Host-` prefix on HTTPS. No Google access or refresh token is persisted. `POST /auth/logout` revokes the application session and clears cookies. Unsafe requests require an Origin matching the configured application origin. Callback state protects the cross-origin Google return.

Anonymous page navigation redirects to `/login`; private APIs return 401. Private HTML is protected even under `/static`. Only login/OAuth endpoints and non-private CSS, JavaScript, icons, and fonts are public. Private responses use `Cache-Control: no-store`. The built-in server disables access logging to avoid recording authorization codes in callback query strings. Keep proxy access logs from recording those query strings too.

## Ownership and migration

Files and saved study sets receive a non-null owner from the authenticated request. Clients cannot choose an owner. All metadata, byte access, previews, downloads, generation sources/context, saved-set updates, and PDF exports enforce that owner. Identical uploads by separate accounts have separate IDs and managed directories. The UI only stores preferences under the current account ID.

On the first upgrade from the unowned schema, startup deletes the old managed `documents/` contents and saved sets, as explicitly requested by the project owner. It does not claim those records for the first Google account. This reset is irreversible, applies locally and on the VPS, and does not delete repository PDFs outside the managed data directory. Later restarts preserve owned data. Keep one application process during this upgrade so old code cannot write legacy records while migration runs.
