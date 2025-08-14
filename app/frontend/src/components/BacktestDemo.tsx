import { useEffect, useMemo, useRef, useState } from 'react';
import { Chart } from 'chart.js/auto';
import { apiUrl } from '@/lib/api';

type EquityPoint = { t: string; v: number };
type Trade = { date: string; side: 'BUY' | 'SELL'; qty: number; price: number; fee: number };

type BacktestResponse = {
  ticker: string;
  equity_curve: EquityPoint[];
  trades: Trade[];
};

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

      const r = await fetch(apiUrl('/api/backtest'), {
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
    let wins = 0, losses = 0;
    for (let i = 0; i < trades.length; i++) {
      const buy = trades[i];
      if (buy.side !== 'BUY') continue;
      let j = i + 1;
      while (j < trades.length && trades[j].side !== 'SELL') j++;
      if (j < trades.length) {
        const sell = trades[j];
        const qty = Math.min(buy.qty, sell.qty);
        const pnl = (sell.price - buy.price) * qty - (buy.fee + sell.fee);
        if (pnl > 0) wins++; else losses++;
        i = j;
      } else break;
    }
    const roundTrips = wins + losses;
    const winRate = roundTrips > 0 ? (wins / roundTrips) * 100 : 0;

    return { startV, endV, totalReturn, maxDrawdownPct, tradesCount: trades.length, roundTrips, winRate };
  }, [data]);

  return (
    <div className="mx-auto max-w-5xl p-4 space-y-4">
      <div className="text-xl font-semibold">Backtest Demo (SMA crossover)</div>

      {/* Controls */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Field label="Ticker">
          <input className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={ticker} onChange={e=>setTicker(e.target.value.toUpperCase())}/>
        </Field>
        <Field label="Start (YYYY-MM-DD)">
          <input className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 placeholder="optional" value={start} onChange={e=>setStart(e.target.value)}/>
        </Field>
        <Field label="End (YYYY-MM-DD)">
          <input className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 placeholder="optional" value={end} onChange={e=>setEnd(e.target.value)}/>
        </Field>
        <Field label="Short Window">
          <input type="number" className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={shortWin} onChange={e=>setShortWin(parseInt(e.target.value || '0'))}/>
        </Field>
        <Field label="Long Window">
          <input type="number" className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={longWin} onChange={e=>setLongWin(parseInt(e.target.value || '0'))}/>
        </Field>
        <Field label="Fee (bps)">
          <input type="number" className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={feeBps} onChange={e=>setFeeBps(parseFloat(e.target.value || '0'))}/>
        </Field>
        <Field label="Slippage (bps)">
          <input type="number" className="px-3 py-2 rounded bg-black/40 border border-white/10"
                 value={slipBps} onChange={e=>setSlipBps(parseFloat(e.target.value || '0'))}/>
        </Field>
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

      {error && <div className="text-red-400 text-sm">{error}</div>}

      {/* Stats */}
      {data && stats && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <Stat label="Start Equity" value={`$${stats.startV.toFixed(2)}`} />
          <Stat label="End Equity" value={`$${stats.endV.toFixed(2)}`} />
          <Stat label="Total Return" value={`${stats.totalReturn.toFixed(2)}%`} />
          <Stat label="Max Drawdown" value={`${stats.maxDrawdownPct.toFixed(2)}%`} />
          <Stat label="# Trades" value={`${stats.tradesCount}`} />
          <Stat label="Win Rate" value={`${stats.winRate.toFixed(1)}% (${stats.roundTrips} rt)`} />
        </div>
      )}

      {/* Chart.js line chart */}
      {data?.equity_curve?.length ? (
        <div className="rounded border border-white/10 p-3 bg-black/30">
          <EquityChart points={data.equity_curve} label={`${data.ticker} Equity`} />
        </div>
      ) : null}

      {/* Trades table */}
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col text-sm">
      <span>{label}</span>
      {children}
    </label>
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

function EquityChart({ points, label }: { points: EquityPoint[]; label: string }) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!ref.current || points.length < 2) return;
    const ctx = ref.current.getContext('2d');
    if (!ctx) return;

    const chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: points.map(p => p.t),
        datasets: [
          {
            label,
            data: points.map(p => p.v),
            borderWidth: 2,
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        animation: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { display: false },
          y: {
            ticks: {
              callback: (v) => `$${Number(v).toFixed(0)}`
            }
          }
        },
      },
    });

    return () => chart.destroy();
  }, [points, label]);

  return <canvas ref={ref} className="w-full h-56" />;
}
