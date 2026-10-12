#!/usr/bin/env python3
"""
Merge all JSON files from nlp/ directory into original CSV
Generates _nlp.csv file
"""

import pandas as pd
from pathlib import Path
import sys
from tqdm.auto import tqdm

# ==================== [CONFIG] ====================

INPUT_FILE = "/Users/you/Documents/Projects/AIT/exp/_sgl/sgl_output.csv"

# ==================================================

def merge_nlp_results():
    """Merge JSON results from nlp/ directory into CSV"""
    
    print("\n" + "="*60)
    print("  Merge NLP Results")
    print("="*60 + "\n")
    
    input_file = Path(INPUT_FILE)
    print(f"[CONFIG] Input file: {input_file}")
    
    if not input_file.exists():
        print(f"[ERROR] Input file not found: {input_file}")
        return
    
    # Load data
    df = pd.read_csv(input_file)
    print(f"[INFO] Total rows: {len(df)}")
    
    # Find nlp directory
    nlp_dir = input_file.parent / "nlp"
    print(f"[INFO] NLP directory: {nlp_dir}")
    
    if not nlp_dir.exists():
        print(f"[ERROR] NLP directory not found: {nlp_dir}")
        return
    
    # Get all JSON files
    json_files = list(nlp_dir.glob("*.json"))
    print(f"[INFO] Found {len(json_files)} JSON files")
    
    # Add NLP result columns
    df['plan_nlp'] = None
    df['insight_nlp'] = None
    
    # Match JSON files to rows with progress bar
    print("\n[INFO] Merging JSON files...")
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Merging", leave=False):
        sim_idx = str(row.get('simulation_index', ''))
        agent_id = str(row.get('llm', ''))
        round_num = str(row.get('round', ''))
        
        plan_name = f"{sim_idx}_{round_num}_{agent_id}_plan.json"
        insight_name = f"{sim_idx}_{round_num}_{agent_id}_insight.json"
        
        for json_file in json_files:
            if json_file.name == plan_name:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        df.at[idx, 'plan_nlp'] = f.read()
                except:
                    pass
            
            elif json_file.name == insight_name:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        df.at[idx, 'insight_nlp'] = f.read()
                except:
                    pass
    
    # Save result
    output_csv = input_file.parent / f"{input_file.stem}_nlp{input_file.suffix}"
    df.to_csv(output_csv, index=False, encoding='utf-8')
    
    # Statistics
    total = len(df)
    plan_filled = df['plan_nlp'].notna().sum()
    insight_filled = df['insight_nlp'].notna().sum()
    both_filled = (df['plan_nlp'].notna() & df['insight_nlp'].notna()).sum()
    
    print("\n[INFO] Results:")
    print("="*60)
    print(f"Total rows: {total}")
    print(f"Plan filled: {plan_filled}/{total} ({plan_filled/total*100:.2f}%)")
    print(f"Insight filled: {insight_filled}/{total} ({insight_filled/total*100:.2f}%)")
    print(f"Both filled: {both_filled}/{total} ({both_filled/total*100:.2f}%)")
    print("="*60)
    print(f"\n[SAVE] Saved to: {output_csv}")
    
    return output_csv

if __name__ == "__main__":
    try:
        merge_nlp_results()
        print("\n[DONE] Complete!")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
