import secrets
from functools import partial
import httpx
from google.auth import exceptions as google_errors
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_oauth2_token
from app.identity.models import AuthConfig, LoginError


class GoogleIdentityProvider:
    async def exchange(self, config: AuthConfig, code: str, verifier: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": config.client_id,
                        "client_secret": config.client_secret,
                        "redirect_uri": config.callback,
                        "grant_type": "authorization_code",
                        "code_verifier": verifier,
                    },
                )
                response.raise_for_status()
                encoded = response.json().get("id_token")
            if not isinstance(encoded, str) or len(encoded) > 65536:
                raise LoginError()
            return encoded
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
            raise LoginError() from None

    def verify(self, encoded: str, nonce: str, client_id: str) -> dict:
        try:
            claims = verify_oauth2_token(
                encoded, partial(GoogleRequest(), timeout=10), client_id
            )
            self._validate_claims(claims, nonce, client_id)
            return claims
        except (
            google_errors.GoogleAuthError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
        ):
            raise LoginError() from None

    @staticmethod
    def _validate_claims(claims, nonce, client_id):
        actual = claims.get("nonce")
        if (
            not isinstance(actual, str)
            or not secrets.compare_digest(actual, nonce)
            or claims.get("email_verified") is not True
            or not isinstance(claims.get("sub"), str)
            or not 1 <= len(claims["sub"]) <= 255
            or not isinstance(claims.get("email"), str)
            or not 1 <= len(claims["email"]) <= 320
            or claims.get("azp", client_id) != client_id
        ):
            raise LoginError()
