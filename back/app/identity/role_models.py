"""Account role values and owner identity."""

from typing import Literal
from pydantic import BaseModel, ConfigDict

OWNER_EMAIL = "sasha.kovalov2008@gmail.com"
Role = Literal["free", "premium", "admin", "owner"]


class RoleChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["free", "premium", "admin"]
