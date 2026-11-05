import os
from urllib.parse import urlsplit
from app.identity.models import AuthConfig


def read_auth_config():
    base = os.getenv("APP_BASE_URL", "https://mathpdf.site").rstrip("/")
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username is not None
        or (parsed.password is not None)
        or parsed.path
        or parsed.query
        or parsed.fragment
        or (
            parsed.scheme == "http"
            and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        )
    ):
        raise ValueError(
            "APP_BASE_URL must be an HTTPS origin or a loopback HTTP origin."
        )
    client_id = (
        os.getenv("GOOGLE_CLIENT_ID", "").strip() or os.getenv("ClientID", "").strip()
    )
    client_secret = (
        os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        or os.getenv("ClientSecret", "").strip()
        or os.getenv("ClientSecter", "").strip()
    )
    return AuthConfig(client_id, client_secret, base)
