from pydantic import BaseModel, EmailStr

from app.core.config import PresenceMode


class UserCreate(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    user_type: str
    department_or_filiere: str | None = None
    active: bool = True


class PolicyUpsert(BaseModel):
    context_id: str
    mode: PresenceMode
    active: bool = True


class TestQrRequest(BaseModel):
    user_id: str
    context_id: str
