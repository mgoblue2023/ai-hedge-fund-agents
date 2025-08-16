# app/backend/routers/backtest.py
from fastapi import APIRouter, HTTPException
import httpx, math
from typing import Dict, Any, List

router = APIRouter(prefix="/backtest", tags=["backtest"])

def _sma(vals: List[float | None], n: int) -> List[float | None]:
    out, s = [], 0.0
    q: List[float] = []
    for x in vals:
        if x is None:
            out.append(None)
            continue
        q.append(x); s += x
        if len(q) > n:
            s -= q.pop(0)
        out.append(s/len(q) if len(q) >= n else None)
    return out

@router.post("/sma")
async def sma_backtest(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simple moving-average crossover demo backtest.
    Body: { symbol, range='1y', fast=20, slow=50, initial_cash=10000 }
    """
    symbol = (payload.get("symbol") or payload.get("ticker") or "").upper()
    if not symbol:
        raise HTTPException(422, "symbol required")
    rng = str(payload.get("range", "1y"))
    fast = int(payload.get("fast", 20))
    slow = int(payload.get("slow", 50))
    cash0 = float(payload.get("initial_cash", 10000))

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": rng, "interval": "1d"}
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.get(url, params=params, headers=headers)
    if r.status_code != 200:
        raise HTTPException(502, f"Yahoo error {r.status_code}: {r.text[:200]}")
    data = r.json()
    result = (data.get("chart") or {}).get("result") or []
    if not result:
        raise HTTPException(502, "Yahoo returned no result")

    res = result[0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]

    sma_fast = _sma(closes, fast)
    sma_slow = _sma(closes, slow)

    pos = 0  # shares
    bal = cash0
    trades: List[Dict[str, Any]] = []
    equity: List[Dict[str, Any]] = []

    for i, t in enumerate(ts):
        c = closes[i]
        f, s = sma_fast[i], sma_slow[i]
        if c is None or f is None or s is None:
            equity.append({"t": t*1000, "equity": bal + (pos*c if c else 0.0)})
            continue

        # Signals: long when fast>slow, flat when fast<slow
        long = 1 if f > s else 0
        have = 1 if pos > 0 else 0

        # Enter
        if long and not have:
            shares = math.floor(bal / c)
            if shares > 0:
                pos = shares
                bal -= shares * c
                trades.append({"t": t*1000, "side": "buy", "price": c, "shares": shares})

        # Exit
        if not long and have:
            bal += pos * c
            trades.append({"t": t*1000, "side": "sell", "price": c, "shares": pos})
            pos = 0

        equity.append({"t": t*1000, "equity": bal + pos * c})

    # Liquidate at end if still long
    if pos > 0 and closes[-1] is not None:
        bal += pos * closes[-1]
        trades.append({"t": ts[-1]*1000, "side": "sell", "price": closes[-1], "shares": pos})
        pos = 0

    return {
        "symbol": symbol,
        "range": rng,
        "fast": fast,
        "slow": slow,
        "initial_cash": cash0,
        "final_equity": round(bal, 2),
        "trades": trades,
        "equity": equity
    }
