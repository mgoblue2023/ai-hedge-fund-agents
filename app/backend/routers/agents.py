# app/backend/routers/agents.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os, re, logging, asyncio, pkgutil, importlib

from app.backend.agents.llm_client import chat as llm_chat

router = APIRouter(prefix="/agents", tags=["agents"])

# ----------------------- Schema -----------------------
class SignalRequest(BaseModel):
    # Accept EITHER a single symbol OR a list of tickers
    symbol: Optional[str] = None
    tickers: Optional[List[str]] = None

    budget: float
    risk: str
    agents: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None
    mode: str = "rule"
    llm_model: Optional[str] = None

    def resolved_tickers(self) -> List[str]:
        if self.tickers:
            ts = [t.strip().upper() for t in self.tickers if t and t.strip()]
            if ts:
                return ts
        if self.symbol and self.symbol.strip():
            return [self.symbol.strip().upper()]
        return []

# ----------------------- Helpers -----------------------
VAL = {"buy": 1, "hold": 0, "sell": -1}

def _parse_action(text: str) -> str:
    if not text:
        return "hold"
    m = re.search(r'final\s*action\s*:\s*(buy|sell|hold)\b', text, re.I)
    if m:
        return m.group(1).lower()
    low = text.lower()
    for kw in ("buy", "sell", "hold"):
        if kw in low:
            return kw
    return "hold"

def _persona_prompt(persona: str, ticker: str, req: SignalRequest) -> str:
    risk = (req.risk or "").lower()
    note = (req.context or {}).get("note", "")
    return (
        f"You are the {persona} agent.\n"
        f"Analyze {ticker} for a 1–3 month swing trade given risk={risk}, budget=${req.budget}.\n"
        f"{'Note: ' + note if note else ''}\n"
        f"Give 2–4 concise sentences of rationale.\n"
        f"Then end with a line exactly like:\n"
        f"Final action: buy|sell|hold"
    )

def persona_agent(persona: str):
    async def run(ticker: str, req: SignalRequest) -> Dict[str, Any]:
        txt = await llm_chat(_persona_prompt(persona, ticker, req), model=req.llm_model)
        txt = (txt or "").strip()
        action = _parse_action(txt)
        return {"agent": persona.lower(), "action": action, "confidence": 0.0, "rationale": txt}
    return run

# ----------------------- Agent registry -----------------------
# Built-in personas (always available)
AGENT_IMPLS: Dict[str, Any] = {
    "buffett": persona_agent("Buffett"),
    "munger": persona_agent("Munger"),
    "technicals": persona_agent("Technicals"),
}

# Also auto-load any modules under app/backend/agents that expose a `run()` function.
# Keys will be the module names (e.g., "value", "quality", "ta", etc.).
try:
    import app.backend.agents as agents_pkg
    for m in pkgutil.iter_modules(agents_pkg.__path__):
        name = m.name
        if name.startswith("_") or name in {"llm_client", "llm_helpers", "router"}:
            continue
        try:
            mod = importlib.import_module(f"app.backend.agents.{name}")
            fn = getattr(mod, "run", None)
            if callable(fn):
                AGENT_IMPLS[name] = fn  # dynamic agent available via its module name
        except Exception as e:
            logging.warning(f"Skipping agent module '{name}': {e}")
except Exception as e:
    logging.warning(f"Could not scan agents package: {e}")

def _select_agents(requested: Optional[List[str]]) -> List[str]:
    if not requested:
        # default to first three registered agents
        return list(AGENT_IMPLS.keys())[:3]
    selected = [a for a in requested if a in AGENT_IMPLS]
    unknown = [a for a in requested if a not in AGENT_IMPLS]
    if unknown:
        logging.warning(f"Ignoring unknown agents: {unknown}")
    if not selected:
        selected = list(AGENT_IMPLS.keys())[:3]
    return selected

async def _run_one_agent(agent_name: str, ticker: str, req: SignalRequest) -> Dict[str, Any]:
    impl = AGENT_IMPLS[agent_name]
    # Try flexible call signatures for dynamically loaded modules
    try:
        if asyncio.iscoroutinefunction(impl):
            return await impl(ticker, req)
        return impl(ticker, req)
    except TypeError:
        try:
            if asyncio.iscoroutinefunction(impl):
                return await impl(ticker=ticker, model=req.llm_model, risk=req.risk, budget=req.budget, context=req.context)
            return impl(ticker=ticker, model=req.llm_model, risk=req.risk, budget=req.budget, context=req.context)
        except Exception as e:
            return {"agent": agent_name, "action": "hold", "confidence": 0.0, "rationale": f"Agent error: {e}"}

def _final_vote(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    # simple average of mapped actions
    score = 0.0
    for d in decisions:
        score += VAL.get(d.get("action"), 0)
    score /= max(1, len(decisions))
    final_vote = "buy" if score > 0.15 else "sell" if score < -0.15 else "hold"
    return {"final_vote": final_vote, "final_score": round(score, 3)}

# ----------------------- Routes -----------------------
@router.post("/signal")
async def signal(req: SignalRequest) -> Dict[str, Any]:
    tickers = req.resolved_tickers()
    if not tickers:
        raise HTTPException(status_code=422, detail="Provide either `tickers` (array) or `symbol` (string).")

    agent_names = _select_agents(req.agents)

    out_results: List[Dict[str, Any]] = []
    for t in tickers:
        decisions: List[Dict[str, Any]] = []
        for a in agent_names:
            try:
                res = await _run_one_agent(a, t, req)
                # normalize shape
                res = {
                    "agent": res.get("agent", a),
                    "action": res.get("action", "hold"),
                    "confidence": float(res.get("confidence", 0.0)),
                    "rationale": res.get("rationale", ""),
                }
            except Exception as e:
                res = {"agent": a, "action": "hold", "confidence": 0.0, "rationale": f"Agent runtime error: {e}"}
            decisions.append(res)

        fv = _final_vote(decisions)
        out_results.append({
            "ticker": t,
            "decisions": decisions,
            **fv
        })

    return {
        "mode": req.mode,
        "llm_model": req.llm_model,
        "results": out_results
    }
