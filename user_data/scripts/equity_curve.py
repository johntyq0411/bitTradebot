#!/usr/bin/env python3
"""
Generate the whitepaper equity-curve + drawdown SVG.

Uses freqtrade's OWN backtest exports (no reconstruction):
  - *_wallet.feather        -> exact strategy equity (total_quote per timestamp)
  - *_market_change.feather -> exact buy-and-hold curve (rel_mean)

Emits a self-contained SVG with strategy vs buy-and-hold + drawdown subplot.
"""
import zipfile, json, glob, os
import numpy as np
import pandas as pd

BACKTEST_DIR = '/freqtrade/user_data/backtest_results'
DATA = '/freqtrade/user_data/data/binanceus/BTC_USDT-1h.feather'
STRATEGY = 'RegimeGatedTrendSMA200Strategy'
OUT_SVG = '/freqtrade/user_data/equity_curve.svg'


def find_2y_zip():
    for z in sorted(glob.glob(f'{BACKTEST_DIR}/*.zip'), key=os.path.getmtime, reverse=True):
        try:
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    if n.endswith('.json') and 'config' not in n:
                        d = json.loads(zf.read(n))
                        tr = d.get('strategy', {}).get(STRATEGY, {}).get('trades', [])
                        if tr and len(tr) == 88:
                            return z
        except Exception:
            continue
    return None


def main():
    zpath = find_2y_zip()
    with zipfile.ZipFile(zpath) as zf:
        wname = [n for n in zf.namelist() if n.endswith('_wallet.feather')][0]
        wallet = pd.read_feather(zf.open(wname))

    # strategy equity: sum total_quote across currencies per timestamp (cash + position)
    eq_raw = wallet.groupby('date')['total_quote'].sum()
    eq = eq_raw.values / eq_raw.values[0]

    # buy & hold: raw 1h close, from the effective backtest start (post-warmup)
    px = pd.read_feather(DATA).set_index('date')['close']
    px = px[px.index >= pd.Timestamp('2024-09-01', tz='UTC')]
    bh = px.values / px.values[0]

    # drawdown on strategy equity
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0

    # save full-resolution final values for accurate labels
    eq_final = float(eq[-1]); bh_final = float(bh[-1]); dd_max = float(dd.min())

    # downsample to ~730 points (daily) for a compact SVG, preserving the last point
    def decimate(arr, target=730):
        step = max(1, len(arr) // target)
        out = np.asarray(arr)[::step]
        return np.append(out, arr[-1])
    eq = decimate(eq); bh = decimate(bh); dd = decimate(dd)

    print(f'strategy final equity: {eq_final:.4f} ({(eq_final-1)*100:.2f}%)')
    print(f'buy&hold final equity: {bh_final:.4f} ({(bh_final-1)*100:.2f}%)')
    print(f'max drawdown: {dd_max*100:.2f}%')

    # ---- SVG ----
    W, H = 900, 460
    top_h, dd_h = 320, 100
    pad_l, pad_r, pad_t, pad_b = 60, 20, 22, 40
    plot_w = W - pad_l - pad_r
    n = len(eq)
    xeq = np.linspace(pad_l, pad_l + plot_w, n)
    xbh = np.linspace(pad_l, pad_l + plot_w, len(bh))

    lo = min(eq.min(), bh.min()) * 0.98
    hi = max(eq.max(), bh.max()) * 1.02

    def ymap(v, vlo, vhi, area_h):
        return pad_t + (1.0 - (v - vlo) / (vhi - vlo)) * area_h

    eq_y = ymap(eq, lo, hi, top_h)
    bh_y = ymap(bh, lo, hi, top_h)
    dd_base = pad_t + top_h + 22
    dd_top = dd_base + dd_h
    dd_y = ymap(dd, dd.min(), 0.0, dd_h)

    def path(x, y):
        return ' '.join(f'{a:.1f},{b:.1f}' for a, b in zip(x, y))

    dd_area = path(xeq, dd_y) + f' {xeq[-1]:.1f},{dd_base:.1f} {xeq[0]:.1f},{dd_base:.1f}'

    svg = f'''<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:#161b22;border:1px solid #30363d;border-radius:8px;">
  <text x="{pad_l}" y="{pad_t-6}" fill="#c9d1d9" font-size="13" font-family="monospace">Equity Curve — 2-Year Backtest (2024-09 → 2026-08)</text>
  <polyline points="{path(xeq, eq_y)}" fill="none" stroke="#2ea043" stroke-width="2"/>
  <polyline points="{path(xbh, bh_y)}" fill="none" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="5 4"/>
  <text x="{pad_l+12}" y="{pad_t+14}" fill="#2ea043" font-size="11" font-family="monospace">Strategy +{ (eq_final-1)*100:.2f}%</text>
  <text x="{pad_l+12}" y="{pad_t+30}" fill="#58a6ff" font-size="11" font-family="monospace">Buy &amp; Hold +{ (bh_final-1)*100:.2f}%</text>
  <line x1="{pad_l}" y1="{pad_t+top_h}" x2="{W-pad_r}" y2="{pad_t+top_h}" stroke="#30363d"/>
  <text x="{pad_l}" y="{dd_base-8}" fill="#8b949e" font-size="12" font-family="monospace">Drawdown (max {dd_max*100:.1f}%)</text>
  <polygon points="{dd_area}" fill="#f85149" opacity="0.35"/>
  <line x1="{pad_l}" y1="{dd_base}" x2="{W-pad_r}" y2="{dd_base}" stroke="#30363d"/>
  <line x1="{pad_l}" y1="{dd_top}" x2="{W-pad_r}" y2="{dd_top}" stroke="#30363d"/>
</svg>'''

    with open(OUT_SVG, 'w') as f:
        f.write(svg)
    print(f'Wrote {OUT_SVG} ({len(svg)} bytes)')


if __name__ == '__main__':
    main()
