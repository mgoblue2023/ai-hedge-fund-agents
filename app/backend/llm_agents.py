# app/backend/agents/llm_agents.py
from .base import AgentResult, register
from ..llm import have_llm, call_openai
from typing import Dict, Any
import re

def _extract_vote(text: str) -> str:
    t = text.upper()
    if "SELL" in t and "BUY" not in t: return "SELL"
    if "BUY" in t and "SELL" not in t: return "BUY"
    return "HOLD"

def _extract_conf(text: str) -> float:
    m = re.search(r"confidence\s*[:=]\s*(\d{1,3})\s*%", text, re.I)
    if m:
        v = int(m.group(1))
        return max(0, min(100, v))/100.0
    return 0.5

class BuffettAgent:
    name = "buffett"
    kind = "llm"
    async def run(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        if not have_llm():
            return AgentResult(agent=self.name, decision="HOLD", confidence=0.3, rationale="LLM not configured; defaulting to HOLD.")
        prompt = f"""
Stock: {symbol}
Context: {context.get('summary','n/a')}

Act like Warren Buffett. Focus on durable competitive advantage, ROIC, debt, earnings stability, management quality, and fair price.
Respond with 3 short bullets. End with:
Decision: BUY/HOLD/SELL
Confidence: NN%
"""
        out = await call_openai(prompt, temperature=0.2, system="You are Warren Buffett-ish but concise and practical.")
        return AgentResult(agent=self.name, decision=_extract_vote(out), confidence=_extract_conf(out), rationale=out[:480])

register(BuffettAgent())

class MungerAgent:
    name = "munger"
    kind = "llm"
    async def run(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        if not have_llm():
            return AgentResult(agent=self.name, decision="HOLD", confidence=0.3, rationale="LLM not configured; defaulting to HOLD.")
        prompt = f"""
Stock: {symbol}
Context: {context.get('summary','n/a')}

Act like Charlie Munger. Emphasize mental models, inversion, incentives, and avoiding stupidity.
Respond with 3 crisp points. End with:
Decision: BUY/HOLD/SELL
Confidence: NN%
"""
        out = await call_openai(prompt, temperature=0.3, system="You are Charlie Munger-ish: blunt, analytical, concise.")
        return AgentResult(agent=self.name, decision=_extract_vote(out), confidence=_extract_conf(out), rationale=out[:480])

register(MungerAgent())
