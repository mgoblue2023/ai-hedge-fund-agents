# app/backend/main.py
import logging
import importlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
log = logging.getLogger("app.backend.main")
logging.basicConfig(level=logging.INFO)

# Helpful startup message (keeps parity with the logs you saw)
def _check_ollama():
    try:
        import shutil  # stdlib
        if shutil.which("ollama") is None:
            log.info("ℹ Ollama is not installed. Install it to use local models.")
            log.info("ℹ Visit https://ollama.com to download and install Ollama")
    except Exception as e:
        log.info("ℹ Ollama check skipped: %s", e)

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(title="AI Hedge Fund Agents", version="0.1.0")

# --- Minimal API that the UI can call ---

from pydantic import BaseModel
from typing import List, Dict, Any

# Components list for the right panel (very simple stub)
@app.get("/api/components")
def get_components() -> Dict[str, Any]:
    return {
        "components": [
            {
                "id": "sma-backtest",
                "name": "SMA Backtest",
                "description": "Runs a simple moving-average backtest.",
            },
            {
                "id": "echo",
                "name": "Echo",
                "description": "Returns whatever you send (debug).",
            },
        ]
    }

# Simple backtest stub so you can see data flow through
class BacktestRequest(BaseModel):
    ticker: str = "AAPL"
    start: str = "2022-01-01"
    end:   str = "2022-01-31"

class EquityPoint(BaseModel):
    t: str
    v: float

class BacktestResponse(BaseModel):
    ticker: str
    equity_curve: List[EquityPoint]

@app.post("/api/backtest", response_model=BacktestResponse)
def backtest(req: BacktestRequest):
    # Dummy curve (increasing line) – replace with real logic later
    pts = [EquityPoint(t=f"2022-01-{d:02d}", v=100.0 + d * 0.6) for d in range(1, 31)]
    return BacktestResponse(ticker=req.ticker, equity_curve=pts)


# CORS (open; tighten origins later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Health & root — declared BEFORE any optional router includes
# -----------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok", "service": "ai-hf-agents-backend"}

@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True}

@app.get("/__ping", include_in_schema=False)
def __ping():
    return {"ok": True}

# -----------------------------------------------------------------------------
# Optional: include your project routers if/when they exist.
# This won't crash deploys if the module or 'router' isn't present.
# -----------------------------------------------------------------------------
def _safe_include(module_path: str, router_name: str = "router", prefix: str = ""):
    try:
        mod = importlib.import_module(module_path)
        router = getattr(mod, router_name)
        app.include_router(router, prefix=prefix)
        log.info("Included router '%s' from %s with prefix '%s'", router_name, module_path, prefix)
    except Exception as e:
        log.info("Skipping router from %s: %s", module_path, e)

# Examples (uncomment or adjust to match your repo once those routers are in place):
# _safe_include("app.backend.api", prefix="/api")
# _safe_include("app.backend.routes.api", prefix="/api")
# _safe_include("app.backend.endpoints.backtest", prefix="/backtest")

# -----------------------------------------------------------------------------
# Guarded OpenAPI so /docs never 502s even if a router has bad type hints.
# -----------------------------------------------------------------------------
def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    try:
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description="Backend for AI Hedge Fund Agents",
            routes=app.routes,
        )
        app.openapi_schema = schema
        return schema
    except Exception as e:
        log.error("OpenAPI generation failed: %s", e)
        # Minimal fallback so /docs still loads
        fallback = {
            "openapi": "3.0.0",
            "info": {"title": app.title, "version": app.version},
            "paths": {
                "/": {"get": {"responses": {"200": {"description": "OK"}}}},
                "/health": {"get": {"responses": {"200": {"description": "OK"}}}},
                "/__ping": {"get": {"responses": {"200": {"description": "OK"}}}},
            },
        }
        app.openapi_schema = fallback
        return fallback

app.openapi = _custom_openapi

# -----------------------------------------------------------------------------
# Startup hooks
# -----------------------------------------------------------------------------
@app.on_event("startup")
def _on_startup():
    _check_ollama()
    log.info("Application startup complete.")
