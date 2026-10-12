#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROB robustness statistics script converted from robust.ipynb, reading anal_config.json.

Features:
- Read base_dir/anal.csv
- For [MSE, Amplitude, PV_Variance] compute mean, std, CV, 95% CI and relative CI width
- Output to base_dir/rob.csv

Usage:
  python anal/rob.py --config anal/anal_config.json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
from scipy import stats


def load_config(config_path: str | None) -> Dict[str, Any]:
    config_file = Path(config_path) if config_path else Path(__file__).with_name('anal_config.json')
    if not config_file.exists():
        raise FileNotFoundError(f'Config file not found: {config_file}')
    with open(config_file, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    if 'base_dir' not in cfg or not cfg['base_dir']:
        raise ValueError('Config missing base_dir')
    return cfg


def summarize_metrics(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for metric in metrics:
        series = pd.to_numeric(df.get(metric, pd.Series(dtype=float)), errors='coerce').dropna()
        if series.empty:
            rows.append({
                'Metric': metric,
                'Mean': np.nan,
                'StdDev': np.nan,
                'CV': np.nan,
                '95% CI Lower': np.nan,
                '95% CI Upper': np.nan,
                'CI Width / Mean': np.nan,
            })
            continue
        mean = float(series.mean())
        std = float(series.std(ddof=1))
        cv = (std / mean) if mean != 0 else np.nan
        # 95% CI using t distribution
        try:
            ci_low, ci_up = stats.t.interval(confidence=0.95, df=len(series) - 1, loc=mean, scale=stats.sem(series))
            ci_low = float(ci_low)
            ci_up = float(ci_up)
        except Exception:
            ci_low, ci_up = np.nan, np.nan
        ci_width = (ci_up - ci_low) if (np.isfinite(ci_up) and np.isfinite(ci_low)) else np.nan
        ci_width_ratio = (ci_width / mean) if (mean != 0 and np.isfinite(ci_width)) else np.nan
        rows.append({
            'Metric': metric,
            'Mean': round(mean, 2),
            'StdDev': round(std, 2) if np.isfinite(std) else np.nan,
            'CV': round(cv, 3) if np.isfinite(cv) else np.nan,
            '95% CI Lower': round(ci_low, 2) if np.isfinite(ci_low) else np.nan,
            '95% CI Upper': round(ci_up, 2) if np.isfinite(ci_up) else np.nan,
            'CI Width / Mean': round(ci_width_ratio, 3) if np.isfinite(ci_width_ratio) else np.nan,
        })
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description='ROB robustness stats script (from robust.ipynb)')
    parser.add_argument('--config', type=str, default=None, help='Path to config (default: anal/anal_config.json)')
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        base_dir = Path(cfg['base_dir'])
        anal_csv = base_dir / 'anal.csv'
        if not anal_csv.exists():
            raise FileNotFoundError(f'anal.csv not found: {anal_csv}. Please run anal.py first.')
        df = pd.read_csv(anal_csv)

        summary_df = summarize_metrics(df, metrics=['MSE', 'Amplitude', 'PV_Variance'])
        out_csv = base_dir / 'rob.csv'
        summary_df.to_csv(out_csv, index=False, encoding='utf-8')
        print(f'Saved ROB CSV: {out_csv}')
    except Exception as e:
        print(f'Error: {e}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
