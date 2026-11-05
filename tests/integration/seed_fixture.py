"""Run only inside the disposable acceptance container, through stdin."""

import json
from pathlib import Path
from app.bootstrap.container import Services
from app.identity.role_models import OWNER_EMAIL


def seed():
    services = Services.create(Path("/data"))
    result = {}
    for name, email in [("free", "free@example.invalid"), ("owner", OWNER_EMAIL)]:
        token = services.auth.create_session(
            {"sub": "acceptance-" + name, "email": email, "name": "Acceptance " + name},
            None,
        )
        user = services.auth.session_user(token)
        result[name] = {"token": token, "user_id": user.id}
    result["cookie"] = services.auth.config.session_cookie
    print(json.dumps(result))


if __name__ == "__main__":
    seed()
