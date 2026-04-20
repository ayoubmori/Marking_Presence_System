from app.core.config import get_settings
from app.services.face_provider import FaceDecision

settings = get_settings()


class MockFaceProvider:
    """
    First-test provider:
    - always_accept  -> directly marks presence
    - always_qr      -> low confidence, sends QR challenge email
    - always_unknown -> reject
    """

    def identify(self, image_bytes: bytes) -> FaceDecision:
        mode = settings.mock_face_mode.strip().lower()
        candidate = settings.mock_face_candidate_user_id

        if mode == "always_accept":
            return FaceDecision(
                matched=True,
                candidate_user_id=candidate,
                confidence=0.95,
                reason="mock auto accept"
            )

        if mode == "always_qr":
            return FaceDecision(
                matched=False,
                candidate_user_id=candidate,
                confidence=0.70,
                reason="mock low confidence, use qr fallback"
            )

        return FaceDecision(
            matched=False,
            candidate_user_id=None,
            confidence=0.20,
            reason="mock unknown face"
        )
