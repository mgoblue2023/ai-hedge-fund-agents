# app/backend/routers/market.py
from fastapi import APIRouter, HTTPException, Query
import httpx, logging
from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone

router = APIRouter(prefix="/market", tags=["market"])

def _as_list(x):
    return x if isinstance(x, list) else (x or [])

def _range_to_lookback_days(r: str) -> int:
    r = (r or "").lower()
    return {
        "1mo": 22, "3mo": 66, "6mo": 126, "ytd": 252, "1y": 252,
        "2y": 504, "5y": 1260, "10y": 2520
    }.get(r, 252)

# ---------------------- Yahoo v8 chart ----------------------
async def _fetch_yahoo_bars(ticker: str, rng: str, interval: str) -> List[Dict[str, Any]]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": rng, "interval": interval, "events": "div,splits"}
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params, headers=headers)
    if r.status_code != 200:
        raise HTTPException(502, f"Yahoo error {r.status_code}: {r.text[:300]}")

    try:
        data = r.json()
        chart = data.get("chart") or {}
        if chart.get("error"):
            raise HTTPException(502, f"Yahoo chart error: {chart['error']}")
        results = chart.get("result") or []
        if not results:
            raise HTTPException(502, "Yahoo returned empty result")

        res = results[0]
        ts = _as_list(res.get("timestamp"))
        indicators = res.get("indicators") or {}
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
                continue
            o = opens[i] if i < len(opens) and opens[i] is not None else c
            h = highs[i] if i < len(highs) and highs[i] is not None else c
            l = lows[i]  if i < len(lows)  and lows[i]  is not None else c
            v = vols[i]  if i < len(vols)  and vols[i]  is not None else 0
            t_ms = ts[i] * 1000
            bars.append({"t": t_ms, "o": o, "h": h, "l": l, "c": c, "v": v})

        if not bars:
            raise HTTPException(404, "Yahoo returned no price bars.")
        return bars
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Yahoo parse error")
        raise HTTPException(502, f"Unexpected Yahoo payload: {type(e).__name__}: {e} body={r.text[:300]}")

# ---------------------- Stooq CSV fallback ----------------------
def _parse_stooq_csv(csv_text: str) -> List[Tuple[int, float, float, float, float, int]]:
    """
    Returns list of (t_ms, o,h,l,c,v) sorted ascending.
    CSV columns: Date,Open,High,Low,Close,Volume
    """
    rows = []
    lines = csv_text.strip().splitlines()
    if not lines or len(lines) < 2:
        return rows
    for line in lines[1:]:
        parts = line.strip().split(',')
        if len(parts) < 6:
            continue
        d, o, h, l, c, v = parts[:6]
        try:
            t_ms = int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
            o = float(o); h = float(h); l = float(l); c = float(c); v = int(float(v))
            rows.append((t_ms, o, h, l, c, v))
        except Exception:
            continue
    rows.sort(key=lambda x: x[0])
    return rows

def _stooq_candidates(tkr: str) -> List[str]:
    """
    Stooq often needs the '.us' suffix for US symbols (e.g., aapl.us).
    Try both plain lower and lower+'.us'.
    """
    t = (tkr or "").lower()
    cands = [t]
    if not t.endswith(".us"):
        cands.append(f"{t}.us")
    return cands

async def _fetch_stooq_bars(ticker: str, rng: str) -> List[Dict[str, Any]]:
    candidates = _stooq_candidates(ticker)
    last_err = None
    async with httpx.AsyncClient(timeout=20.0) as client:
        for sym in candidates:
            url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and "Date,Open,High,Low,Close,Volume" in r.text:
                rows = _parse_stooq_csv(r.text)
                if rows:
                    lookback = _range_to_lookback_days(rng)
                    rows = rows[-lookback:]
                    return [{"t": t, "o": o, "h": h, "l": l, "c": c, "v": v} for (t, o, h, l, c, v) in rows]
            last_err = f"{r.status_code}: {r.text[:120]}"
    raise HTTPException(404, f"Stooq returned no rows for {ticker} (tried {candidates}). Last: {last_err}")

# ---------------------- Public endpoint ----------------------
@router.get("/prices")
async def get_prices(
    ticker: str = Query(..., min_length=1),
    range: str = Query("1y"),
    interval: str = Query("1d"),
    source: str = Query("auto", regex="^(auto|yahoo|stooq)$"),
) -> Dict[str, Any]:
    """
    Returns OHLCV bars as [{t(ms), o,h,l,c,v}].
    - source=auto: try Yahoo, then Stooq
    - source=yahoo: force Yahoo
    - source=stooq: force Stooq
    """
    tkr = (ticker or "").upper().strip()
    if not tkr:
        raise HTTPException(422, "ticker is required")

    errors: Dict[str, str] = {}
    bars: List[Dict[str, Any]] = []
    src = None

    try:
        if source in ("auto", "yahoo"):
            bars = await _fetch_yahoo_bars(tkr, range, interval)
            src = "yahoo"
    except HTTPException as e:
        errors["yahoo"] = f"{e.status_code}: {e.detail}"
    except Exception as e:
        logging.exception("Yahoo unexpected failure")
        errors["yahoo"] = f"500: {e}"

    if not bars and source in ("auto", "stooq"):
        try:
            bars = await _fetch_stooq_bars(tkr, range)
            src = "stooq"
        except HTTPException as e:
            errors["stooq"] = f"{e.status_code}: {e.detail}"
        except Exception as e:
            logging.exception("Stooq unexpected failure")
            errors["stooq"] = f"500: {e}"

    if not bars:
        raise HTTPException(502, {"message": "Failed to fetch prices from all sources.", "errors": errors})

    return {
        "ticker": tkr,
        "range": range,
        "interval": interval,
        "source": src,
        "count": len(bars),
        "bars": bars,
    }
