from datetime import datetime, date
from typing import Optional

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    full_name: str
    email: str = Field(index=True)
    user_type: str = Field(index=True)  # student | employee
    department_or_filiere: Optional[str] = None
    active: bool = True

    # placeholder for future real model integration
    face_template_ref: Optional[str] = None


class PresencePolicy(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    context_id: str = Field(index=True)   # class session or work site/department
    mode: str = Field(index=True)         # checkin_only | checkin_checkout
    active: bool = True


class PresenceRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: str = Field(index=True)
    context_id: str = Field(index=True)
    mode: str = Field(index=True)

    presence_date: date = Field(default_factory=lambda: datetime.utcnow().date(), index=True)

    checkin_at: Optional[datetime] = None
    checkout_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    source: str = Field(index=True)  # face | qr_email_fallback
    confidence: Optional[float] = None
    camera_id: Optional[str] = None
    notes: Optional[str] = None


class VerificationChallenge(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    jti: str = Field(index=True)
    user_id: str = Field(index=True)
    context_id: str = Field(index=True)

    token_hash: str = Field(index=True)
    status: str = Field(index=True, default="pending")  # pending | used | expired | cancelled

    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    used_at: Optional[datetime] = None
