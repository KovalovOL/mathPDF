import hashlib
from urllib.parse import urlsplit


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def safe_next(value: str | None) -> str:
    """Accept only local entry points, including their document/set query."""
    if (
        not value
        or len(value) > 2048
        or "\\" in value
        or any((ord(c) < 32 for c in value))
    ):
        return "/"
    try:
        parts = urlsplit(value)
    except ValueError:
        return "/"
    if parts.scheme or parts.netloc or parts.path not in {"/", "/workspace", "/admin"}:
        return "/"
    return parts.path + (f"?{parts.query}" if parts.query else "")
