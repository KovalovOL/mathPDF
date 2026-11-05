from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from app.identity.policies import safe_next
from app.core.observability.diagnostics import http_context

PUBLIC_ROUTES = {
    "/health",
    "/login",
    "/auth/config",
    "/auth/google/login",
    "/auth/google/callback",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth):
        super().__init__(app)
        self._auth = auth

    async def dispatch(self, request: Request, call_next):
        user = await run_in_threadpool(
            self._auth.session_user,
            request.cookies.get(self._auth.config.session_cookie),
        )
        request.state.user = user
        if user and http_context.get() is not None:
            http_context.get()["user_id"] = user.id
        rejection = self._rejection(request, user)
        response = rejection if rejection is not None else await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "SAMEORIGIN",
                "Cache-Control": "no-store",
                "Vary": "Cookie",
            }
        )
        return response

    def _rejection(self, request, user):
        path = request.url.path
        if path not in PUBLIC_ROUTES and user is None:
            return self._anonymous(request)
        if user and path.startswith(("/api/", "/internal/")):
            if request.headers.get("x-mathpdf-user", user.id) != user.id:
                return JSONResponse(
                    {"detail": "The active account has changed."},
                    status_code=409,
                    headers={"X-MathPDF-Account-Changed": "1"},
                )
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not self._same_origin(
            request
        ):
            return JSONResponse(
                {"detail": "Request origin is not allowed."}, status_code=403
            )
        if path.rstrip("/") in {"/admin", "/static/admin.html"} or path.startswith(
            "/api/admin/"
        ):
            if user is None or self._auth.roles.role(user.id) not in {"admin", "owner"}:
                return JSONResponse(
                    {"detail": "Administrator access is required."}, status_code=403
                )
        return None

    @staticmethod
    def _anonymous(request):
        if request.url.path == "/internal/access":
            target = safe_next(request.headers.get("x-mathpdf-original-uri", "/"))
            return JSONResponse(
                {"detail": "Sign in to continue."},
                status_code=401,
                headers={"X-MathPDF-Signin": "/login?" + urlencode({"next": target})},
            )
        if request.url.path.startswith(
            ("/api/", "/internal/")
        ) or request.method not in {"GET", "HEAD"}:
            return JSONResponse({"detail": "Sign in to continue."}, status_code=401)
        target = safe_next(
            request.url.path + ("?" + request.url.query if request.url.query else "")
        )
        return RedirectResponse(
            "/login?" + urlencode({"next": target}), status_code=303
        )

    def _same_origin(self, request):
        return (
            request.headers.get("origin") == self._auth.config.base_url
            and request.headers.get("sec-fetch-site") != "cross-site"
        )
