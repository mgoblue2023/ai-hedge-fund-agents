
# app/backend/agents/router.py
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import os, hashlib

try:
    import httpx  # optional; if missing we use rule-based mode
except Exception:
    httpx = None

router = APIRouter(prefix="/agents", tags=["agents"])

# ---------- Models ----------
class SignalIn(BaseModel):
    tickers: List[str] = Field(..., description="Tickers to score, e.g. ['AAPL','MSFT']")
    budget: Optional[float] = 10000
    risk: Optional[str] = Field("medium", description="'low'|'medium'|'high'")
    agents: Optional[List[str]] = Field(default=["buffett","munger","technicals"])
    context: Optional[Dict[str, Any]] = None  # optional extra notes/fundamentals you pass in

class AgentDecision(BaseModel):
    agent: str
    action: str           # 'buy'|'hold'|'sell'
    confidence: float     # 0..1
    rationale: str

class TickerDecision(BaseModel):
    ticker: str
    decisions: List[AgentDecision]
    final_vote: str       # 'buy'|'hold'|'sell'
    final_score: float    # weighted vote score

class SignalOut(BaseModel):
    mode: str             # 'rule-based' or 'llm'
    llm_model: Optional[str] = None
    results: List[TickerDecision]

# ---------- Helpers ----------
def _stable_score(key: str) -> float:
    """Deterministic 0..1 score per (agent,ticker) so results are stable across runs."""
    h = hashlib.sha256(key.encode()).hexdigest()
    return (int(h[:8], 16) % 1000) / 1000.0

def _rule_based_decision(agent: str, ticker: str) -> AgentDecision:
    s = _stable_score(f"{agent}:{ticker}")
    if s > 0.66:
        action = "buy"
    elif s < 0.33:
        action = "sell"
    else:
        action = "hold"
    conf = round(abs(s - 0.5) * 2, 2)  # 0..1
    why = f"Placeholder {agent} heuristic; score={s:.2f}. Replace with real logic/LLM anytime."
    return AgentDecision(agent=agent, action=action, confidence=conf, rationale=why)

async def _llm_decision(agent: str, ticker: str, context: Optional[Dict[str, Any]]) -> AgentDecision:
    """Calls OpenAI if OPENAI_API_KEY is set and httpx is installed, else falls back."""
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key or httpx is None:
        return _rule_based_decision(agent, ticker)

    prompt = (
        f"You are an investing persona named {agent}. "
        f"Decide BUY/HOLD/SELL for {ticker} over the next 1-3 months. "
        f"Use this optional context: {context or {}}. "
        "Return JSON with keys: action (buy|hold|sell), confidence (0..1), reason."
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
        data = r.json()
        content = data["choices"][0]["message"]["content"]

        import json
        j = json.loads(content)
        action = str(j.get("action", "hold")).lower()
        confidence = float(j.get("confidence", 0.5))
        reason = j.get("reason", "LLM rationale.")
        confidence = max(0.0, min(confidence, 1.0))
        if action not in {"buy","hold","sell"}:
            action = "hold"
        return AgentDecision(agent=agent, action=action, confidence=confidence, rationale=reason)
    except Exception as e:
        return AgentDecision(agent=agent, action="hold", confidence=0.0, rationale=f"LLM call failed: {e}")

# ---------- Endpoints ----------
@router.get("/ping")
def ping():
    return {"ok": True, "agents": ["buffett", "munger", "technicals"]}

@router.post("/signal", response_model=SignalOut)
async def signal(body: SignalIn):
    use_llm = bool(os.getenv("OPENAI_API_KEY")) and (httpx is not None)
    mode = "llm" if use_llm else "rule-based"
    results: List[TickerDecision] = []

    for t in body.tickers:
        decisions: List[AgentDecision] = []
        for a in body.agents:
            if use_llm:
                dec = await _llm_decision(a, t, body.context)
            else:
                dec = _rule_based_decision(a, t)
            decisions.append(dec)

        # Weighted vote: buy=+1, sell=-1, hold=0 (weighted by confidence)
        score = sum((1 if d.action=="buy" else -1 if d.action=="sell" else 0) * d.confidence for d in decisions)
        final = "buy" if score > 0.15 else "sell" if score < -0.15 else "hold"
        results.append(TickerDecision(ticker=t, decisions=decisions, final_vote=final, final_score=round(score, 3)))

    return SignalOut(mode=mode, llm_model=os.getenv("OPENAI_MODEL") if mode=="llm" else None, results=results)
