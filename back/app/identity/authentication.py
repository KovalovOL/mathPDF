"""OIDC/session policies with injected persistence and identity-provider ports."""

import base64
import hashlib
import secrets
import time
from asyncio import to_thread
from datetime import datetime, timezone
from urllib.parse import urlencode
from app.identity.models import AuthConfig, LoginError, User
from app.identity.policies import safe_next, token_hash
from app.identity.ports import SessionRepositoryPort, IdentityProviderPort, RolesPort

SESSION_SECONDS = 30 * 24 * 60 * 60
FLOW_SECONDS = 10 * 60


class Authentication:
    def __init__(
        self,
        repository: SessionRepositoryPort,
        config: AuthConfig,
        roles: RolesPort,
        identity: IdentityProviderPort,
    ):
        self._repository, self._config, self._roles, self._identity = (
            repository,
            config,
            roles,
            identity,
        )

    @property
    def config(self) -> AuthConfig:
        return self._config

    @property
    def roles(self) -> RolesPort:
        return self._roles

    def session_user(self, token: str | None) -> User | None:
        if not token or len(token) > 256:
            return None
        row = self._repository.find_session(token_hash(token), int(time.time()))
        return User.model_validate(row) if row else None

    def revoke(self, token: str | None) -> None:
        if token and len(token) <= 256:
            self._repository.revoke(token_hash(token))

    def begin(self, next_path: str, previous_cookie: str | None) -> tuple[str, str]:
        if not self._config.configured:
            raise LoginError()
        cookie, state, nonce = (secrets.token_urlsafe(32) for _ in range(3))
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        previous = (
            token_hash(previous_cookie)
            if previous_cookie and len(previous_cookie) <= 256
            else None
        )
        self._repository.store_flow(
            (
                token_hash(cookie),
                token_hash(state),
                nonce,
                verifier,
                safe_next(next_path),
                int(time.time()) + FLOW_SECONDS,
            ),
            previous,
            int(time.time()),
        )
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": self._config.client_id,
                "redirect_uri": self._config.callback,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return cookie, url

    def consume(self, cookie: str | None, state: str | None) -> dict:
        if not cookie or len(cookie) > 256 or not state or len(state) > 256:
            raise LoginError()
        row = self._repository.consume_flow(token_hash(cookie))
        if (
            row is None
            or row["expires_at"] <= int(time.time())
            or not secrets.compare_digest(row["state_hash"], token_hash(state))
        ):
            raise LoginError()
        return row

    def verify_identity(self, encoded: str, nonce: str) -> dict:
        return self._identity.verify(encoded, nonce, self._config.client_id)

    def create_session(self, claims: dict, old_token: str | None) -> str:
        token = secrets.token_urlsafe(32)
        name = claims.get("name")
        name = (
            name.strip()[:200]
            if isinstance(name, str) and name.strip()
            else claims["email"][:200]
        )
        previous = (
            token_hash(old_token) if old_token and len(old_token) <= 256 else None
        )
        identifier = self._repository.create(
            claims,
            name,
            token_hash(token),
            previous,
            int(time.time()),
            datetime.now(timezone.utc).isoformat(),
            SESSION_SECONDS,
        )
        self._roles.verified_login(identifier, claims["email"])
        return token

    async def finish(
        self,
        cookie: str | None,
        state: str | None,
        code: str | None,
        error: str | None,
        old_token: str | None,
    ) -> tuple[str, str]:
        flow = await to_thread(self.consume, cookie, state)
        if error or not code or len(code) > 4096 or not self._config.configured:
            raise LoginError()
        encoded = await self._identity.exchange(self._config, code, flow["verifier"])
        claims = await to_thread(self.verify_identity, encoded, flow["nonce"])
        token = await to_thread(self.create_session, claims, old_token)
        return token, flow["next_path"]

    def set_cookie(self, response, name: str, token: str, max_age: int) -> None:
        response.set_cookie(
            name,
            token,
            max_age=max_age,
            secure=self._config.secure,
            httponly=True,
            samesite="lax",
            path="/",
        )

    def clear_cookie(self, response, name: str) -> None:
        response.delete_cookie(
            name, secure=self._config.secure, httponly=True, samesite="lax", path="/"
        )
