from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class PresenceMode(str, Enum):
    CHECKIN_ONLY = "checkin_only"
    CHECKIN_CHECKOUT = "checkin_checkout"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Flexible Presence API"
    database_url: str = "sqlite:///./presence.db"
    secret_key: str = "change-me"

    qr_token_ttl_seconds: int = 10

    face_auto_accept_threshold: float = 0.85
    face_qr_fallback_threshold: float = 0.60

    default_presence_mode: PresenceMode = PresenceMode.CHECKIN_ONLY

    # Real Face Provider Settings
    faces_dir: str = "./faces"
    liveness_threshold: float = 0.35

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"

    camera_id: str = "usb-cam-1"

    # Mock face provider settings for first test
    mock_face_mode: str = "always_qr"  # always_accept | always_qr | always_unknown
    mock_face_candidate_user_id: str = "EMP001"

    # If SMTP is not configured, QR PNGs are saved locally for testing
    debug_save_email_to_disk: bool = True
    debug_outbox_dir: str = "./debug_outbox"

    enable_test_endpoints: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
