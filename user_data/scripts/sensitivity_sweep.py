#!/usr/bin/env python3
"""
Parameter sensitivity sweep for RegimeGatedTrendSweepStrategy.

Sweeps the regime/exit SMA, the pullback-entry SMA, and the ADX threshold over
a grid of backtests, records net profit / PF / trades per point, and saves the
full matrix incrementally (so a mid-run failure loses nothing).

Reproducibility artifact for the whitepaper "Parameter Sensitivity" section.
"""
import json, subprocess, re, itertools, time, os

CONFIG = '/freqtrade/user_data/config_baseline.json'
STRATEGY = 'RegimeGatedTrendSweepStrategy'
TIMERANGE = '20240801-20260825'
OVERRIDE_PATH = '/freqtrade/user_data/sweep_override.json'
OUT = '/freqtrade/user_data/backtest_results/sensitivity_sweep.json'

TREND = [150, 175, 200, 225, 250]          # regime/exit SMA
PULLBACK = [10, 15, 20, 25, 30, 35, 40]   # pullback-entry SMA
ADX_EXTRA = [15, 25]                       # ADX 1D sweep (default 20)


def run_backtest(params):
    with open(OVERRIDE_PATH, 'w') as f:
        json.dump(params, f)
    cmd = ['freqtrade', 'backtesting', '--config', CONFIG,
           '--config', OVERRIDE_PATH, '--strategy', STRATEGY,
           '--timerange', TIMERANGE, '--cache', 'none', '--notes', 'SWEEP']
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    out = r.stdout + '\n' + r.stderr

    def grab(pattern):
        m = re.search(pattern, out)
        return m.group(1) if m else None

    profit = grab(r'Total profit %[^\d-]*([-\d.]+)')
    pf = grab(r'Profit factor[^\d-]*([-\d.]+)')
    trades = grab(r'Total/Daily Avg Trades[^\d]*(\d+)')
    return dict(params=params,
                profit_pct=float(profit) if profit else None,
                pf=float(pf) if pf else None,
                trades=int(trades) if trades else None,
                elapsed=round(time.time() - t0, 1))


def main():
    combos = []
    for t, p in itertools.product(TREND, PULLBACK):
        combos.append({'sweep_trend_sma': t, 'sweep_pullback_sma': p, 'sweep_adx': 20})
    for a in ADX_EXTRA:
        combos.append({'sweep_trend_sma': 200, 'sweep_pullback_sma': 20, 'sweep_adx': a})

    results = []
    total = len(combos)
    t_start = time.time()
    for i, params in enumerate(combos, 1):
        res = run_backtest(params)
        results.append(res)
        # incremental save
        with open(OUT, 'w') as f:
            json.dump(results, f, indent=2)
        label = f"trend={params['sweep_trend_sma']} pullback={params['sweep_pullback_sma']} adx={params['sweep_adx']}"
        print(f"[{i}/{total}] {label} -> {res['profit_pct']}% "
              f"(PF {res['pf']}, {res['trades']} trades, {res['elapsed']}s)", flush=True)

    # summary
    profitable = [r for r in results if r['profit_pct'] is not None and r['profit_pct'] > 0]
    print(f"\nDONE in {round((time.time()-t_start)/60, 1)} min. "
          f"{len(profitable)}/{total} points profitable "
          f"({len(profitable)/total*100:.1f}%).")
    print(f"Saved {len(results)} results to {OUT}")


if __name__ == '__main__':
    main()
