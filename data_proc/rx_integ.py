#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RX integration script (r1..rN → rX.csv)
Read r1..rN.csv under all formal simulation_index in experiment_directory,
append metadata columns, and concatenate vertically into rX.csv.
Configuration is read from a single JSON (containing br and sgl branches).
"""

import os
import re
import pandas as pd
from pathlib import Path
import json
from typing import Dict, List

# Configuration is only read from JSON; no in-script defaults

class DataIntegrator:
    """RX data integrator"""

    def __init__(self, config_file: str = None):
        self.config = self._load_config(config_file)
        self.root_dir = Path(self.config['root_directory'])
        exp_dir_name = self.config.get('experiment_directory')
        self.exp_dir = (self.root_dir / exp_dir_name) if exp_dir_name else None
        
    def _load_config(self, config_file: str) -> Dict:
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

            # experiment_directory is optional (auto mode supported)
            missing = [k for k in ['root_directory', 'output_filename'] if not merged.get(k)]
            if missing:
                raise ValueError("Config missing required fields: " + ", ".join(missing))
            return merged
        else:
            default_cfg = Path(__file__).with_name('rx_integ_config.json')
            if default_cfg.exists():
                return self._load_config(str(default_cfg))
            raise ValueError('No config provided and default rx_integ_config.json not found')
    
    def get_available_simulation_indices(self) -> List[str]:
        """
        Get all available simulation_index
        
        Returns:
            List of simulation_index
        """
        if self.exp_dir is None or not self.exp_dir.exists():
            print(f"Experiment directory does not exist: {self.exp_dir}")
            return []
            
        def is_formal(sim_dir: Path) -> bool:
            market_dir = sim_dir / 'market'
            if not market_dir.exists():
                return False
            rounds = []
            for p in market_dir.glob('r*.csv'):
                m = re.fullmatch(r"r(\d+)\.csv", p.name)
                if m:
                    try:
                        rounds.append(int(m.group(1)))
                    except Exception:
                        pass
            rounds = sorted(set(rounds))
            # Formal: rounds are continuous from 1 and max round >= 20
            return rounds and (rounds == list(range(1, rounds[-1] + 1))) and rounds[-1] >= 20

        indices: List[str] = []
        for item in self.exp_dir.iterdir():
            if not item.is_dir() or not item.name.startswith('20'):
                continue
            if is_formal(item):
                indices.append(item.name)
        return sorted(indices)
    
    def load_round_data(self, simulation_index: str, round_num: int) -> pd.DataFrame:
        """
        Load data for a specified round
        
        Args:
            simulation_index: simulation index
            round_num: round number
            
        Returns:
            DataFrame of this round
        """
        market_dir = self.exp_dir / simulation_index / 'market'
        csv_file = market_dir / f'r{round_num}.csv'
        
        if not csv_file.exists():
            print(f"Warning: file not found {csv_file}")
            return pd.DataFrame()
        
        try:
            df = pd.read_csv(csv_file)
            return df
        except Exception as e:
            print(f"Error: failed to read {csv_file}: {e}")
            return pd.DataFrame()
    
    def get_llm_type_mapping(self, simulation_index: str) -> Dict[str, str]:
        """
        Get llm_type_mapping based on market_type
        
        Args:
            simulation_index: simulation index
            
        Returns:
            llm_type_mapping dict
        """
        market_type = self.config['market_type']
        
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
    
    def add_metadata_columns(self, df: pd.DataFrame, simulation_index: str, round_num: int) -> pd.DataFrame:
        """
        Add metadata columns to DataFrame
        
        Args:
            df: original data DataFrame
            simulation_index: simulation index
            round_num: round number
            
        Returns:
            DataFrame with metadata columns
        """
        if df.empty:
            return df
        
        df_copy = df.copy()
        llm_mapping = self.get_llm_type_mapping(simulation_index)
        
        df_copy['llm_type'] = df_copy['llm'].map(llm_mapping)
        df_copy['market_type'] = self.config['market_type']
        df_copy['round'] = round_num
        df_copy['simulation_index'] = simulation_index
        
        return df_copy
    
    def integrate_simulation_data(self, simulation_index: str) -> pd.DataFrame:
        """
        Integrate all rounds of a specified simulation_index
        
        Args:
            simulation_index: simulation index
            
        Returns:
            Integrated DataFrame
        """
        print(f"Start integrating simulation_index: {simulation_index}")
        
        all_data = []
        
        # Auto-detect total rounds: use the maximum N of market/rN.csv
        market_dir = self.exp_dir / simulation_index / 'market'
        rounds = []
        for p in market_dir.glob('r*.csv'):
            m = re.fullmatch(r"r(\d+)\.csv", p.name)
            if m:
                try:
                    rounds.append(int(m.group(1)))
                except Exception:
                    pass
        rounds = sorted(set(rounds))
        if not rounds:
            print(f"Error: no r*.csv found under {market_dir}")
            return pd.DataFrame()
        total_rounds = rounds[-1]

        for round_num in range(1, total_rounds + 1):
            print(f"  Processing round {round_num}...")
            
            round_df = self.load_round_data(simulation_index, round_num)
            
            if not round_df.empty:
                round_df_with_metadata = self.add_metadata_columns(round_df, simulation_index, round_num)
                all_data.append(round_df_with_metadata)
            else:
                print(f"    Warning: round {round_num} data is empty")
        
        if not all_data:
            print(f"Error: no data found for {simulation_index}")
            return pd.DataFrame()
        
        integrated_df = pd.concat(all_data, ignore_index=True)
        
        print(f"Integrated: {len(integrated_df)} rows")
        return integrated_df
    
    def save_integrated_data(self, df: pd.DataFrame, simulation_index: str) -> str:
        """
        Save the integrated data
        
        Args:
            df: integrated DataFrame
            simulation_index: simulation index
            
        Returns:
            Saved file path
        """
        if df.empty:
            print("Error: no data to save")
            return ""
        
        market_dir = self.exp_dir / simulation_index / 'market'
        market_dir.mkdir(parents=True, exist_ok=True)
        output_file = market_dir / self.config['output_filename']
        
        try:
            df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"Saved to: {output_file}")
            return str(output_file)
        except Exception as e:
            print(f"Error: failed to save {output_file}: {e}")
            return ""
    
    def run_integration(self, simulation_index: str = None) -> bool:
        """
        Run the data integration pipeline
        
        Args:
            simulation_index: specified simulation_index (external scheduler provides it)
            
        Returns:
            success boolean
        """
        # No default target inside; external batch loop calls this per simulation_index
        
        print(f"Start integration...")
        print(f"Target simulation_index: {simulation_index}")
        print(f"Market type: {self.config['market_type']}")
        print("-" * 50)
        
        sim_dir = self.exp_dir / simulation_index
        if not sim_dir.exists():
            print(f"Error: simulation_index directory not found: {sim_dir}")
            return False
        
        integrated_df = self.integrate_simulation_data(simulation_index)
        
        if integrated_df.empty:
            print("Error: failed to integrate any data")
            return False
        
        output_file = self.save_integrated_data(integrated_df, simulation_index)
        if not output_file:
            return False
        
        print("-" * 50)
        print("Integration done!")
        return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='RX integration script (r1..rN → rX.csv)')
    parser.add_argument('--config', '-c', type=str, default=None, help='Path to config JSON (single file containing br and sgl modes)')
    args = parser.parse_args()

    # Default to rx_integ_config.json in the same directory if --config not provided
    if not args.config:
        default_cfg = Path(__file__).with_name('rx_integ_config.json')
        if default_cfg.exists():
            args.config = str(default_cfg)

    integrator = DataIntegrator(
        config_file=args.config,
    )

    # Auto mode: if experiment_directory not provided, iterate subdirectories under root_directory
    def _should_skip(name: str) -> bool:
        return name.startswith('_') or name.startswith('.')

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
            sims = integrator.get_available_simulation_indices()
            if not sims:
                print('No formal simulation_index found')
                continue
            for sim in sims:
                success = integrator.run_integration(sim)
                if success:
                    print(f'Processed: {sim}')
    else:
        sims = integrator.get_available_simulation_indices()
        if not sims:
            print('No formal simulation_index found')
            return
        for sim in sims:
            success = integrator.run_integration(sim)
            if success:
                print(f'Processed: {sim}')


if __name__ == "__main__":
    main()
