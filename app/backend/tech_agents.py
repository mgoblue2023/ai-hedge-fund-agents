# app/backend/agents/tech_agent.py
from .base import AgentResult, register
from typing import Dict, Any
import pandas as pd

def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()

def _rsi(s: pd.Series, n: int=14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    down = -d.clip(upper=0).ewm(alpha=1/n, adjust=False).mean()
    rs = up / (down + 1e-9)
    return 100 - (100 / (1 + rs))

def _load_prices(symbol: str, period="1y", interval="1d") -> pd.DataFrame:
    try:
        import yfinance as yf
    except Exception:
        raise RuntimeError("yfinance not installed. Add yfinance to backend dependencies.")
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

class TechnicalsAgent:
    name = "technicals"
    kind = "rule"
    async def run(self, symbol: str, context: Dict[str, Any]) -> AgentResult:
        period = context.get("period","1y"); interval = context.get("interval","1d")
        df = _load_prices(symbol, period, interval)
        if df.empty: 
            return AgentResult(agent=self.name, decision="HOLD", confidence=0.3, rationale="No price data.")
        close = df["Close"]
        sma20, sma50 = _sma(close, 20), _sma(close, 50)
        rsi = _rsi(close, 14)

        cross_up   = sma20.iloc[-2] < sma50.iloc[-2] and sma20.iloc[-1] > sma50.iloc[-1]
        cross_down = sma20.iloc[-2] > sma50.iloc[-2] and sma20.iloc[-1] < sma50.iloc[-1]
        overbought = rsi.iloc[-1] > 70
        oversold   = rsi.iloc[-1] < 30

        score, why = 0.0, []
        if cross_up:   score += 0.5; why.append("20>50 SMA bullish cross")
        if cross_down: score -= 0.5; why.append("20<50 SMA bearish cross")
        if oversold:   score += 0.3; why.append("RSI oversold")
        if overbought: score -= 0.3; why.append("RSI overbought")

        decision   = "BUY" if score > 0.2 else "SELL" if score < -0.2 else "HOLD"
        confidence = min(1.0, abs(score))
        rationale  = ", ".join(why) or "Mixed signals"
        return AgentResult(agent=self.name, decision=decision, confidence=confidence, rationale=rationale)

register(TechnicalsAgent())
