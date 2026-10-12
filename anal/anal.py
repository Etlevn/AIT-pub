#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analysis script converted from anal.ipynb with externalized config.

Features:
- Iterate each experiment (simulation_index) under BASE_DIR
- Read market/mkt.csv and compute: Rounds, MSE (vs 14), Amplitude (vs 14)
- Parse *_portfolio.txt under latest input/rN to compute PV_Variance
- Keep only formal runs (rounds >= 20)
- Save results as BASE_DIR/anal.csv
- Generate dual-axis price-volume plots into BASE_DIR/plots/

Config:
- Read anal_config.json in the same folder by default; override via --config
- Fields:
  {
    "base_dir": "/abs/path/to/exp/<group or root>",
    "fundamental_value": 14
  }

Usage:
  python anal.py --config anal_config.json
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def load_config(config_path: str | None) -> Dict[str, Any]:
    if config_path is None:
        config_file = Path(__file__).with_name('anal_config.json')
    else:
        config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f'Config file not found: {config_file}')
    with open(config_file, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    # Validation
    if 'base_dir' not in cfg or not cfg['base_dir']:
        raise ValueError('Config missing base_dir')
    if 'fundamental_value' not in cfg:
        cfg['fundamental_value'] = 14
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


def compute_pv_variance(last_input_dir: Path) -> float | None:
    pv_list: List[float] = []
    for file in last_input_dir.iterdir():
        if not file.name.endswith('_portfolio.txt') or not file.is_file():
            continue
        try:
            cash, redemp = None, None
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    if 'Current cash' in line:
                        cash = float(line.strip().split(':')[1])
                    elif 'Expected redemption value' in line:
                        redemp = float(line.strip().split(':')[1])
            if cash is not None and redemp is not None:
                pv_list.append(cash + redemp)
        except Exception:
            continue
    if len(pv_list) == 0:
        return None
    return float(np.var(pv_list))


def find_last_input_round(input_dir: Path) -> Path | None:
    if not input_dir.exists():
        return None
    round_dirs: List[int] = []
    for d in input_dir.iterdir():
        if d.is_dir() and d.name.startswith('r'):
            try:
                round_dirs.append(int(d.name[1:]))
            except Exception:
                pass
    if not round_dirs:
        return None
    last_round = max(round_dirs)
    return input_dir / f'r{last_round}'


def analyze(base_dir: Path, fundamental_value: float) -> pd.DataFrame:
    results: List[Dict[str, Any]] = []

    for exp_name in sorted(os.listdir(base_dir)):
        exp_path = base_dir / exp_name
        if not exp_path.is_dir():
            continue

        mkt_path = exp_path / 'market' / 'mkt.csv'
        try:
            prices = read_market_prices(mkt_path)
        except Exception as e:
            print(f"[WARNING] Failed to read mkt.csv for {exp_name}: {e}")
            continue

        actual_rounds = len(prices) - 1
        # Keep only formal runs: rounds >= 20
        if actual_rounds < 20:
            print(f"[SKIPPED] {exp_name} rounds={actual_rounds} (<20)")
            continue

        mse = np.mean([(p - fundamental_value) ** 2 for p in prices]) if prices else None
        amplitude = (max(prices) - fundamental_value) if prices else None

        input_dir = exp_path / 'input'
        pv_var: float | None
        try:
            last_input = find_last_input_round(input_dir)
            if last_input is None:
                raise ValueError('No input round folders found.')
            pv_var = compute_pv_variance(last_input)
        except Exception as e:
            print(f"[WARNING] Failed to compute PV variance for {exp_name}: {e}")
            pv_var = None

        results.append({
            'experiment': exp_name,
            'Rounds': actual_rounds,
            'MSE': round(float(mse), 2) if mse is not None else '',
            'Amplitude': round(float(amplitude), 2) if amplitude is not None else '',
            'PV_Variance': round(float(pv_var), 2) if pv_var is not None else ''
        })

    df = pd.DataFrame(results)
    df = df.sort_values('experiment').reset_index(drop=True)
    return df


def plot_all(base_dir: Path, df: pd.DataFrame, fundamental_value: float) -> None:
    plot_dir = base_dir / 'plots'
    plot_dir.mkdir(parents=True, exist_ok=True)

    for _, exp in df.iterrows():
        exp_name = exp['experiment']
        exp_path = base_dir / exp_name
        mkt_path = exp_path / 'market' / 'mkt.csv'

        prices: List[float] = []
        volumes: List[float] = []
        try:
            with open(mkt_path, 'r', encoding='utf-8') as f:
                for line in f:
                    s = line.strip()
                    if not s or s.lower().startswith('round'):
                        continue
                    parts = s.split(',')
                    if len(parts) < 3:
                        continue
                    _, price, volume = parts[:3]
                    prices.append(float(price))
                    volumes.append(float(volume))
        except Exception as e:
            print(f"[ERROR] Failed to read {mkt_path}: {e}")
            continue

        # Only plot for formal runs: rounds >= 20
        actual_rounds = len(prices) - 1
        if actual_rounds < 20:
            print(f"[SKIPPED] {exp_name} rounds={actual_rounds} (<20) – skipping plot")
            continue
        if len(prices) == 0:
            print(f"[SKIPPED] No market data in {exp_name}")
            continue

        rounds = list(range(len(prices)))

        fig, ax1 = plt.subplots(figsize=(6, 4))
        ax1.plot(rounds, prices, color='tab:red', marker='o', label='Market Price')
        ax1.axhline(y=fundamental_value, linestyle='--', color='gray', label='Fundamental Value')
        ax1.set_ylabel('Price', color='tab:red')
        ax1.set_ylim(0, max(30, max(prices) + 2))
        ax1.tick_params(axis='y', labelcolor='tab:red')

        ax2 = ax1.twinx()
        ax2.bar(rounds, volumes, alpha=0.3, color='tab:blue', label='Volume')
        ax2.set_ylabel('Volume', color='tab:blue')
        ax2.tick_params(axis='y', labelcolor='tab:blue')

        title = f"{exp_name} (Rounds={int(exp['Rounds'])})\nMSE={exp['MSE']} | Amp={exp['Amplitude']} | PVVar={exp['PV_Variance']}"
        plt.title(title)
        ax1.set_xlabel('Round')
        ax1.grid(True, linestyle=':')
        fig.tight_layout()

        save_path = plot_dir / f"{exp_name}.png"
        plt.savefig(save_path)
        plt.close()

    print(f"All dual-axis plots saved to: {plot_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description='Analysis script (from anal.ipynb)')
    parser.add_argument('--config', type=str, default=None, help='Path to config (default: anal_config.json)')
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        base_dir = Path(cfg['base_dir'])
        fundamental_value = float(cfg.get('fundamental_value', 14))

        df = analyze(base_dir, fundamental_value)
        out_csv = base_dir / 'anal.csv'
        df.to_csv(out_csv, index=False, encoding='utf-8')
        print(f"Saved summary CSV: {out_csv}")

        plot_all(base_dir, df, fundamental_value)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
