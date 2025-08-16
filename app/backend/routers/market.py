# app/backend/routers/market.py
from fastapi import APIRouter, HTTPException
import httpx
from typing import Dict, Any, List

router = APIRouter(prefix="/market", tags=["market"])

@router.get("/prices")
async def get_prices(ticker: str, range: str = "1y", interval: str = "1d") -> Dict[str, Any]:
    """
    Server-side proxy to Yahoo Finance chart API.
    Returns OHLCV bars as [{t(ms), o,h,l,c,v}].
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": range, "interval": interval}
    headers = {"User-Agent": "Mozilla/5.0"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params, headers=headers)
    if r.status_code != 200:
        raise HTTPException(502, f"Yahoo error {r.status_code}: {r.text[:200]}")
    data = r.json()
    result = (data.get("chart") or {}).get("result") or []
    if not result:
        raise HTTPException(502, "Yahoo returned no result")

    res = result[0]
    ts = res.get("timestamp") or []
    q = (res.get("indicators") or {}).get("quote") or [{}]
    q0 = q[0] if q else {}
    opens = q0.get("open") or []
    highs = q0.get("high") or []
    lows  = q0.get("low") or []
    closes= q0.get("close") or []
    vols  = q0.get("volume") or []

    bars: List[Dict[str, Any]] = []
    for i in range(len(ts)):
        if closes[i] is None:  # skip missing close rows
            continue
        bars.append({
            "t": ts[i]*1000, "o": opens[i], "h": highs[i], "l": lows[i], "c": closes[i], "v": vols[i],
        })

    return {"ticker": ticker.upper(), "range": range, "interval": interval, "bars": bars}
