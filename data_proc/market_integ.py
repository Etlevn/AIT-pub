#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market text integration script
Reads r20 market text files under all formal simulation_index directories in the
experiment_directory and integrates them into a structured CSV.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd


# Configuration is only read from JSON; no in-script defaults


class MarketTxtIntegrator:
    """Integrator that converts r20 llm_xxx_r20_market.txt into structured CSV."""

    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.root_dir = Path(self.config['root_directory'])
        exp_dir_name = self.config.get('experiment_directory')
        self.exp_dir = (self.root_dir / exp_dir_name) if exp_dir_name else None

    def _load_config(self, config_file: Optional[str]) -> Dict:
        """
        Support a single JSON that contains config for both br and sgl modes:
        {
          "market_type": "br",
          "br": { "root_directory": "...", "experiment_directory": "...", "output_filename": "..." },
          "sgl": { "root_directory": "...", "experiment_directory": "...", "sgl_llm_type": "..." }
        }
        """
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                external = json.load(f)
            market_type = external.get('market_type')
            if market_type not in ('br', 'sgl'):
                raise ValueError('Invalid or missing market_type in config (must be "br" or "sgl")')
            merged = {
                'market_type': market_type,
                'root_directory': external.get('root_directory'),
                'experiment_directory': external.get('experiment_directory'),
                'output_filename': external.get('output_filename'),
            }
            if market_type == 'sgl':
                merged['sgl_llm_type'] = external.get('sgl_llm_type')
            # experiment_directory optional for auto mode
            missing = [k for k in ['root_directory', 'output_filename'] if not merged.get(k)]
            if missing:
                raise ValueError("Config missing required fields: " + ", ".join(missing))
            return merged
        else:
            # If not provided, try default file in the same directory
            default_cfg = Path(__file__).with_name('market_integ_config.json')
            if default_cfg.exists():
                return self._load_config(str(default_cfg))
            raise ValueError('No config provided and default market_integ_config.json not found')

    # ---------------------------------------------------------------------
    # Discover simulation_index (directories starting with '20') and filter
    # formal runs (market contains r1..rN, continuous from 1, max round >= 20)
    # ---------------------------------------------------------------------
    def discover_formal_simulation_indices(self) -> List[str]:
        if self.exp_dir is None or not self.exp_dir.exists():
            return []

        indices: List[str] = []
        for item in self.exp_dir.iterdir():
            if not item.is_dir() or not item.name.startswith('20'):
                continue
            market_dir = item / 'market'
            if not market_dir.exists():
                continue
            # Count strictly matched r{number}.csv files, e.g., r1.csv ... rN.csv
            rounds = []
            for p in market_dir.glob('r*.csv'):
                m = re.fullmatch(r"r(\d+)\.csv", p.name)
                if m:
                    try:
                        rounds.append(int(m.group(1)))
                    except Exception:
                        pass
            rounds = sorted(set(rounds))
            # Formal run: rounds are continuous from 1 and max round >= 20
            if rounds and rounds == list(range(1, rounds[-1] + 1)) and rounds[-1] >= 20:
                indices.append(item.name)

        return sorted(indices)

    # ---------------------------------------------------------------------
    # Load llm->type mapping from battle_royale_config.json (BR mode)
    # or from config (SGL mode)
    # ---------------------------------------------------------------------
    def get_llm_type_mapping(self, simulation_index: str) -> Dict[str, str]:
        market_type = self.config.get('market_type', 'br')
        if market_type == 'sgl':
            return self._load_sgl_mapping(simulation_index)
        elif market_type == 'br':
            return self._load_battle_royale_mapping(simulation_index)
        else:
            return {}

    def _load_sgl_mapping(self, simulation_index: str) -> Dict[str, str]:
        """
        Load LLM model name from sgl_config.json, fallback to config if not found
        
        Args:
            simulation_index: simulation index
            
        Returns:
            llm_type_mapping dict
        """
        config_file = self.exp_dir / simulation_index / 'sgl_config.json'
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    sgl_config = json.load(f)
                
                model_name = sgl_config.get('model_name')
                if model_name:
                    return {f'llm_{i:03d}': model_name for i in range(1, 21)}
                else:
                    print(f"Warning: model_name not found in sgl_config.json: {config_file}")
            except Exception as e:
                print(f"Error: failed to read sgl_config.json {config_file}: {e}")
        
        # No fallback: require per-experiment sgl_config.json
        print(f"Warning: sgl_config.json not found; no fallback used. Please add sgl_config.json under {self.exp_dir / simulation_index}")
        return {}

    def _load_battle_royale_mapping(self, simulation_index: str) -> Dict[str, str]:
        """
        Load LLM assignments from br_config.json
        
        Args:
            simulation_index: simulation index
            
        Returns:
            llm_type_mapping dict
        """
        config_file = self.exp_dir / simulation_index / 'br_config.json'
        
        if not config_file.exists():
            print(f"Warning: br_config.json not found: {config_file}")
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                battle_config = json.load(f)
            
            assignments = battle_config.get('assignments', {})
            return assignments
            
        except Exception as e:
            print(f"Error: failed to read br_config.json {config_file}: {e}")
            return {}

    # ---------------------------------------------------------------------
    # Parse a single market.txt into structured dicts
    # ---------------------------------------------------------------------
    MARKET_BLOCK_HEADER = re.compile(r'^Round\s+(\d+):\s*$')

    def parse_market_txt(self, text: str) -> List[Dict]:
        """
        Parse the entire market.txt file and return structured records per Round.

        Each list element contains:
        - round: int
        - mkt_prc, mkt_vol, stk_num, stk_val, cash, div, int: float
        - forecasts: List[Tuple[int, float]] up to 4 pairs (pad with None if fewer)
        """
        lines = text.splitlines()

        # Group into Round blocks
        blocks: List[Tuple[int, List[str]]] = []
        curr_round: Optional[int] = None
        curr_lines: List[str] = []

        def flush_block():
            nonlocal curr_round, curr_lines
            if curr_round is not None:
                blocks.append((curr_round, curr_lines))
            curr_round = None
            curr_lines = []

        for raw in lines:
            m = self.MARKET_BLOCK_HEADER.match(raw.strip())
            if m:
                flush_block()
                curr_round = int(m.group(1))
                continue
            if curr_round is not None:
                curr_lines.append(raw)
        flush_block()

        records: List[Dict] = []

        def extract_float(pattern: str, block_text: str) -> Optional[float]:
            mm = re.search(pattern, block_text, flags=re.IGNORECASE)
            if not mm:
                return None
            try:
                return float(mm.group(1))
            except Exception:
                return None

        def extract_int(pattern: str, block_text: str) -> Optional[int]:
            mm = re.search(pattern, block_text, flags=re.IGNORECASE)
            if not mm:
                return None
            try:
                return int(float(mm.group(1)))
            except Exception:
                return None

        for rnd, blk_lines in blocks:
            blk = "\n".join(blk_lines)

            mkt_prc = extract_float(r"Market\s+price:\s*([\d\.]+)", blk)
            mkt_vol = extract_int(r"Market\s+volume:\s*([\d\.]+)", blk)
            stk_num = extract_int(r"#\s*of\s*shares\s*owned:\s*([-\d\.]+)", blk)
            cash    = extract_float(r"Current\s+cash:\s*([-\d\.]+)", blk)
            stk_val = extract_float(r"Stock\s+value:\s*([-\d\.]+)", blk)
            div     = extract_float(r"Dividend\s+earned:\s*([-\d\.]+)", blk)
            intr    = extract_float(r"Interest\s+earned:\s*([-\d\.]+)", blk)

            fcst_pairs: List[Tuple[Optional[int], Optional[float]]] = []
            for line in blk.splitlines():
                line_stripped = line.strip()
                m = re.match(r"-\s*Round\s*(\d+)\s*price\s*forecast:\s*([-\d\.]+)", line_stripped, flags=re.IGNORECASE)
                if m:
                    try:
                        r_val = int(m.group(1))
                    except Exception:
                        r_val = None
                    try:
                        p_val = float(m.group(2))
                    except Exception:
                        p_val = None
                    fcst_pairs.append((r_val, p_val))

            fcst_pairs = fcst_pairs[:4]
            while len(fcst_pairs) < 4:
                fcst_pairs.append((None, None))

            records.append({
                'round': rnd,
                'mkt_prc': mkt_prc,
                'mkt_vol': mkt_vol,
                'stk_num': stk_num,
                'stk_val': stk_val,
                'cash': cash,
                'div': div,
                'int': intr,
                'fcst_1_rnd': fcst_pairs[0][0],
                'fcst_1_prc': fcst_pairs[0][1],
                'fcst_2_rnd': fcst_pairs[1][0],
                'fcst_2_prc': fcst_pairs[1][1],
                'fcst_3_rnd': fcst_pairs[2][0],
                'fcst_3_prc': fcst_pairs[2][1],
                'fcst_4_rnd': fcst_pairs[3][0],
                'fcst_4_prc': fcst_pairs[3][1],
            })

        return records

    # ---------------------------------------------------------------------
    # Process a single simulation_index: read all llm_*_r{target}__market.txt under r{target}
    # and integrate
    # ---------------------------------------------------------------------
    def integrate_single_simulation(self, simulation_index: str) -> pd.DataFrame:
        # Auto-detect max round by scanning input/r{N} directories and taking max N
        input_root = self.exp_dir / simulation_index / 'input'
        max_round = 0
        if input_root.exists():
            for d in input_root.iterdir():
                if d.is_dir():
                    m = re.fullmatch(r"r(\d+)", d.name)
                    if m:
                        try:
                            max_round = max(max_round, int(m.group(1)))
                        except Exception:
                            pass
        if max_round <= 0:
            return pd.DataFrame()
        target_round = max_round
        input_dir = input_root / f'r{target_round}'
        if not input_dir.exists():
            return pd.DataFrame()

        # Read LLM type mapping
        llm_type_map = self.get_llm_type_mapping(simulation_index)
        market_type = self.config.get('market_type', 'br')

        records: List[Dict] = []

        for txt_path in sorted(input_dir.glob(f'llm_*_r{target_round}_market.txt')):
            llm_name = txt_path.name.split('_r')[0]

            try:
                text = txt_path.read_text(encoding='utf-8')
            except Exception:
                continue

            per_round = self.parse_market_txt(text)

            for rr in per_round:
                rnum = rr.get('round')
                if not isinstance(rnum, int):
                    continue
                if rnum < 1 or rnum > target_round:
                    continue

                row = {
                    'llm': llm_name,
                    'mkt_prc': rr.get('mkt_prc'),
                    'mkt_vol': rr.get('mkt_vol'),
                    'stk_num': rr.get('stk_num'),
                    'stk_val': rr.get('stk_val'),
                    'cash': rr.get('cash'),
                    'div': rr.get('div'),
                    'int': rr.get('int'),
                    'fcst_1_rnd': rr.get('fcst_1_rnd'),
                    'fcst_1_prc': rr.get('fcst_1_prc'),
                    'fcst_2_rnd': rr.get('fcst_2_rnd'),
                    'fcst_2_prc': rr.get('fcst_2_prc'),
                    'fcst_3_rnd': rr.get('fcst_3_rnd'),
                    'fcst_3_prc': rr.get('fcst_3_prc'),
                    'fcst_4_rnd': rr.get('fcst_4_rnd'),
                    'fcst_4_prc': rr.get('fcst_4_prc'),
                    'llm_type': llm_type_map.get(llm_name),
                    'market_type': market_type,
                    'round': rnum,
                    'simulation_index': simulation_index,
                }

                records.append(row)

        if not records:
            return pd.DataFrame()

        columns = [
            'llm',
            'mkt_prc', 'mkt_vol', 'stk_num', 'stk_val', 'cash', 'div', 'int',
            'fcst_1_rnd', 'fcst_1_prc', 'fcst_2_rnd', 'fcst_2_prc',
            'fcst_3_rnd', 'fcst_3_prc', 'fcst_4_rnd', 'fcst_4_prc',
            'llm_type', 'market_type', 'round', 'simulation_index'
        ]

        df = pd.DataFrame.from_records(records, columns=columns)
        return df

    # ---------------------------------------------------------------------
    # Scan all formal simulation_index and write CSV
    # ---------------------------------------------------------------------
    def run(self) -> None:
        sims = self.discover_formal_simulation_indices()
        if not sims:
            print('No formal simulation_index found')
            return

        for sim in sims:
            df = self.integrate_single_simulation(sim)
            if df.empty:
                print(f'Skip {sim}: failed to integrate r20 market texts')
                continue

            out_file = self.exp_dir / sim / 'market' / self.config['output_filename']
            out_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out_file, index=False, encoding='utf-8')
            print(f'Saved: {out_file}')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Integrate r20 market texts into CSV')
    parser.add_argument('--config', '-c', type=str, default=None, help='Path to config JSON (single file containing br and sgl modes)')
    # All configuration is sourced from JSON; no CLI overrides
    args = parser.parse_args()

    # If --config not provided, default to market_integ_config.json in the same directory
    # to support direct run: python market_integ.py
    if not args.config:
        from pathlib import Path as _P
        default_cfg = _P(__file__).with_name('market_integ_config.json')
        if default_cfg.exists():
            args.config = str(default_cfg)

    integrator = MarketTxtIntegrator(config_file=args.config)

    def _should_skip(name: str) -> bool:
        return name.startswith('_') or name.startswith('.')

    # Auto mode: if experiment_directory not provided, iterate root_directory subfolders
    if integrator.exp_dir is None:
        exp_root = integrator.root_dir
        if not exp_root.exists():
            print(f"Root directory not found: {exp_root}")
            return
        exp_names = [p.name for p in sorted(exp_root.iterdir()) if p.is_dir() and not _should_skip(p.name)]
        if not exp_names:
            print('No experiments found for AUTO mode')
            return
        print(f"Auto mode: found {len(exp_names)} experiments under {exp_root}")
        for idx, exp_name in enumerate(exp_names, 1):
            print('=' * 60)
            print(f"[{idx}/{len(exp_names)}] Experiment: {exp_name}")
            print('-' * 60)
            integrator.exp_dir = integrator.root_dir / exp_name
            integrator.run()
    else:
        integrator.run()


if __name__ == '__main__':
    main()


