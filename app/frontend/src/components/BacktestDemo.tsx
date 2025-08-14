import { useMemo, useState } from 'react';

type EquityPoint = { t: string; v: number };
type Trade = { date: string; side: 'BUY' | 'SELL'; qty: number; price: number; fee: number };

type BacktestResponse = {
  ticker: string;
  equity_curve: EquityPoint[];
  trades: Trade[];
};

const API =
  (import.meta as any)?.env?.VITE_API_BASE ||
  (window as any).VITE_API_BASE ||
  'https://ai-hedge-fund-agents-1.onrender.com'; // fallback; replace if different

export default function BacktestDemo() {
  const [ticker, setTicker] = useState('AAPL');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [shortWin, setShortWin] = useState(20);
  const [longWin, setLongWin] = useState(50);
  const [feeBps, setFeeBps] = useState(5);
  const [slipBps, setSlipBps] = useState(5);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const body: any = {
        ticker,
        short_window: shortWin,
        long_window: longWin,
        fee_bps: feeBps,
        slip_bps: slipBps,
      };
      if (start) body.start = start;
      if (end) body.end = end;

      const r = await fetch(`${API}/api/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(await r.text());
      const json = (await r.json()) as BacktestResponse;
      setData(json);
    } catch (e: any) {
      setError(e?.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  }

  // --- Stats from equity + trades ---
  const stats = useMemo(() => {
    const eq = data?.equity_curve ?? [];
    if (eq.length < 2) return null;

    const startV = eq[0].v;
    const endV = eq[eq.length - 1].v;
    const totalReturn = (endV / startV - 1) * 100;

    // Max drawdown
    let peak = -Infinity;
    let maxDD = 0;
    for (const p of eq) {
      if (p.v > peak) peak = p.v;
      if (peak > 0) {
        const dd = (peak - p.v) / peak;
        if (dd > maxDD) maxDD = dd;
      }
    }
    const maxDrawdownPct = maxDD * 100;

    // Win rate over round trips (BUY -> SELL)
    const trades = data?.trades ?? [];
    let wins = 0;
    let losses = 0;
    for (let i = 0; i < trades.length; i++) {
      const buy = trades[i];
      if (buy.side !== 'BUY') continue;
      let j = i + 1;
      while (j < trades.length && trades[j].side !== 'SELL') j++;
      if (j < trades.length) {
        const sell = trades[j];
        const qty = Math.min(buy.qty, sell.qty); // be safe
        const pnl = (sell.price - buy.price) * qty - (buy.fee + sell.fee);
        if (pnl > 0) wins++; else losses++;
        i = j; // skip ahead to after the SELL
      } else {
        break;
      }
    }
    const roundTrips = wins + losses;
    const winRate = roundTrips > 0 ? (wins / roundTrips) * 100 : 0;

    return {
      startV,
      endV,
      totalReturn,
      maxDrawdownPct,
      tradesCount: trades.length,
      roundTrips,
      winRate,
    };
  }, [data]);

  // --- SVG line path for equity ---
  const chart = useMemo(() => {
    const points = data?.equity_curve || [];
    const W = 800, H = 300, PAD = 30;
    if (points.length < 2) return { d: '', W, H, min: 0, max: 0, last: 0 };

    const vals = points.map(p => p.v);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const last = vals[vals.length - 1];
    const range = max - min || 1;
    const stepX = (W - PAD * 2) / (points.length - 1);

    const d = points
      .map((p, i) => {
        const x = PAD + i * stepX;
        const y = PAD + (H - PAD * 2) * (1 - (p.v - min) / range);
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');

    return { d, W, H, min, max, last };
  }, [data]);

  return (
    <div className="p-4 max-w-[1000px] mx-auto">
      <div className="mb-4 text-xl font-semibold">Backtest Demo (SMA crossover)</div>

      {/* Controls */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <label className="flex flex-col text-sm">
          <span>Ticker</span>
          <input className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={ticker} onChange={e=>setTicker(e.target.value.toUpperCase())} />
        </label>
        <label className="flex flex-col text-sm">
          <span>Start (YYYY-MM-DD)</span>
          <input className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 placeholder="optional" value={start} onChange={e=>setStart(e.target.value)} />
        </label>
        <label className="flex flex-col text-sm">
          <span>End (YYYY-MM-DD)</span>
          <input className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 placeholder="optional" value={end} onChange={e=>setEnd(e.target.value)} />
        </label>
        <label className="flex flex-col text-sm">
          <span>Short Window</span>
          <input type="number" className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={shortWin} onChange={e=>setShortWin(parseInt(e.target.value||'0'))} />
        </label>
        <label className="flex flex-col text-sm">
          <span>Long Window</span>
          <input type="number" className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={longWin} onChange={e=>setLongWin(parseInt(e.target.value||'0'))} />
        </label>
        <label className="flex flex-col text-sm">
          <span>Fee (bps)</span>
          <input type="number" className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={feeBps} onChange={e=>setFeeBps(parseFloat(e.target.value||'0'))} />
        </label>
        <label className="flex flex-col text-sm">
          <span>Slippage (bps)</span>
          <input type="number" className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={slipBps} onChange={e=>setSlipBps(parseFloat(e.target.value||'0'))} />
        </label>

        <div className="flex items-end">
          <button
            onClick={run}
            disabled={loading}
            className="w-full px-4 py-2 rounded bg-black text-white border border-white/20 hover:bg-white/10 disabled:opacity-50"
          >
            {loading ? 'Running…' : 'Run Backtest'}
          </button>
        </div>
      </div>

      {error && <div className="text-red-400 mb-3 text-sm">{error}</div>}

      {/* Stats */}
      {data && stats && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-4">
          <Stat label="Start Equity" value={`$${stats.startV.toFixed(2)}`} />
          <Stat label="End Equity" value={`$${stats.endV.toFixed(2)}`} />
          <Stat label="Total Return" value={`${stats.totalReturn.toFixed(2)}%`} />
          <Stat label="Max Drawdown" value={`${stats.maxDrawdownPct.toFixed(2)}%`} />
          <Stat label="# Trades" value={`${stats.tradesCount}`} />
          <Stat label="Win Rate" value={`${stats.winRate.toFixed(1)}% (${stats.roundTrips} rt)`} />
        </div>
      )}

      {/* Chart */}
      {data?.equity_curve?.length ? (
        <div className="rounded border border-white/10 p-3 mb-4 bg-black/30">
          <div className="text-sm opacity-80 mb-2">
            {data.ticker} — last equity: {chart.last.toFixed(2)} (min {chart.min.toFixed(2)} / max {chart.max.toFixed(2)})
          </div>
          <svg width={chart.W} height={chart.H} className="w-full h-auto">
            <rect x="0" y="0" width={chart.W} height={chart.H} fill="transparent" />
            <path d={chart.d} fill="none" stroke="white" strokeWidth="2" />
          </svg>
        </div>
      ) : null}

      {/* Trades */}
      {data?.trades?.length ? (
        <div className="rounded border border-white/10 overflow-x-auto bg-black/30">
          <table className="w-full text-sm">
            <thead className="bg-black/40">
              <tr>
                <th className="text-left p-2">Date</th>
                <th className="text-left p-2">Side</th>
                <th className="text-right p-2">Qty</th>
                <th className="text-right p-2">Price</th>
                <th className="text-right p-2">Fee</th>
              </tr>
            </thead>
            <tbody>
              {data.trades.map((t, i) => (
                <tr key={i} className="odd:bg-white/5">
                  <td className="p-2">{t.date}</td>
                  <td className="p-2">{t.side}</td>
                  <td className="p-2 text-right">{t.qty}</td>
                  <td className="p-2 text-right">{t.price.toFixed(2)}</td>
                  <td className="p-2 text-right">{t.fee.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-white/10 bg-black/30 p-3">
      <div className="text-xs opacity-70">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
