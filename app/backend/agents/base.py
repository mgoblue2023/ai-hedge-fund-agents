# app/backend/agents/base.py
from typing import Protocol, Dict, Any, List
from pydantic import BaseModel

class AgentResult(BaseModel):
    agent: str
    decision: str  # BUY | HOLD | SELL
    confidence: float  # 0..1
    rationale: str

class Agent(Protocol):
    name: str
    kind: str  # "llm" | "rule"
    async def run(self, symbol: str, context: Dict[str, Any]) -> AgentResult: ...

REGISTRY: Dict[str, Agent] = {}

def register(agent: Agent):
    REGISTRY[agent.name] = agent
    return agent

def ensemble(results: List[AgentResult]) -> Dict[str, Any]:
    if not results:
        return {"decision": "HOLD", "score": 0.0, "confidence": 0.0}
    score_map = {"BUY": 1.0, "HOLD": 0.0, "SELL": -1.0}
    avg = sum(score_map[r.decision] * max(0.2, min(1.0, r.confidence)) for r in results) / len(results)
    decision = "BUY" if avg > 0.2 else "SELL" if avg < -0.2 else "HOLD"
    return {"decision": decision, "score": avg, "confidence": min(1.0, abs(avg))}
