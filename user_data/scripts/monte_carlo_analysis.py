#!/usr/bin/env python3
"""
Monte Carlo + Slippage analysis for RegimeGatedTrendSMA200Strategy.

Reads freqtrade backtest exports, computes corrected (SHA-consistent) metrics,
runs permutation + bootstrap Monte Carlo, applies a slippage tax, and saves
a JSON artifact. Reproducibility artifact for the whitepaper robustness sections.
"""
import zipfile, json, glob, os
from collections import Counter
import numpy as np

BACKTEST_DIR = '/freqtrade/user_data/backtest_results'
STRATEGY = 'RegimeGatedTrendSMA200Strategy'
SLIPPAGE_PER_SIDE = 0.0005  # 0.05% per side => 0.1% round-trip extra
ITERS = 10000
SEED = 42


def load_trades(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        for n in zf.namelist():
            if n.endswith('.json') and 'config' not in n:
                data = json.loads(zf.read(n))
                strat = data.get('strategy', {}).get(STRATEGY)
                if strat:
                    return strat.get('trades', [])
    return None


def discover():
    out = []
    for z in glob.glob(f'{BACKTEST_DIR}/*.zip'):
        trades = load_trades(z)
        if not trades:
            continue
        dates = [t.get('open_date', '') for t in trades]
        out.append({'zip': os.path.basename(z), 'n': len(trades),
                    'min': min(dates), 'max': max(dates)})
    return out


def equity_curve(returns):
    eq = [1.0]
    for r in returns:
        eq.append(eq[-1] * (1.0 + r))
    return np.array(eq)


def max_drawdown(eq):
    peak = np.maximum.accumulate(eq)
    return float(-((eq - peak) / peak).min())


def compute_metrics(returns, profits_abs):
    eq = equity_curve(returns)
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    pos_abs = sum(p for p, r in zip(profits_abs, returns) if r > 0)
    neg_abs = abs(sum(p for p, r in zip(profits_abs, returns) if r < 0))
    return dict(
        total_return=float(eq[-1] - 1.0),
        dd=max_drawdown(eq),
        pf_ratio=float(sum(wins) / abs(sum(losses))) if losses else float('inf'),
        pf_abs=float(pos_abs / neg_abs) if neg_abs else float('inf'),
        win_rate=float(len(wins) / len(returns) * 100),
        n=len(returns),
        best=float(max(returns)),
        worst=float(min(returns)),
    )


def permutation_mc(returns, iters=ITERS, seed=SEED):
    rng = np.random.default_rng(seed)
    dds = np.array([max_drawdown(equity_curve(rng.permutation(returns))) for _ in range(iters)])
    return dds


def bootstrap_mc(returns, iters=ITERS, seed=SEED):
    rng = np.random.default_rng(seed)
    finals, dds = [], []
    for _ in range(iters):
        s = rng.choice(returns, size=len(returns), replace=True)
        eq = equity_curve(s)
        finals.append(eq[-1] - 1.0)
        dds.append(max_drawdown(eq))
    return np.array(finals), np.array(dds)


def main():
    runs = sorted(discover(), key=lambda x: -x['n'])
    print('Discovered RegimeGatedTrendSMA200Strategy runs:')
    for r in runs:
        print(f"  {r['zip']}  n={r['n']}  {r['min'][:10]} -> {r['max'][:10]}")

    twoy = runs[0]
    oney = next((r for r in runs if 28 <= r['n'] <= 34), None)

    results = {}

    for label, run in [('2Y', twoy), ('1Y', oney)]:
        if run is None:
            continue
        trades = load_trades(os.path.join(BACKTEST_DIR, run['zip']))
        returns = [t['profit_ratio'] for t in trades]
        pabs = [t['profit_abs'] for t in trades]
        m = compute_metrics(returns, pabs)
        exits = Counter(t['exit_reason'] for t in trades)
        results[label] = dict(m, exits=dict(exits), zip=run['zip'])
        print(f"\n=== {label} ACTUAL (corrected) ===")
        print(f"  trades={m['n']}  total_return={m['total_return']*100:.2f}%  "
              f"dd={m['dd']*100:.2f}%  pf_ratio={m['pf_ratio']:.2f}  "
              f"pf_abs={m['pf_abs']:.2f}  win%={m['win_rate']:.1f}")
        print(f"  best={m['best']*100:.2f}%  worst={m['worst']*100:.2f}%")
        print(f"  exits={dict(exits)}")

    # ---- Monte Carlo on 2Y ----
    trades = load_trades(os.path.join(BACKTEST_DIR, twoy['zip']))
    returns = np.array([t['profit_ratio'] for t in trades])
    pabs = [t['profit_abs'] for t in trades]
    base = compute_metrics(list(returns), pabs)

    print(f"\n=== MONTE CARLO (2Y, n={len(returns)}, {ITERS:,} iters) ===")

    dds = permutation_mc(returns)
    print("Permutation MC (trade-order shuffle) -> max drawdown:")
    print(f"  actual DD={base['dd']*100:.2f}% | mean={dds.mean()*100:.2f}% "
          f"median={np.median(dds)*100:.2f}% p95={np.percentile(dds,95)*100:.2f}% "
          f"p99={np.percentile(dds,99)*100:.2f}% max={dds.max()*100:.2f}%")
    print(f"  P(DD>20%)={(dds>0.20).mean()*100:.2f}%  P(DD>25%)={(dds>0.25).mean()*100:.2f}%")

    finals, bdds = bootstrap_mc(returns)
    print("Bootstrap MC (resample w/ replacement) -> total return + DD:")
    print(f"  return: mean={finals.mean()*100:.2f}% median={np.median(finals)*100:.2f}% "
          f"p5={np.percentile(finals,5)*100:.2f}% p95={np.percentile(finals,95)*100:.2f}% "
          f"min={finals.min()*100:.2f}%")
    print(f"  P(return<0) [risk of ruin] = {(finals<0).mean()*100:.2f}%")
    print(f"  DD: p95={np.percentile(bdds,95)*100:.2f}% max={bdds.max()*100:.2f}%")

    results['monte_carlo'] = dict(
        permutation_dd=dict(actual=base['dd'], mean=float(dds.mean()),
                            p95=float(np.percentile(dds,95)), p99=float(np.percentile(dds,99)),
                            max=float(dds.max()), p_gt_20=float((dds>0.20).mean()),
                            p_gt_25=float((dds>0.25).mean())),
        bootstrap_return=dict(mean=float(finals.mean()), p5=float(np.percentile(finals,5)),
                              p95=float(np.percentile(finals,95)), min=float(finals.min()),
                              p_negative=float((finals<0).mean())),
    )

    # ---- Slippage ----
    print(f"\n=== SLIPPAGE MODEL ({SLIPPAGE_PER_SIDE*100:.2f}%/side = 0.10% round-trip extra) ===")
    slip = returns - (2 * SLIPPAGE_PER_SIDE)
    ms = compute_metrics(list(slip), pabs)
    print(f"  adjusted: total_return={ms['total_return']*100:.2f}%  dd={ms['dd']*100:.2f}%  "
          f"pf_ratio={ms['pf_ratio']:.2f}  win%={ms['win_rate']:.1f}  "
          f"worst={ms['worst']*100:.2f}%")
    sdds = permutation_mc(slip)
    sfinals, _ = bootstrap_mc(slip)
    print(f"  slippage permutation DD: p95={np.percentile(sdds,95)*100:.2f}% max={sdds.max()*100:.2f}%")
    print(f"  slippage bootstrap return: p5={np.percentile(sfinals,5)*100:.2f}% "
          f"P(<0)={(sfinals<0).mean()*100:.2f}%")

    results['slippage'] = dict(
        per_side=SLIPPAGE_PER_SIDE, metrics=ms,
        perm_dd_p95=float(np.percentile(sdds,95)), perm_dd_max=float(sdds.max()),
        boot_ret_p5=float(np.percentile(sfinals,5)), boot_p_negative=float((sfinals<0).mean()),
    )

    out = '/freqtrade/user_data/backtest_results/monte_carlo_summary.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved artifact: {out}")


if __name__ == '__main__':
    main()
