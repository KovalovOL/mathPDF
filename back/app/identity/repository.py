from app.core.ports import PersistencePort


class UserRepository:
    def __init__(self, context: PersistencePort):
        self._context = context

    def user_identity(self, identifier):
        from app.identity.models import User

        with self._context.connection() as db:
            row = db.execute(
                "SELECT u.id,u.email,u.name,COALESCE(r.role,'free') AS role FROM users u LEFT JOIN user_roles r ON r.user_id=u.id WHERE u.id=?",
                (identifier,),
            ).fetchone()
        if not row:
            raise KeyError("User not found")
        return User.model_validate(dict(row))
