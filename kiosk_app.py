import cv2
import time
import requests
import threading
import customtkinter as ctk
from PIL import Image

# --- CONFIGURATION ---
API_BASE = "http://127.0.0.1:8000"
CONTEXT_ID = "WORK-HQ"
CAMERA_ID = "kiosk-1"
CAMERA_INDEX = 0

FACE_INTERVAL = 2.0
FACE_COOLDOWN = 60.0
QR_COOLDOWN = 5.0

class PresenceKiosk(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Smart Presence Kiosk")
        self.geometry("900x600")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # State Variables
        self.pause_face_until = 0.0
        self.last_face_attempt = 0.0
        self.recent_qrs = {}
        self.is_processing = False
        self.pending_user_id = None  # Remembers WHO we are asking about

        # --- UI LAYOUT ---
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.video_frame = ctk.CTkFrame(self, corner_radius=10)
        self.video_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.video_label = ctk.CTkLabel(self.video_frame, text="")
        self.video_label.pack(expand=True, fill="both", padx=10, pady=10)

        self.dash_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#1e1e1e")
        self.dash_frame.grid(row=0, column=1, padx=(0, 20), pady=20, sticky="nsew")

        self.status_title = ctk.CTkLabel(self.dash_frame, text="READY", font=("Roboto", 24, "bold"), text_color="#00ffcc")
        self.status_title.pack(pady=(30, 5))
        self.status_sub = ctk.CTkLabel(self.dash_frame, text="Scanning for faces & QR...", font=("Roboto", 14), text_color="gray")
        self.status_sub.pack(pady=(0, 20))

        # --- NEW: YES / NO BUTTONS ---
        self.btn_frame = ctk.CTkFrame(self.dash_frame, fg_color="transparent")
        self.btn_yes = ctk.CTkButton(self.btn_frame, text="YES (Y)", font=("Roboto", 16, "bold"), fg_color="#27AE60", hover_color="#219653", command=self.confirm_yes)
        self.btn_no = ctk.CTkButton(self.btn_frame, text="NO (N)", font=("Roboto", 16, "bold"), fg_color="#E74C3C", hover_color="#C0392B", command=self.confirm_no)
        
        # Keyboard bindings so the user can just press Y or N
        self.bind("<y>", lambda event: self.confirm_yes())
        self.bind("<Y>", lambda event: self.confirm_yes())
        self.bind("<n>", lambda event: self.confirm_no())
        self.bind("<N>", lambda event: self.confirm_no())

        self.log_box = ctk.CTkTextbox(self.dash_frame, width=250, height=300, font=("Consolas", 12))
        self.log_box.pack(pady=20, padx=20)
        self.log_box.insert("0.0", "> System initialized...\n")
        self.log_box.configure(state="disabled")

        self.cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        self.detector = cv2.QRCodeDetector()
        self.update_video()

    def log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"> {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_ui(self, state, title, sub):
        self.status_title.configure(text=title)
        self.status_sub.configure(text=sub)
        if state == "success":
            self.status_title.configure(text_color="#00ff00")
        elif state == "action":
            self.status_title.configure(text_color="#ffcc00")
        elif state == "error":
            self.status_title.configure(text_color="#ff4444")
        else:
            self.status_title.configure(text_color="#00ffcc")

    def show_buttons(self):
        self.btn_frame.pack(pady=10)
        self.btn_yes.pack(side="left", padx=10)
        self.btn_no.pack(side="right", padx=10)

    def hide_buttons(self):
        self.btn_frame.pack_forget()

    # --- INTERACTIVE CONFIRMATION LOGIC ---
    def confirm_yes(self):
        if not self.pending_user_id: return
        
        user_id_to_send = self.pending_user_id
        self.pending_user_id = None
        self.hide_buttons()
        self.set_ui("action", "SENDING...", "Generating secure code...")
        
        # Trigger the email API in the background
        threading.Thread(target=self.api_send_email, args=(user_id_to_send,)).start()

    def confirm_no(self):
        if not self.pending_user_id: return
        
        self.pending_user_id = None
        self.hide_buttons()
        self.set_ui("error", "CANCELLED", "Please step closer to the camera")
        self.log("User rejected AI guess.")
        self.pause_face_until = time.time() + 3.0 # Quick reset so they can try again

    def update_video(self):
        ret, frame = self.cap.read()
        if ret:
            self.process_frame(frame)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(600, 450))
            self.video_label.configure(image=ctk_img)
            self.video_label.image = ctk_img
        self.after(30, self.update_video)

    def process_frame(self, frame):
        now = time.time()
        
        # Don't scan faces or QRs while we are waiting for a YES/NO answer!
        if self.pending_user_id: 
            return

        found, decoded_infos, points, _ = self.detector.detectAndDecodeMulti(frame)
        if found:
            for qr_raw in decoded_infos:
                if not qr_raw: continue
                last_seen = self.recent_qrs.get(qr_raw, 0)
                if now - last_seen > QR_COOLDOWN and not self.is_processing:
                    self.recent_qrs[qr_raw] = now
                    threading.Thread(target=self.api_verify_qr, args=(qr_raw,)).start()

        if now >= self.pause_face_until and now - self.last_face_attempt >= FACE_INTERVAL and not self.is_processing:
            self.last_face_attempt = now
            self.is_processing = True 
            threading.Thread(target=self.api_verify_face, args=(frame,)).start()

    # --- API CALLS ---
    def api_verify_face(self, frame):
        try:
            ok, buffer = cv2.imencode(".jpg", frame)
            files = {"image": ("frame.jpg", buffer.tobytes(), "image/jpeg")}
            data = {"context_id": CONTEXT_ID, "camera_id": CAMERA_ID}
            res = requests.post(f"{API_BASE}/presence/identify", data=data, files=files, timeout=10)
            data = res.json()

            if res.status_code == 200:
                if data.get("verification") == "needs_confirmation":
                    # THE AI IS GUESSING! Ask the user!
                    self.pending_user_id = data.get("user_id")
                    self.set_ui("action", "CONFIRM IDENTITY", f"Are you {data.get('full_name')}?")
                    self.log(f"AI guessed {data.get('full_name')}. Waiting for user...")
                    self.show_buttons()
                    # Pause the camera loop until they press a button
                    self.pause_face_until = time.time() + 60.0 
                    
                elif data.get("verification") == "face_accepted":
                    self.set_ui("success", "FACE ACCEPTED", data.get('full_name'))
                    self.log(f"{data.get('full_name')} logged in.")
                    self.pause_face_until = time.time() + 3.0
            else:
                detail = data.get('detail', 'Unknown error')
                if detail != "Face not recognized":
                    self.set_ui("error", "REJECTED", detail)
        except Exception:
            pass
        finally:
            self.is_processing = False

    def api_send_email(self, user_id):
        try:
            data = {"user_id": user_id, "context_id": CONTEXT_ID}
            res = requests.post(f"{API_BASE}/presence/send-fallback-email", data=data, timeout=10)
            if res.status_code == 200:
                self.set_ui("action", "EMAIL SENT", "Check your phone for the QR code")
                self.log(f"Verification email sent to user!")
                self.pause_face_until = time.time() + FACE_COOLDOWN
            else:
                self.set_ui("error", "EMAIL ERROR", "Failed to send email.")
        except Exception:
            self.set_ui("error", "NETWORK ERROR", "Can't reach backend")
            self.pause_face_until = 0.0

    def api_verify_qr(self, qr_raw):
        self.is_processing = True
        try:
            self.log("QR Detected! Verifying...")
            res = requests.post(f"{API_BASE}/presence/verify-qr", data={"qr_raw": qr_raw, "camera_id": CAMERA_ID}, timeout=10)
            data = res.json()

            if res.status_code == 200:
                self.set_ui("success", "QR SUCCESS", data.get('full_name'))
                self.log(f"{data.get('full_name')} {data.get('action')}")
                self.pause_face_until = 0.0
            else:
                self.set_ui("error", "INVALID QR", data.get('detail'))
                self.log(f"QR Error: {data.get('detail')}")
        except Exception:
            self.set_ui("error", "NETWORK ERROR", "Can't reach backend")
        finally:
            self.is_processing = False

if __name__ == "__main__":
    app = PresenceKiosk()
    app.mainloop()
    app.cap.release()