import os
import pickle
from deepface import DeepFace

FACES_DIR = "./faces"
DB_FILE = "./face_embeddings.pkl"

def build_database():
    print(f"[*] Scanning {FACES_DIR} for faces...")
    
    database = []
    
    # Loop through every person's folder
    for folder_name in os.listdir(FACES_DIR):
        folder_path = os.path.join(FACES_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue
            
        print(f"    -> Processing user: {folder_name}")
        
        # Loop through their photos
        for filename in os.listdir(folder_path):
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
                
            img_path = os.path.join(folder_path, filename)
            
            try:
                # This is the magic! It converts the picture into 512 numbers
                result = DeepFace.represent(
                    img_path=img_path, 
                    model_name="Facenet", 
                    enforce_detection=False
                )
                
                # Save the numbers and the name
                embedding = result[0]["embedding"]
                database.append({
                    "name": folder_name,
                    "embedding": embedding
                })
                print(f"       [+] Saved {filename}")
                
            except Exception as e:
                print(f"       [-] Failed to process {filename}: {e}")

    # Save the giant list of numbers to a lightning-fast local file
    with open(DB_FILE, "wb") as f:
        pickle.dump(database, f)
        
    print(f"\n[SUCCESS] Saved {len(database)} face embeddings to {DB_FILE}!")

if __name__ == "__main__":
    build_database()