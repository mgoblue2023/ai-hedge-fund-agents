# app/backend/main.py
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging

app = FastAPI(title="AI Hedge Fund Agents", version="0.1.0")

# --- CORS ---
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

# --- Include routers if present (agents, web). Health is defined above. ---
try:
    # Common location: app/backend/routers/agents.py -> router = APIRouter(prefix="/agents")
    from app.backend.routers import agents as agents_router
    app.include_router(agents_router.router)
except Exception as e1:
    # Fallback: some repos keep it at app/backend/agents/router.py -> router
    try:
        from app.backend.agents import router as agents_router2
        app.include_router(agents_router2.router)
    except Exception as e2:
        logging.warning(f"Agents router not loaded: {e1} | fallback: {e2}")

# Optional web/static router if you have one
try:
    from app.backend.routers import web as web_router
    app.include_router(web_router.router)
except Exception as e:
    logging.warning(f"Web router not loaded: {e}")

# ---------- DEBUG LLM PING (inline; safe diagnostics) ----------
try:
    from app.backend.agents.llm_client import chat as llm_chat
except Exception as import_err:
    # If the client can't import, expose that clearly.
    _debug = APIRouter(prefix="/debug", tags=["debug"])

    @_debug.get("/llm-ping")
    async def llm_ping_import_error():
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "phase": "import",
                "error": f"{type(import_err).__name__}: {import_err}",
                "hint": "Ensure app/backend/agents/llm_client.py exists and packages have __init__.py"
            },
        )

    app.include_router(_debug)
else:
    _debug = APIRouter(prefix="/debug", tags=["debug"])

    @_debug.get("/llm-ping")
    async def llm_ping(model: str | None = None):
        """
        Calls the LLM and returns diagnostics instead of throwing 500s,
        so we can see what's wrong (key, model, rate limit, etc).
        """
        try:
            txt = await llm_chat("Reply with exactly: PONG", model=model)
            return {"ok": True, "model": model, "text": txt}
        except Exception as e:
            logging.exception("llm-ping failed")
            return JSONResponse(
                status_code=200,  # keep 200 so Swagger shows the body
                content={
                    "ok": False,
                    "phase": "call",
                    "error": f"{type(e).__name__}: {e}",
                    "has_OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
                    "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "openai"),
                    "OPENAI_BASE_URL": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                    "LLM_MODEL_default": os.getenv("LLM_MODEL", "gpt-4o-mini"),
                    "hint": "401=bad key, 404=model not allowed, 429=rate limit. Check Render env & redeploy.",
                },
            )

    app.include_router(_debug)
# ---------- END DEBUG LLM PING ----------

# ---------- DEBUG: list available agent modules ----------
import pkgutil, importlib, types
import app.backend.agents as agents_pkg

@_debug.get("/agents-available")
def debug_agents_available():
    """
    Lists Python modules under app/backend/agents. Often these map to the agent keys
    your /agents/signal endpoint expects (e.g., 'value', 'quality', 'ta', etc.).
    """
    names = []
    try:
        for m in pkgutil.iter_modules(agents_pkg.__path__):
            name = m.name
            if name.startswith("_") or name in ("llm_client", "llm_helpers", "generic", "router"):
                continue
            names.append(name)
    except Exception as e:
        names.append(f"(error scanning agents package: {e})")
    return {"agents_by_module": sorted(names)}
# ---------- END DEBUG ----------

