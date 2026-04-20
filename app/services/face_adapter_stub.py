# app/services/face_adapter_stub.py
from app.services.face_provider import FaceDecision


class FaceAdapterStub:
    def identify(self, image_bytes: bytes) -> FaceDecision:
        # Replace this later with your teammates' model call
        return FaceDecision(
            matched=False,
            candidate_user_id=None,
            confidence=0.0,
            reason="face model not integrated yet"
        )
