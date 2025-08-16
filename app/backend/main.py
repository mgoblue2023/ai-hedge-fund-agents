# app/backend/main.py
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os, logging, pkgutil, importlib

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
    return {"service": "ai-hedge-fund-agents", "ok": True, "ui": "/web"}

# --- Try to include your existing agents/web routers (optional) ---
try:
    from app.backend.routers import agents as agents_router
    app.include_router(agents_router.router)
except Exception as e1:
    try:
        from app.backend.agents import router as agents_router2
        app.include_router(agents_router2.router)
    except Exception as e2:
        logging.warning(f"Agents router not loaded: {e1} | fallback: {e2}")

try:
    from app.backend.routers import web as web_router
    app.include_router(web_router.router)
except Exception as e:
    logging.warning(f"Web router not loaded: {e}")

# --- Include market/backtest routers (these are the new ones you added) ---
try:
    from app.backend.routers import market as market_router
    app.include_router(market_router.router)
except Exception as e:
    logging.warning(f"Market router not loaded: {e}")

try:
    from app.backend.routers import backtest as backtest_router
    app.include_router(backtest_router.router)
except Exception as e:
    logging.warning(f"Backtest router not loaded: {e}")

# ======================= DEBUG ROUTES =======================
_debug = APIRouter(prefix="/debug", tags=["debug"])

# /debug/llm-ping
try:
    from app.backend.agents.llm_client import chat as llm_chat
except Exception as import_err:
    @_debug.get("/llm-ping")
    async def llm_ping_import_error():
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "phase": "import",
                "error": f"{type(import_err).__name__}: {import_err}",
                "hint": "Ensure app/backend/agents/llm_client.py exists and packages have __init__.py",
            },
        )
else:
    @_debug.get("/llm-ping")
    async def llm_ping(model: str | None = None):
        try:
            txt = await llm_chat("Reply with exactly: PONG", model=model)
            return {"ok": True, "model": model, "text": txt}
        except Exception as e:
            logging.exception("llm-ping failed")
            return JSONResponse(
                status_code=200,
                content={
                    "ok": False,
                    "phase": "call",
                    "error": f"{type(e).__name__}: {e}",
                    "has_OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
                    "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "openai"),
                    "OPENAI_BASE_URL": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                    "LLM_MODEL_default": os.getenv("LLM_MODEL", "gpt-4o-mini"),
                    "hint": "401=bad key, 404=model not allowed, 429=quota. Use LLM_MOCK=1 to develop without API.",
                },
            )

# /debug/agents-available
@_debug.get("/agents-available")
def debug_agents_available():
    try:
        import app.backend.agents as agents_pkg
    except Exception as e:
        return {"ok": False, "error": f"ImportError: {e}", "agents_by_module": []}

    names = []
    try:
        for m in pkgutil.iter_modules(agents_pkg.__path__):
            name = m.name
            if name.startswith("_") or name in {"llm_client", "llm_helpers", "router", "generic"}:
                continue
            names.append(name)
    except Exception as e:
        return {"ok": False, "error": f"ScanError: {e}", "agents_by_module": []}
    return {"ok": True, "agents_by_module": sorted(names)}

# /debug/agents-registry
def _find_registry_keys():
    candidates = [
        "app.backend.routers.agents",
        "app.backend.agents.router",
        "app.backend.agents",
        "app.backend.agents.registry",
    ]
    possible_names = ["AGENT_IMPLS", "AGENT_MAP", "AGENTS", "AGENT_REGISTRY"]
    results = []
    for modpath in candidates:
        try:
            mod = importlib.import_module(modpath)
        except Exception:
            continue
        for varname in possible_names:
            val = getattr(mod, varname, None)
            if isinstance(val, dict) and val:
                results.append({"module": modpath, "variable": varname, "keys": list(val.keys())})
    return results

@_debug.get("/agents-registry")
def debug_agents_registry():
    found = _find_registry_keys()
    if not found:
        return {
            "ok": False,
            "found": [],
            "hint": "Could not locate a registry dict (AGENT_IMPLS/AGENT_MAP/AGENTS). "
                    "Use /debug/agents-available for module names, or share your /agents/signal handler so we can wire it."
        }
    return {"ok": True, "found": found}

app.include_router(_debug)
# ===================== END DEBUG ROUTES =====================

# --- Static UI at /web ---
app.mount("/web", StaticFiles(directory="web", html=True), name="web")
