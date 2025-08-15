# app/backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Tuple, Optional
from app.backend.routers import agents as agents_router
app.include_router(agents_router.router)

import requests, csv, io

app = FastAPI(title="AI Hedge Fund Agents", version="0.1.0")

# === CORS (Step 1) ===
FRONTEND_ORIGIN = "https://ai-hedge-fund-agents-2.onrender.com"  # <-- put your frontend URL here
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Convenience
@app.get("/")
def root():
    return RedirectResponse("/docs")

@app.get("/health")
def health():
    return {"ok": True}

# === SMA Backtest (Step 2) ===

def _stooq_symbol(ticker: str) -> str:
    # US stocks on stooq end with .us (AAPL -> aapl.us)
    return f"{ticker.lower()}.us"

def fetch_prices_stooq(ticker: str) -> List[Tuple[str, float]]:
    sym = _stooq_symbol(ticker)
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    out: List[Tuple[str, float]] = []
    reader = csv.DictReader(io.StringIO(r.text))
    for row in reader:
        if row.get("Close") in (None, "", "0"):
            continue
        out.append((row["Date"], float(row["Close"])))
    out.sort(key=lambda x: x[0])  # ascending by date
    return out

def _within_range(d: str, start: Optional[str], end: Optional[str]) -> bool:
    if start and d < start:
        return False
    if end and d > end:
        return False
    return True

class BacktestRequest(BaseModel):
    ticker: str = "AAPL"
    start: Optional[str] = None      # "YYYY-MM-DD"
    end:   Optional[str] = None
    short_window: int = 20
    long_window:  int = 50
    initial_cash: float = 10_000.0
    fee_bps:  float = 0.0            # e.g. 10 = 0.10%
    slip_bps: float = 0.0            # execution slippage in bps

class EquityPoint(BaseModel):
    t: str
    v: float

class BacktestResponse(BaseModel):
    ticker: str
    equity_curve: List[EquityPoint]
    trades: List[Dict[str, Any]]

def sma(series: List[float], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    s = 0.0
    q: List[float] = []
    for x in series:
        q.append(x); s += x
        if len(q) > window:
            s -= q.pop(0)
        out.append(s/len(q) if len(q) == window else None)
    return out

@app.post("/api/backtest", response_model=BacktestResponse)
def backtest(req: BacktestRequest):
    raw = fetch_prices_stooq(req.ticker)
    data = [(d, p) for (d, p) in raw if _within_range(d, req.start, req.end)]
    if not data:
        return BacktestResponse(ticker=req.ticker, equity_curve=[], trades=[])

    dates = [d for d, _ in data]
    prices = [p for _, p in data]

    s_sma = sma(prices, req.short_window)
    l_sma = sma(prices, req.long_window)

    cash = req.initial_cash
    position = 0
    trades: List[Dict[str, Any]] = []
    equity_curve: List[EquityPoint] = []

    def with_slip(price: float, bps: float, side: str) -> float:
        m = bps / 10_000.0
        return price * (1 + m) if side == "BUY" else price * (1 - m)

    fee_mult = req.fee_bps / 10_000.0

    for i, (d, px) in enumerate(data):
        equity_curve.append(EquityPoint(t=d, v=cash + position * px))

        if s_sma[i] is None or l_sma[i] is None:
            continue

        go_long = s_sma[i] > l_sma[i]
        go_flat = s_sma[i] < l_sma[i]

        if go_long and position == 0:
            exec_px = with_slip(px, req.slip_bps, "BUY")
            qty = int(cash // exec_px)
            if qty > 0:
                cost = qty * exec_px
                fee = cost * fee_mult
                cash -= (cost + fee)
                position += qty
                trades.append({"date": d, "side": "BUY", "qty": qty, "price": exec_px, "fee": fee})

        elif go_flat and position > 0:
            exec_px = with_slip(px, req.slip_bps, "SELL")
            proceeds = position * exec_px
            fee = proceeds * fee_mult
            cash += (proceeds - fee)
            trades.append({"date": d, "side": "SELL", "qty": position, "price": exec_px, "fee": fee})
            position = 0

    # final mark
    d_last, px_last = data[-1]
    equity_curve[-1] = EquityPoint(t=d_last, v=cash + position * px_last)

    return BacktestResponse(ticker=req.ticker, equity_curve=equity_curve, trades=trades)

