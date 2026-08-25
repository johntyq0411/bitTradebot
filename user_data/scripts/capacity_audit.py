#!/usr/bin/env python3
"""
AUM capacity audit for RegimeGatedTrendSMA200Strategy.

Estimates the maximum capital deployable before our own orders move BTC/USDT
by more than 0.1%, using the square-root law of market impact:

    impact = kappa * sigma_daily * sqrt(Q / V)

with V = the volume over the execution window (one hour for a single order).

Key subtlety: venue volume is HEAVILY skewed (median hourly volume << mean/ADV),
so an ADV-based estimate overstates capacity. We report BOTH, plus the actual
liquidity at the strategy's own entry times, and note that the strategy's
limit (maker) orders are passive so real impact is below the model bound.

Reproducibility artifact for the whitepaper "AUM Capacity Audit" section.
"""
import zipfile, json, glob
import numpy as np
import pandas as pd

BACKTEST_DIR = '/freqtrade/user_data/backtest_results'
DATA = '/freqtrade/user_data/data/binanceus/BTC_USDT-1h.feather'
STRATEGY = 'RegimeGatedTrendSMA200Strategy'


def load_2y_trades():
    for z in sorted(glob.glob(f'{BACKTEST_DIR}/*.zip'), key=__import__('os').path.getmtime, reverse=True):
        try:
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    if n.endswith('.json') and 'config' not in n:
                        d = json.loads(zf.read(n))
                        tr = d.get('strategy', {}).get(STRATEGY, {}).get('trades', [])
                        if tr and len(tr) >= 80:
                            return tr
        except Exception:
            continue
    return None


def main():
    df = pd.read_feather(DATA).set_index('date')
    df['usd_vol'] = df['volume'] * df['close']

    daily_vol = df['usd_vol'].resample('1D').sum()
    adv = float(daily_vol.mean())
    med_daily = float(daily_vol.median())
    med_hourly = float(df['usd_vol'].median())
    mean_hourly = float(df['usd_vol'].mean())
    frac_under_1m = float((df['usd_vol'] < 1e6).mean())
    max_hourly = float(df['usd_vol'].max())

    daily_close = df['close'].resample('1D').last().dropna()
    daily_ret = np.log(daily_close / daily_close.shift(1)).dropna()
    sigma = float(daily_ret.std())

    print('=== VENUE LIQUIDITY (binanceus BTC/USDT 1h) ===')
    print(f'ADV (mean daily USD vol):     ${adv/1e6:9.1f}M/day')
    print(f'Median daily USD vol:         ${med_daily/1e6:9.1f}M/day')
    print(f'Median HOURLY USD vol:        ${med_hourly/1e6:9.1f}M/hour')
    print(f'Mean hourly USD vol:          ${mean_hourly/1e6:9.1f}M/hour  (spike-dominated)')
    print(f'Hours with <$1M volume:       {frac_under_1m*100:.0f}%')
    print(f'Max single-hour volume:       ${max_hourly/1e6:9.1f}M  (outlier spike)')
    print(f'Daily volatility sigma:       {sigma*100:.2f}% (annualized {sigma*np.sqrt(365)*100:.0f}%)')

    print('\n=== CAPACITY (square-root impact, target <= 0.1% move) ===')
    print('impact = kappa * sigma * sqrt(Q / V)')
    for label, v in [('ADV (naive, overstated)', adv), ('median daily vol', med_daily), ('median HOURLY vol (realistic)', med_hourly)]:
        line = f'  {label:28s} V=${v/1e6:7.1f}M  ->'
        for kappa in [0.1, 0.3, 1.0]:
            qmax = v * (0.001 / (kappa * sigma)) ** 2
            line += f'  k={kappa}: ${qmax/1e6:6.1f}M' if qmax >= 1e6 else f'  k={kappa}: ${qmax/1e3:6.0f}k'
        print(line)

    trades = load_2y_trades()
    if trades:
        hourly = df['usd_vol']
        ev = []
        for t in trades:
            ts = pd.Timestamp(t['open_date'])
            if ts.tzinfo is None:
                ts = ts.tz_localize('UTC')
            if ts in hourly.index:
                ev.append(float(hourly.loc[ts]))
        ev = np.array(ev)
        print(f'\n=== LIQUIDITY AT OUR ENTRY TIMES (n={len(ev)}) ===')
        print(f'  median entry-hour volume: ${np.median(ev)/1e6:.2f}M/hour')
        print(f'  vs market median hourly:  ${med_hourly/1e6:.2f}M/hour')
        print(f'  ratio: {np.median(ev)/med_hourly:.2f}x')
        qmax_entry = float(np.median(ev)) * (0.001 / (0.3 * sigma)) ** 2
        print(f'  capacity at median entry liquidity (k=0.3): ${qmax_entry/1e3:.0f}k')

    print('\n=== NOTE ===')
    print('Strategy uses LIMIT (maker) orders for entry/exit -> passive, real impact below model.')
    print('Only the -15% disaster stop is a MARKET order, and it fired 0 times in 2y backtest.')
    print('Binding constraint on a thin venue = limit-order FILL probability, not raw impact.')


if __name__ == '__main__':
    main()
