# app/backend/routers/market.py
from fastapi import APIRouter, HTTPException, Query
import httpx
from typing import Dict, Any, List

router = APIRouter(prefix="/market", tags=["market"])

def _as_list(x):
    return x if isinstance(x, list) else (x or [])

@router.get("/prices")
async def get_prices(
    ticker: str = Query(..., min_length=1),
    range: str = Query("1y"),
    interval: str = Query("1d"),
) -> Dict[str, Any]:
    """
    Robust Yahoo Finance proxy that tolerates None/uneven arrays.
    Returns bars as [{t(ms), o,h,l,c,v}].
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": range, "interval": interval, "events": "div,splits"}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, params=params, headers=headers)
    except httpx.RequestError as e:
        raise HTTPException(502, f"Network error contacting Yahoo: {e}") from e

    if r.status_code != 200:
        # Surface upstream error instead of 500
        raise HTTPException(502, f"Yahoo error {r.status_code}: {r.text[:300]}")

    # Parse & normalize
    try:
        data = r.json()
        chart = data.get("chart") or {}
        if chart.get("error"):
            raise HTTPException(502, f"Yahoo chart error: {chart['error']}")
        result = (chart.get("result") or [])[0]
    except Exception as e:
        raise HTTPException(502, f"Unexpected Yahoo payload: {type(e).__name__}: {e} body={r.text[:300]}") from e

    ts = _as_list(result.get("timestamp"))
    indicators = result.get("indicators") or {}
    quotes = _as_list(indicators.get("quote"))
    q0 = quotes[0] if quotes else {}
    opens  = _as_list(q0.get("open"))
    highs  = _as_list(q0.get("high"))
    lows   = _as_list(q0.get("low"))
    closes = _as_list(q0.get("close"))
    vols   = _as_list(q0.get("volume"))

    bars: List[Dict[str, Any]] = []
    n = len(ts)
    for i in range(n):
        c = closes[i] if i < len(closes) else None
        if c is None:
            # skip rows with missing close (common in Yahoo payloads)
            continue
        o = opens[i] if i < len(opens) and opens[i] is not None else c
        h = highs[i] if i < len(highs) and highs[i] is not None else c
        l = lows[i]  if i < len(lows)  and lows[i]  is not None else c
        v = vols[i]  if i < len(vols)  and vols[i]  is not None else 0
        t_ms = ts[i] * 1000
        bars.append({"t": t_ms, "o": o, "h": h, "l": l, "c": c, "v": v})

    if not bars:
        raise HTTPException(404, "No price bars returned for that query.")

    return {
        "ticker": ticker.upper(),
        "range": range,
        "interval": interval,
        "count": len(bars),
        "bars": bars,
    }
