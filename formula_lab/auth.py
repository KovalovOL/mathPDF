"""Google OIDC login and revocable, opaque application sessions."""

import base64
import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
from google.auth import exceptions as google_errors
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_oauth2_token
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .workspace import Workspace
from .roles import Role, Roles


SESSION_SECONDS = 30 * 24 * 60 * 60
FLOW_SECONDS = 10 * 60


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def safe_next(value: str | None) -> str:
    """Accept only local entry points, including their document/set query."""
    if not value or len(value) > 2048 or "\\" in value or any(ord(c) < 32 for c in value):
        return "/"
    try:
        parts = urlsplit(value)
    except ValueError:
        return "/"
    if parts.scheme or parts.netloc or parts.path not in {"/", "/workspace", "/admin"}:
        return "/"
    return parts.path + (f"?{parts.query}" if parts.query else "")


class User(BaseModel):
    id: str
    email: str
    name: str
    role: Role = "free"


class LoginError(Exception):
    """Authentication failed; details must not expose provider responses."""


@dataclass(frozen=True)
class AuthConfig:
    client_id: str
    client_secret: str
    base_url: str

    @classmethod
    def from_environment(cls):
        base = os.getenv("APP_BASE_URL", "https://mathpdf.site").rstrip("/")
        parsed = urlsplit(base)
        if (parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.path or parsed.query or parsed.fragment
                or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})):
            raise ValueError("APP_BASE_URL must be an HTTPS origin or a loopback HTTP origin.")
        # Compatibility with the names already used in the owner's APP_ENV.
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip() or os.getenv("ClientID", "").strip()
        client_secret = (os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
                         or os.getenv("ClientSecret", "").strip() or os.getenv("ClientSecter", "").strip())
        return cls(client_id, client_secret, base)

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret)

    @property
    def callback(self):
        return self.base_url + "/auth/google/callback"

    @property
    def secure(self):
        return self.base_url.startswith("https://")

    @property
    def session_cookie(self):
        return "__Host-mathpdf_session" if self.secure else "mathpdf_session"

    @property
    def flow_cookie(self):
        return "__Host-mathpdf_oauth" if self.secure else "mathpdf_oauth"


