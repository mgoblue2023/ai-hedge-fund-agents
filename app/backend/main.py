# app/backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging

app = FastAPI(title="AI Hedge Fund Agents", version="0.1.0")

# --- CORS ---
# Allow your frontend; if FRONTEND_URL isn't set, allow all (ok during dev)
frontend_url = os.getenv("FRONTEND_URL")
allow_origins = [frontend_url] if frontend_url else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Health & root ---
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/")
def root():
    return {"service": "ai-hedge-fund-agents", "ok": True}

# --- Routers (load after app exists!) ---
try:
    # If your router lives at app/backend/agents/router.py with "router = APIRouter(prefix='/agents')"
    from .agents import router as agents_router  # relative import because we run as app.backend.main
    app.include_router(agents_router.router)     # don't add prefix again if it's in the file
except Exception as e:
    logging.warning(f"Agents router not loaded: {e}")
