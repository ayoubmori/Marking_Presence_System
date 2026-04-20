import hashlib
import io
import time
import uuid
from datetime import datetime, timedelta

import jwt
import qrcode

from app.core.config import get_settings

settings = get_settings()

def build_qr_token(user_id: str, context_id: str) -> tuple[str, str, datetime, str]:
    now = datetime.utcnow()
    exp = now + timedelta(seconds=settings.qr_token_ttl_seconds)
    jti = str(uuid.uuid4())

    # THE FIX: We use a strict Unix timestamp so timezones can't mess it up!
    exp_timestamp = int(time.time()) + settings.qr_token_ttl_seconds

    payload = {
        "sub": user_id,
        "context_id": context_id,
        "purpose": "presence_qr_fallback",
        "jti": jti,
        "exp": exp_timestamp,  # Using the safe timestamp here
    }

    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash, exp, jti

def verify_qr_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])

def render_qr_png(token: str) -> bytes:
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def token_hash_of(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()