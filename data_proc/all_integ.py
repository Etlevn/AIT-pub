#!/usr/bin/env python3
"""
Unified integration runner

Runs three integration pipelines using a single JSON config:
 - market_integ (parse llm_*_rN_market.txt → _mkt.csv)
 - rx_integ (merge r1..rN.csv → _rX.csv)
 - output_integ (parse output JSON → _output.csv)

Config example (all_integ_config.json):
{
  "market_type": "br",
  "root_directory": "/Users/you/Documents/Projects/AIT",
  "experiment_directory": "exp",
  "sgl_llm_type": "claude-3-5-sonnet-20240620",
  "run_market": true,
  "run_rx": true,
  "run_output": true,
  "market_output_filename": "_mkt.csv",
  "rx_output_filename": "_rX.csv",
  "output_output_filename": "_output.csv"
}
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict

# Ensure local imports work when executed from this directory
import sys

THIS_DIR = Path(__file__).parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import market_integ as market_mod
import rx_integ as rx_mod
import output_integ as out_mod


def load_config(config_file: str | None) -> Dict[str, Any]:
    if config_file is None:
        config_file = THIS_DIR / 'all_integ_config.json'
    cfg_path = Path(config_file)
    if not cfg_path.exists():
        raise FileNotFoundError(f'Config not found: {cfg_path}')
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    # Required common fields (experiment_directory optional for auto mode)
    required = ['market_type', 'root_directory']
    missing = [k for k in required if k not in cfg or not cfg.get(k)]
    if missing:
        raise ValueError('Config missing required fields: ' + ', '.join(missing))

    # Default toggles
    cfg.setdefault('run_market', True)
    cfg.setdefault('run_rx', True)
    cfg.setdefault('run_output', True)

    # Default filenames
    cfg.setdefault('market_output_filename', '_mkt.csv')
    cfg.setdefault('rx_output_filename', '_rX.csv')
    cfg.setdefault('output_output_filename', '_output.csv')

    return cfg


def build_sub_config(base: Dict[str, Any], output_filename_key: str) -> Dict[str, Any]:
    sub = {
        'market_type': base.get('market_type'),
        'root_directory': base.get('root_directory'),
        'experiment_directory': base.get('experiment_directory'),
        'output_filename': base.get(output_filename_key),
    }
    # Do not inject sgl_llm_type here; downstream modules read from per-experiment sgl_config.json
    return sub


def run_market(cfg: Dict[str, Any]) -> None:
    sub_cfg = build_sub_config(cfg, 'market_output_filename')
    # Write a lightweight temp config JSON for the module to consume
    tmp_path = THIS_DIR / '.all_integ_tmp_market.json'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(sub_cfg, f, ensure_ascii=False, indent=2)
    try:
        integrator = market_mod.MarketTxtIntegrator(str(tmp_path))
        integrator.run()
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def run_rx(cfg: Dict[str, Any]) -> None:
    sub_cfg = build_sub_config(cfg, 'rx_output_filename')
    tmp_path = THIS_DIR / '.all_integ_tmp_rx.json'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(sub_cfg, f, ensure_ascii=False, indent=2)
    try:
        integrator = rx_mod.DataIntegrator(str(tmp_path))
        sims = integrator.get_available_simulation_indices()
        if not sims:
            print('No formal simulation_index found for RX integration')
            return
        for sim in sims:
            integrator.run_integration(sim)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def run_output(cfg: Dict[str, Any]) -> None:
    sub_cfg = build_sub_config(cfg, 'output_output_filename')
    tmp_path = THIS_DIR / '.all_integ_tmp_output.json'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(sub_cfg, f, ensure_ascii=False, indent=2)
    try:
        integrator = out_mod.OutputIntegrator(str(tmp_path))
        integrator.integrate_all_outputs()
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description='Run all integrations with a unified config')
    parser.add_argument('--config', '-c', type=str, default=None, help='Path to all_integ_config.json')
    args = parser.parse_args()

    cfg = load_config(args.config)

    print('=' * 60)
    print('All Integrations Runner')
    print('=' * 60)
    print(f"Root: {cfg['root_directory']}")
    exp_dir_cfg = cfg.get('experiment_directory', '')
    print(f"Experiment dir: {exp_dir_cfg if exp_dir_cfg else '[AUTO]'}")
    print(f"Market type: {cfg['market_type']}")
    print('-' * 60)

    def should_skip(name: str) -> bool:
        return name.startswith('_') or name.startswith('.')

    # If a single experiment_directory is provided, run once as before
    if cfg.get('experiment_directory'):
        if cfg.get('run_market'):
            print('[1/3] Running market_integ...')
            run_market(cfg)
            print('-' * 60)
        else:
            print('[1/3] market_integ skipped by config')

        if cfg.get('run_rx'):
            print('[2/3] Running rx_integ...')
            run_rx(cfg)
            print('-' * 60)
        else:
            print('[2/3] rx_integ skipped by config')

        if cfg.get('run_output'):
            print('[3/3] Running output_integ...')
            run_output(cfg)
            print('-' * 60)
        else:
            print('[3/3] output_integ skipped by config')
    else:
        # Auto mode: enumerate all experiments under root_directory
        exp_root = Path(cfg['root_directory'])
        if not exp_root.exists():
            print(f"Root directory not found: {exp_root}")
            return 1

        exp_names = [p.name for p in sorted(exp_root.iterdir()) if p.is_dir() and not should_skip(p.name)]

        if not exp_names:
            print('No experiments found for AUTO mode')
            return 0

        print(f"Auto mode: found {len(exp_names)} experiments under {exp_root}")

        for idx, exp_name in enumerate(exp_names, 1):
            print('=' * 60)
            print(f"[{idx}/{len(exp_names)}] Experiment: {exp_name}")
            print('-' * 60)

            # Build per-experiment cfg
            per_cfg = dict(cfg)
            per_cfg['experiment_directory'] = exp_name

            if per_cfg.get('run_market'):
                print('[1/3] Running market_integ...')
                run_market(per_cfg)
                print('-' * 60)
            else:
                print('[1/3] market_integ skipped by config')

            if per_cfg.get('run_rx'):
                print('[2/3] Running rx_integ...')
                run_rx(per_cfg)
                print('-' * 60)
            else:
                print('[2/3] rx_integ skipped by config')

            if per_cfg.get('run_output'):
                print('[3/3] Running output_integ...')
                run_output(per_cfg)
                print('-' * 60)
            else:
                print('[3/3] output_integ skipped by config')

    print('All integrations done.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


