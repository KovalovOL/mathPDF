from dataclasses import dataclass
from pydantic import BaseModel
from app.identity.role_models import Role


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
