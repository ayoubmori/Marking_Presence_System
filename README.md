```markdown
# 🏛️ Smart Presence Kiosk

An enterprise-grade, asynchronous AI attendance system built with Python. It uses **DeepFace** for facial recognition, **OpenCV** for anti-spoofing (liveness detection), and **FastAPI** for a robust backend. If facial recognition fails (low confidence), it seamlessly triggers a secure **QR Code fallback** via email.

---

## ✨ Features

- **⚡ Lightning-Fast AI (Vector Database):** Uses Facenet embeddings to compare live faces against a pre-calculated database in milliseconds, eliminating slow `for` loops.
- **🛡️ Anti-Spoofing (Liveness Detection):** Prevents users from using photos or screens to check-in by analyzing blur, edges, and color saturation.
- **📧 Secure QR Fallback:** If the AI is unsure of a face, it prompts the user to confirm their identity and instantly emails a secure, expiring JWT QR code (via Brevo API).
- **🖥️ Native Kiosk UI:** A beautiful, dark-mode desktop app built with `CustomTkinter` that connects directly to USB webcams without browser permission issues.
- **📊 Real-Time Web Dashboard:** A live HTML/JS dashboard that managers can open on any computer to watch check-ins and check-outs happen in real-time.

---

## 🏗️ System Architecture

1. **The Brain (Backend):** `FastAPI` + `SQLModel` (SQLite). Manages the database, verifies tokens, and handles emails.
2. **The Eyes (Kiosk App):** `CustomTkinter` + `OpenCV` + `DeepFace`. Runs on the physical hardware at the door, calculates face embeddings, and sends API requests.
3. **The Manager (Dashboard):** A lightweight `index.html` file that fetches live data from the backend.

---

## ⚙️ Prerequisites & Installation

### 1. Requirements
Ensure you have Python 3.9+ installed. You also need a working USB or built-in webcam.

### 2. Clone and Setup Environment
```bash
# Navigate to your project folder
cd presence_system

# Create a virtual environment (Recommended)
python -m venv .venv

# Activate the virtual environment
# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies
Install the required libraries (including the AI and UI tools):
```bash
pip install fastapi uvicorn[standard] sqlmodel opencv-python requests python-multipart pydantic-settings PyJWT qrcode[pil] aiosmtplib deepface customtkinter pillow tf-keras
```

### 4. Environment Configuration
Create a `.env` file in the root directory and configure your email and threshold settings:
```env
APP_NAME="Smart Presence API"
DATABASE_URL="sqlite:///./presence.db"
SECRET_KEY="your-super-secret-key-change-me"

# Email Settings (Brevo API Key)
SMTP_PASSWORD="xkeysib-your-brevo-api-key-here"
SMTP_FROM="noreply@yourdomain.com"

# AI Thresholds
FACE_AUTO_ACCEPT_THRESHOLD=0.85
FACE_QR_FALLBACK_THRESHOLD=0.60
LIVENESS_THRESHOLD=0.35
```

---

## 📸 Adding Users to the AI Database

The system uses a vector database to recognize faces. You must structure your `faces/` folder using the exact **Full Name** of the user as it appears in the database.

1. Create a `faces/` directory in the root of your project.
2. Create a subfolder for each user.
3. Add 2-3 clear pictures of their face into their folder.

```text
presence_system/
├── faces/
│   ├── ayoub/
│   │   ├── img1.jpg
│   │   └── img2.jpg
│   ├── saida/
│   │   ├── picA.png
│   │   └── picB.png
```

---

## 🚀 How to Run the System

You need to run this system in **Two Separate Terminals**. 

### Step 1: Initialize the Databases
*(Run these commands once, or whenever you add new photos/users)*
```bash
# 1. Create the SQLite Database and seed it with test users
python seed.py

# 2. Build the Face Embeddings Vector File (face_embeddings.pkl)
python build_embeddings.py
```

### Step 2: Start the Backend Server (Terminal 1)
Leave this running in the background. It hosts the API and the database.
```bash
uvicorn app.main:app --reload
```

### Step 3: Start the Kiosk App (Terminal 2)
Open a new terminal, activate your virtual environment, and run the physical camera scanner.
```bash
python kiosk_app.py
```

### Step 4: Open the Manager Dashboard
Simply open your web browser and navigate to:
**`http://127.0.0.1:8000`**
*(Or double-click the `index.html` file).* Watch the table update automatically as people walk past the Kiosk!

---

## 💡 Usage Flow
1. **Walk up to the Kiosk:** The camera detects a face and runs a liveness check.
2. **High Confidence (Match):** The system instantly checks you in and the UI flashes Green.
3. **Low Confidence (Lighting is bad):** The UI freezes and asks: *"Are you [Name]?"*
    * **Press 'Y' (Yes):** An email with a QR code is sent to your phone.
    * **Press 'N' (No):** The system cancels and tries to scan again.
4. **Scan QR:** Hold the QR code from your email up to the camera to complete the secure fallback check-in.
5. **Check-out:** Walk up to the camera again later in the day, and it will automatically calculate your shift duration and clock you out!
```