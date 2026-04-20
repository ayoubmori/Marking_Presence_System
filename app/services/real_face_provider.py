import os
import cv2
import pickle
import numpy as np
from deepface import DeepFace

from app.core.config import get_settings
from app.services.face_provider import FaceDecision

settings = get_settings()

# Helper function to calculate math distance between two faces instantly
def cosine_distance(a, b):
    a = np.array(a)
    b = np.array(b)
    return 1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

class RealFaceProvider:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        
        # Load the pre-calculated math into RAM!
        self.db_file = "./face_embeddings.pkl"
        self.face_db = []
        
        if os.path.exists(self.db_file):
            with open(self.db_file, "rb") as f:
                self.face_db = pickle.load(f)
            print(f"[AI ENGINE] Loaded {len(self.face_db)} face embeddings into memory! ⚡")
        else:
            print("[AI WARNING] face_embeddings.pkl not found! Run build_embeddings.py first.")

    def check_liveness(self, face_bgr) -> tuple[bool, float]:
        """Anti-Spoofing logic"""
        if face_bgr is None or face_bgr.size == 0:
            return False, 0.0
            
        face = cv2.resize(face_bgr, (100, 100))
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        
        s1 = min(cv2.Laplacian(gray, cv2.CV_64F).var() / 200.0, 1.0)
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        s2 = min(np.var(np.sqrt(gx**2 + gy**2)) / 500.0, 1.0)
        
        fft = np.fft.fftshift(np.fft.fft2(gray))
        mag = np.abs(fft)
        h, w = mag.shape
        mask = np.zeros((h, w), dtype=bool)
        mask[h//4:3*h//4, w//4:3*w//4] = True
        s3 = 1.0 - min(mag[~mask].mean() / 15.0, 1.0)
        
        hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV)
        s4 = 1.0 - min(np.sum(hsv[:,:,2] > 220) / hsv[:,:,2].size / 0.25, 1.0)
        
        sat = hsv[:,:,1]
        sl = np.std([np.mean(sat[:50,:50]), np.mean(sat[:50,50:]),
                     np.mean(sat[50:,:50]), np.mean(sat[50:,50:])])
        s5 = min((np.std(sat) + sl*2) / 50.0, 1.0)
        
        score = s1*0.30 + s2*0.20 + s3*0.25 + s4*0.15 + s5*0.10
        return score >= settings.liveness_threshold, round(score, 3)

    def identify(self, image_bytes: bytes) -> FaceDecision:
        if not self.face_db:
            return FaceDecision(matched=False, confidence=0.0, reason="Database is empty. Run build_embeddings.py")

        # 1. Decode image & Extract Face
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))

        if len(faces) == 0:
            return FaceDecision(matched=False, confidence=0.0, reason="No face detected in frame")

        faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
        x, y, w, h = faces[0]
        face_bgr = frame[y:y+h, x:x+w]

        # 2. Check Liveness
        is_real, liveness_score = self.check_liveness(face_bgr)
        if not is_real:
            return FaceDecision(matched=False, confidence=0.10, reason="Spoof detected")

        # 3. Convert Live Face into Numbers (Embeddings)
        try:
            live_result = DeepFace.represent(img_path=face_bgr, model_name="Facenet", enforce_detection=False)
            live_embedding = live_result[0]["embedding"]
        except Exception:
            return FaceDecision(matched=False, confidence=0.0, reason="Failed to extract facial features")

        # 4. INSTANT SEARCH: Compare live numbers to database numbers
        best_candidate_name = None
        lowest_distance = 1.0 

        for item in self.face_db:
            dist = cosine_distance(live_embedding, item["embedding"])
            if dist < lowest_distance:
                lowest_distance = dist
                best_candidate_name = item["name"]

        # 5. Convert Distance to Confidence
        calculated_confidence = max(0.0, 1.0 - lowest_distance)
        
        return FaceDecision(
            matched=False, 
            candidate_user_id=best_candidate_name, 
            confidence=round(calculated_confidence, 2), 
            reason=f"Best guess: {best_candidate_name} (Dist: {round(lowest_distance, 2)})"
        )