import os
import re
import base64
from datetime import datetime
import requests

from app.core.config import get_settings

settings = get_settings()

def email_delivery_mode() -> str:
    # If we have an API key, use the API mode
    if settings.smtp_password and settings.smtp_password.startswith("xkeysib"):
        return "api"
    return "debug_outbox"

def _safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")

# FastAPI runs this in the background, keeping your camera lightning fast!
def send_qr_email(to_email: str, full_name: str, qr_png: bytes, context_id: str, expires_at_iso: str) -> None:
    delivery_mode = email_delivery_mode()

    if delivery_mode == "debug_outbox":
        os.makedirs(settings.debug_outbox_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        base = f"{timestamp}_{_safe_filename(full_name)}_{_safe_filename(context_id)}"
        png_path = os.path.join(settings.debug_outbox_dir, f"{base}.png")
        
        with open(png_path, "wb") as f:
            f.write(qr_png)
        print(f"[DEBUG OUTBOX] QR saved locally to {png_path}")
        return

    # --- THE NEW API APPROACH ---
    api_key = settings.smtp_password
    url = "https://api.brevo.com/v3/smtp/email"

    # We must convert the raw image bytes into Base64 so it can be sent via JSON
    b64_qr = base64.b64encode(qr_png).decode("utf-8")

    payload = {
        "sender": {"name": "Presence System", "email": settings.smtp_from},
        "to": [{"email": to_email, "name": full_name}],
        "subject": "Your Verification QR Code",
        "htmlContent": f"<h3>Hello {full_name},</h3><p>Your verification QR code is attached.</p><p>It expires at <b>{expires_at_iso} UTC</b> and can be used only once.</p><p>Context: {context_id}</p>",
        "attachment": [
            {
                "content": b64_qr,
                "name": "verification_qr.png"
            }
        ]
    }

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    try:
        # Send the API request
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status() 
        print(f"✅ [API EMAIL SUCCESS] QR sent straight to {to_email} inbox!")
    except Exception as e:
        print(f"❌ [API EMAIL ERROR] Failed to send: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Error Details: {e.response.text}")