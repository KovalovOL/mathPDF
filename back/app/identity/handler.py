from fastapi import Request
from fastapi.responses import RedirectResponse
from app.identity.authentication import (
    FLOW_SECONDS,
    LoginError,
    SESSION_SECONDS,
    safe_next,
)
from app.infrastructure.http.frontend import html_page


class IdentityHandler:
    def __init__(self, auth, users):
        self._auth, self._users = auth, users

    def register(self, router):
        router.add_api_route(
            "/login", self.login, methods=["GET"], include_in_schema=False
        )
        router.add_api_route(
            "/auth/config", self.auth_config, methods=["GET"], include_in_schema=False
        )
        router.add_api_route(
            "/auth/google/login",
            self.google_login,
            methods=["GET"],
            include_in_schema=False,
        )
        router.add_api_route(
            "/auth/google/callback",
            self.google_callback,
            methods=["GET"],
            include_in_schema=False,
        )
        router.add_api_route(
            "/auth/logout", self.logout, methods=["POST"], include_in_schema=False
        )
        router.add_api_route("/api/me", self.me, methods=["GET"])
        router.add_api_route("/api/welcome/claim", self.claim_welcome, methods=["POST"])

    def login(self, request: Request, next: str = "/"):
        if request.state.user:
            return RedirectResponse(safe_next(next), status_code=303)
        return html_page("login.html")

    def auth_config(self):
        return {"configured": self._auth.config.configured}

    def google_login(self, request: Request, next: str = "/"):
        try:
            cookie, url = self._auth.begin(
                next, request.cookies.get(self._auth.config.flow_cookie)
            )
        except LoginError:
            return RedirectResponse("/login?error=unavailable", status_code=303)
        response = RedirectResponse(url, status_code=303)
        self._auth.set_cookie(
            response, self._auth.config.flow_cookie, cookie, FLOW_SECONDS
        )
        return response

    async def google_callback(
        self,
        request: Request,
        state: str | None = None,
        code: str | None = None,
        error: str | None = None,
    ):
        try:
            token, next_path = await self._auth.finish(
                request.cookies.get(self._auth.config.flow_cookie),
                state,
                code,
                error,
                request.cookies.get(self._auth.config.session_cookie),
            )
            response = RedirectResponse(next_path, status_code=303)
            self._auth.set_cookie(
                response, self._auth.config.session_cookie, token, SESSION_SECONDS
            )
        except LoginError:
            response = RedirectResponse("/login?error=failed", status_code=303)
        self._auth.clear_cookie(response, self._auth.config.flow_cookie)
        return response

    def logout(self, request: Request):
        self._auth.revoke(request.cookies.get(self._auth.config.session_cookie))
        response = RedirectResponse("/login", status_code=303)
        self._auth.clear_cookie(response, self._auth.config.session_cookie)
        self._auth.clear_cookie(response, self._auth.config.flow_cookie)
        return response

    def me(self, request: Request):
        user = request.state.user
        return {**user.model_dump(), "welcome_pending": self._users.welcome_pending(user.id)}

    def claim_welcome(self, request: Request):
        return {"show": self._users.claim_welcome(request.state.user.id)}