class Authentication:
    def __init__(self, workspace: Workspace, config: AuthConfig):
        self.workspace, self.config = workspace, config
        self.roles=Roles(workspace)
        with workspace.connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
                CREATE TABLE IF NOT EXISTS oauth_flows (
                    cookie_hash TEXT PRIMARY KEY, state_hash TEXT NOT NULL,
                    nonce TEXT NOT NULL, verifier TEXT NOT NULL,
                    next_path TEXT NOT NULL, expires_at INTEGER NOT NULL
                );
            """)

    def session_user(self, token: str | None) -> User | None:
        if not token or len(token) > 256:
            return None
        with self.workspace.connection() as connection:
            row = connection.execute("""SELECT u.id,u.email,u.name,COALESCE(r.role,'free') AS role FROM users u
                LEFT JOIN user_roles r ON r.user_id=u.id JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>?""",
                                     (token_hash(token), int(time.time()))).fetchone()
        return User.model_validate(dict(row)) if row else None

    def revoke(self, token: str | None):
        if token and len(token) <= 256:
            with self.workspace.connection() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))

    def begin(self, next_path: str, previous_cookie: str | None) -> tuple[str, str]:
        if not self.config.configured:
            raise LoginError()
        cookie, state, nonce = (secrets.token_urlsafe(32) for _ in range(3))
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        now = int(time.time())
        with self.workspace.connection() as connection:
            connection.execute("DELETE FROM oauth_flows WHERE expires_at<=?", (now,))
            if previous_cookie and len(previous_cookie) <= 256:
                connection.execute("DELETE FROM oauth_flows WHERE cookie_hash=?", (token_hash(previous_cookie),))
            connection.execute("INSERT INTO oauth_flows VALUES (?,?,?,?,?,?)",
                               (token_hash(cookie), token_hash(state), nonce, verifier,
                                safe_next(next_path), now + FLOW_SECONDS))
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": self.config.client_id, "redirect_uri": self.config.callback,
            "response_type": "code", "scope": "openid email profile", "state": state,
            "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256",
            "prompt": "select_account",
        })
        return cookie, url

    def consume(self, cookie: str | None, state: str | None) -> dict:
        if not cookie or len(cookie) > 256 or not state or len(state) > 256:
            raise LoginError()
        with self.workspace.connection() as connection:
            row = connection.execute("DELETE FROM oauth_flows WHERE cookie_hash=? RETURNING *",
                                     (token_hash(cookie),)).fetchone()
        if (row is None or row["expires_at"] <= int(time.time())
                or not secrets.compare_digest(row["state_hash"], token_hash(state))):
            raise LoginError()
        return dict(row)

    def verify_identity(self, encoded: str, nonce: str) -> dict:
        claims = verify_oauth2_token(encoded, partial(GoogleRequest(), timeout=10), self.config.client_id)
        actual_nonce = claims.get("nonce")
        if (not isinstance(actual_nonce, str) or not secrets.compare_digest(actual_nonce, nonce)
                or claims.get("email_verified") is not True
                or not isinstance(claims.get("sub"), str) or not 1 <= len(claims["sub"]) <= 255
                or not isinstance(claims.get("email"), str) or not 1 <= len(claims["email"]) <= 320
                or claims.get("azp", self.config.client_id) != self.config.client_id):
            raise LoginError()
        return claims

    def create_session(self, claims: dict, old_token: str | None) -> str:
        now = int(time.time())
        stamp = datetime.now(timezone.utc).isoformat()
        token = secrets.token_urlsafe(32)
        name = claims.get("name")
        name = name.strip()[:200] if isinstance(name, str) and name.strip() else claims["email"][:200]
        with self.workspace.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""INSERT INTO users VALUES (?,?,?,?,?,?)
                ON CONFLICT(google_sub) DO UPDATE SET email=excluded.email,
                name=excluded.name, updated_at=excluded.updated_at""",
                               (uuid4().hex, claims["sub"], claims["email"], name, stamp, stamp))
            user = connection.execute("SELECT id FROM users WHERE google_sub=?", (claims["sub"],)).fetchone()
            connection.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            if old_token and len(old_token) <= 256:
                connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(old_token),))
            connection.execute("INSERT INTO sessions VALUES (?,?,?,?)",
                               (token_hash(token), user["id"], now + SESSION_SECONDS, now))
        self.roles.verified_login(user['id'],claims['email'])
        return token

    async def finish(self, cookie: str | None, state: str | None, code: str | None,
                     error: str | None, old_token: str | None) -> tuple[str, str]:
        flow = await run_in_threadpool(self.consume, cookie, state)
        if error or not code or len(code) > 4096 or not self.config.configured:
            raise LoginError()
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                response = await client.post("https://oauth2.googleapis.com/token", data={
                    "code": code, "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret, "redirect_uri": self.config.callback,
                    "grant_type": "authorization_code", "code_verifier": flow["verifier"],
                })
                response.raise_for_status()
                encoded = response.json().get("id_token")
            if not isinstance(encoded, str) or len(encoded) > 65536:
                raise LoginError()
            claims = await run_in_threadpool(self.verify_identity, encoded, flow["nonce"])
        except (httpx.HTTPError, google_errors.GoogleAuthError, ValueError, TypeError, AttributeError, KeyError):
            raise LoginError() from None
        token = await run_in_threadpool(self.create_session, claims, old_token)
        return token, flow["next_path"]

    def set_cookie(self, response, name: str, token: str, max_age: int):
        response.set_cookie(name, token, max_age=max_age, secure=self.config.secure,
                            httponly=True, samesite="lax", path="/")

    def clear_cookie(self, response, name: str):
        response.delete_cookie(name, secure=self.config.secure, httponly=True, samesite="lax", path="/")
