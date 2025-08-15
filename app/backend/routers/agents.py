# app/backend/routers/agents.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from ..agents.base import REGISTRY, AgentResult, ensemble
import asyncio

router = APIRouter(tags=["agents"])

class SignalRequest(BaseModel):
    symbol: str = Field(..., examples=["AAPL"])
    agents: Optional[List[str]] = None  # default: all
    period: str = "1y"
    interval: str = "1d"
    context: Dict[str, Any] = {}

class SignalResponse(BaseModel):
    symbol: str
    results: List[AgentResult]
    ensemble: Dict[str, Any]

@router.get("/agents", response_model=Dict[str, Dict[str, str]])
async def list_agents():
    return {name: {"kind": ag.kind} for name, ag in REGISTRY.items()}

@router.post("/agents/signal", response_model=SignalResponse)
async def run_signals(req: SignalRequest):
    names = req.agents or list(REGISTRY.keys())
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown agents: {unknown}")
    async def _go(n: str):
        ag = REGISTRY[n]
        ctx = {**req.context, "period": req.period, "interval": req.interval}
        return await ag.run(req.symbol, ctx)
    results = await asyncio.gather(*[_go(n) for n in names])
    return SignalResponse(symbol=req.symbol, results=results, ensemble=ensemble(results))
