from typing import Optional, Protocol
from pydantic import BaseModel


class FaceDecision(BaseModel):
    matched: bool
    candidate_user_id: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""


class FaceProvider(Protocol):
    def identify(self, image_bytes: bytes) -> FaceDecision:
        pass
