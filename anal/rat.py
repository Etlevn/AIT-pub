#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAT analysis script converted from anal/rat.ipynb (D.6.1–D.6.3), reading anal_config.json.

Features:
- Iterate experiments (simulation_index) under base_dir
- Only process formal runs (rounds >= 20)
- Extract price_forecasts from output/r1..rN JSON and compute errors vs market/mkt.csv
- Output per-experiment statistics: MSE, error distribution (mean/std/skew/kurt),
  unbiasedness t-test (t_stat, p_val), autocorrelation (AR(1), DW)
- Save results to base_dir/rat.csv

Config:
- Read anal/anal_config.json by default; can override via --config
- Fields: {"base_dir": "/abs/path", "fundamental_value": 14} (fundamental_value not used here)

Usage:
  python anal/rat.py --config anal/anal_config.json
"""

import os
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp
import statsmodels.api as sm
from statsmodels.stats.stattools import durbin_watson


def load_config(config_path: str | None) -> Dict[str, Any]:
    if config_path is None:
        config_file = Path(__file__).with_name('anal_config.json')
    else:
        config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f'Config file not found: {config_file}')
    with open(config_file, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    if 'base_dir' not in cfg or not cfg['base_dir']:
        raise ValueError('Config missing base_dir')
    return cfg


def read_market_prices(mkt_csv: Path) -> List[float]:
    prices: List[float] = []
    with open(mkt_csv, 'r', encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not s or s.lower().startswith('round'):
                continue
            parts = s.split(',')
            if len(parts) < 2:
                continue
            try:
                prices.append(float(parts[1]))
            except Exception:
                continue
    return prices


def analyze_distribution(df: pd.DataFrame) -> Dict[str, float]:
    return {
        'mean_error': float(df['error'].mean()),
        'std_error': float(df['error'].std()),
        'skewness': float(df['error'].skew()),
        'kurtosis': float(df['error'].kurtosis()),
    }


def analyze_unbiasedness(df: pd.DataFrame) -> Dict[str, float]:
    t_stat, p_val = ttest_1samp(df['error'], popmean=0)
    return {
        't_stat_error': float(t_stat),
        'p_val_error': float(p_val),
    }


def analyze_autocorrelation(df: pd.DataFrame) -> Dict[str, float]:
    df_sorted = df.sort_values(by=['agent', 'predicted_round']).copy()
    df_sorted['error_lag'] = df_sorted.groupby('agent')['error'].shift(1)
    df_lagged = df_sorted.dropna(subset=['error', 'error_lag'])
    if df_lagged.empty:
        return {'AR1_coef': np.nan, 'AR1_pval': np.nan, 'DW_stat': np.nan}
    X = sm.add_constant(df_lagged['error_lag'])
    y = df_lagged['error']
    model = sm.OLS(y, X).fit()
    ar1_coef = float(model.params.get('error_lag', np.nan))
    ar1_pval = float(model.pvalues.get('error_lag', np.nan))
    dw_stat = float(durbin_watson(model.resid))
    return {'AR1_coef': ar1_coef, 'AR1_pval': ar1_pval, 'DW_stat': dw_stat}


def analyze_llm_experiment(exp_path: Path) -> Dict[str, Any] | None:
    mkt_path = exp_path / 'market' / 'mkt.csv'
    prices: List[float] = []
    try:
        prices = read_market_prices(mkt_path)
    except Exception:
        print(f"[warning] Failed to load market prices for {exp_path}")
        return None

    actual_rounds = len(prices) - 1
    if actual_rounds < 20:
        print(f"[SKIPPED] {exp_path.name} rounds={actual_rounds} (<20)")
        return None

    # Collect r1..rN forecasts
    forecast_rows: List[Dict[str, Any]] = []
    output_dir = exp_path / 'output'
    if not output_dir.exists():
        return None

    # Auto iterate r1..rN
    round_dirs: List[int] = []
    for d in output_dir.iterdir():
        if d.is_dir() and d.name.startswith('r'):
            try:
                round_dirs.append(int(d.name[1:]))
            except Exception:
                pass
    for r in sorted(round_dirs):
        round_dir = output_dir / f'r{r}'
        for fname in os.listdir(round_dir):
            if not fname.endswith('.json'):
                continue
            fpath = round_dir / fname
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                forecasts = data.get('new_content', {}).get('price_forecasts', [])
                # Extract agent id
                parts = fname.split('_')
                agent_id = parts[1] if len(parts) > 1 else 'unknown'
                for item in forecasts:
                    try:
                        pred_round = int(item.get('round'))
                        forecast = float(item.get('forecasted_price'))
                    except Exception:
                        continue
                    if 1 <= pred_round <= len(prices):
                        true_price = prices[pred_round - 1]
                        error = forecast - true_price
                        forecast_rows.append({
                            'source_round': r,
                            'agent': agent_id,
                            'predicted_round': pred_round,
                            'forecast': forecast,
                            'true_price': true_price,
                            'error': error,
                        })
            except Exception:
                continue

    if len(forecast_rows) == 0:
        print(f"[warning] No valid forecast data found in {exp_path}")
        return None

    df = pd.DataFrame(forecast_rows)
    result: Dict[str, Any] = {
        'experiment': exp_path.name,
        'MSE': float(np.mean((df['forecast'] - df['true_price']) ** 2)),
    }
    result.update(analyze_distribution(df))
    result.update(analyze_unbiasedness(df))
    result.update(analyze_autocorrelation(df))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='RAT analysis script (from rat.ipynb)')
    parser.add_argument('--config', type=str, default=None, help='Path to config (default: anal/anal_config.json)')
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        base_dir = Path(cfg['base_dir'])
        results: List[Dict[str, Any]] = []

        for folder in sorted(os.listdir(base_dir)):
            exp_path = base_dir / folder
            if not exp_path.is_dir():
                continue
            market_file = exp_path / 'market' / 'mkt.csv'
            if not market_file.exists():
                print(f"[skip] No market file in: {folder}")
                continue
            # Filter non-formal (<20)
            prices = read_market_prices(market_file)
            actual_rounds = len(prices) - 1
            if actual_rounds < 20:
                print(f"[SKIPPED] {folder} rounds={actual_rounds} (<20)")
                continue

            print(f"Analyzing: {folder} ...")
            try:
                res = analyze_llm_experiment(exp_path)
                if res is not None:
                    results.append(res)
            except Exception as e:
                print(f"[error] {folder} failed: {e}")

        df_all = pd.DataFrame(results).round(4)
        out_csv = base_dir / 'rat.csv'
        df_all.to_csv(out_csv, index=False, encoding='utf-8')
        print(f"Saved RAT CSV: {out_csv}")
        print(f" {len(df_all)} experiments analyzed.")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
