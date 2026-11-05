"""Versioned frontend HTTP assets; no frontend source or filesystem dependency."""

import hashlib
import os
from functools import lru_cache
from pathlib import Path
import httpx
from fastapi.responses import HTMLResponse


@lru_cache
def build_id() -> str:
    configured = os.getenv("MATHPDF_BUILD")
    if configured:
        return configured
    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for path in sorted([*root.rglob("*.py"), *root.rglob("*.md")]):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


class FrontendAssets:
    def __init__(self, base_url: str | None = None):
        self._url = (
            base_url or os.getenv("MATHPDF_FRONTEND_URL", "http://127.0.0.1:8771")
        ).rstrip("/")
        self._manifest = None

    def manifest(self) -> dict:
        if self._manifest is None:
            response = httpx.get(
                self._url + "/manifest.json", timeout=10, follow_redirects=False
            )
            response.raise_for_status()
            data = response.json()
            if data.get("version") != 1 or not isinstance(data.get("assets"), dict):
                raise ValueError("The frontend print asset contract is unsupported.")
            self._manifest = data
        return self._manifest

    def read(self, name: str) -> bytes:
        expected = self.manifest()["assets"].get(name)
        if (
            not expected
            or name.startswith("/")
            or ".." in name.split("/")
            or "\\" in name
        ):
            raise ValueError("Unknown frontend asset.")
        response = httpx.get(self._url + "/" + name, timeout=20, follow_redirects=False)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != expected:
            self._manifest = None
            raise ValueError("Frontend assets changed during export. Please try again.")
        return response.content


def html_page(name: str) -> HTMLResponse:
    if name not in {
        "login.html",
        "home.html",
        "index.html",
        "admin.html",
        "pdf-viewer.html",
    }:
        raise ValueError("Unknown application page")
    return HTMLResponse(
        FrontendAssets().read(name), headers={"Cache-Control": "no-store"}
    )
