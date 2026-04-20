from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse  # <-- 1. IMPORT THIS

from app.api.presence import router as presence_router
from app.core.config import get_settings
from app.core.database import create_db_and_tables

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --- 2. UPDATE THIS ROUTE ---
@app.get("/")
def root():
    # This tells FastAPI to serve your index.html file when you visit the base URL!
    return FileResponse("index.html")

app.include_router(presence_router)