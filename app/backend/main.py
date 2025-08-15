# app/backend/main.py
from fastapi import FastAPI, APIRouter
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

# --- Include routers if present (agents, web). Health is already defined above. ---
# Try routers in app.backend.routers.*
try:
    from app.backend.routers import agents as agents_router
    app.include_router(agents_router.router)
except Exception as e1:
    # Fallback: some repos put agents router at app.backend.agents.router:router
    try:
        from app.backend.agents import router as agents_router2
        app.include_router(agents_router2.router)
    except Exception as e2:
        logging.warning(f"Agents router not loaded: {e1} | fallback: {e2}")

# Optional web/static router if your project has one
try:
    from app.backend.routers import web as web_router
    app.include_router(web_router.router)
except Exception as e:
    logging.warning(f"Web router not loaded: {e}")

# ---------- DEBUG LLM PING (inline drop-in) ----------
from app.backend.agents.llm_client import chat as llm_chat

_debug = APIRouter(prefix="/debug", tags=["debug"])

@_debug.get("/llm-ping")
async def llm_ping(model: str | None = None):
    txt = await llm_chat("Reply with exactly: PONG", model=model)
    return {"ok": True, "model": model, "text": txt}

app.include_router(_debug)
# ---------- END DEBUG LLM PING ----------
