"""Version local application assets and require browser revalidation."""

import hashlib
import re
from functools import lru_cache
from pathlib import Path

from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


STATIC = Path(__file__).parent / "static"
HTML_PAGES = {"home.html", "index.html", "login.html", "pdf-viewer.html", "admin.html"}
ASSET_LINK = re.compile(r'''((?:src|href)=["'])(/static/[^"'?]+\.(?:js|mjs|css))(["'])''')


@lru_cache
def build_id() -> str:
    digest = hashlib.sha256()
    root = STATIC.parent
    paths = list(root.glob("*.py")) + list((root / "prompts").glob("*.md"))
    paths += [path for path in STATIC.iterdir() if path.suffix in {".html", ".js", ".css"}]
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@lru_cache(maxsize=100)
def asset_version(url: str) -> str:
    path = (STATIC / url.removeprefix("/static/")).resolve()
    if not path.is_relative_to(STATIC.resolve()) or not path.is_file():
        return build_id()
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def html_page(name: str) -> HTMLResponse:
    if name not in HTML_PAGES:
        raise ValueError("Unknown application page")
    html = (STATIC / name).read_text(encoding="utf-8")
    html = ASSET_LINK.sub(lambda match: f"{match[1]}{match[2]}?v={asset_version(match[2])}{match[3]}", html)
    html = html.replace("<head>", f'<head>\n  <meta name="mathpdf-build" content="{build_id()}">', 1)
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


class ApplicationAssets(StaticFiles):
    async def get_response(self, path, scope):
        if path=='admin.html' and getattr(scope.get('state',{}).get('user'),'role',None) not in {'admin','owner'}:
            return JSONResponse({'detail':'Administrator access is required.'},status_code=403)
        if path in HTML_PAGES and scope["method"] in {"GET", "HEAD"}:
            return html_page(path)
        response = await super().get_response(path, scope)
        if Path(path).suffix in {".js", ".mjs", ".css"}:
            response.headers["Cache-Control"] = "no-cache"
        return response
