#!/usr/bin/env python3
"""
NLP Main Module - Behavioral Bias Evaluation System
Analyzes LLM trading agent outputs for behavioral biases using NLP techniques.

Usage:
    python nlp_main.py --input data.xlsx --output results/ --config nlp_config.json
    python nlp_main.py --input data.xlsx --output results/  # Uses default config
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import concurrent.futures
import time

import pandas as pd
from tqdm.auto import tqdm

# Import utility functions
import nlp_utils


def thread_print(thread_id: int, index: int, message: str, total_samples: int = None, max_threads: int = None):
    """Print message with thread and index identification, with alignment"""
    if total_samples:
        # Calculate padding based on total number of samples
        max_digits = len(str(total_samples))
        padded_index = str(index).rjust(max_digits)
    else:
        padded_index = str(index)
    
    if max_threads:
        # Calculate padding for thread_id based on max threads
        thread_digits = len(str(max_threads))
        padded_thread = str(thread_id).rjust(thread_digits)
    else:
        padded_thread = str(thread_id)
    
    tqdm.write(f"[THD {padded_thread}] Idx {padded_index} | {message}")


def process_single_row(
    index: int,
    row_data: Dict[str, Any],
    cfg: Dict[str, Any],
    system_prompt: str,
    output_dir: Path,
    timestamp: str,
    thread_id: int = 1,
    total_samples: int = None,
    max_threads: int = None
) -> Dict[str, Any]:
    """
    Process a single data row (agent's plan and insight).
    
    Returns:
        Dictionary with processing results and statistics
    """
    start_time = time.time()
    
    simulation_index = str(row_data.get('simulation_index', 'Unknown'))
    round_num = str(row_data.get('round', 'Unknown'))
    agent_id = str(row_data.get('llm', 'Unknown'))
    
    thread_print(thread_id, index + 1, f"[INFO] Sim:{simulation_index},Round:{round_num},Agent:{agent_id}", total_samples, max_threads)
    
    results = {
        "index": index,
        "simulation_index": simulation_index,
        "agent_id": agent_id,
        "round": round_num,
        "plan_success": False,
        "insight_success": False,
        "plan_file": None,
        "insight_file": None
    }
    
    api_mode = cfg["api_settings"]["api_mode"]
    model_name = cfg["api_settings"]["model_name"]
    
    # Process Plan if enabled
    if cfg["evaluation_settings"]["evaluate_plan"]:
        thread_print(thread_id, index + 1, "[PROC] Evaluating PLAN...", total_samples, max_threads)
        plan_text = str(row_data.get('plan', 'No plan provided'))
        
        # Build prompt
        plan_prompt = nlp_utils.build_evaluation_prompt(
            system_prompt=system_prompt,
            evaluation_target="plan",
            target_text=plan_text,
            agent_info=row_data,
            config=cfg
        )
        
        # Call LLM
        plan_result = nlp_utils.call_llm_for_evaluation(
            prompt=plan_prompt,
            model_name=model_name,
            api_mode=api_mode
        )
        
        # Validate result
        is_valid, errors = nlp_utils.validate_evaluation_result(
            plan_result,
            cfg["mechanism_order"]
        )
        
        if is_valid:
            thread_print(thread_id, index + 1, "[DONE] Plan evaluation successful", total_samples, max_threads)
            results["plan_success"] = True
            
            # Add metadata
            plan_result["evaluation_target"] = "PLAN"
            plan_result["agent_info"] = {
                "llm_id": agent_id,
                "round": round_num,
                "market_type": row_data.get('market_type', 'N/A')
            }
            
            # Save to file if enabled
            if cfg["output_settings"]["save_individual_json"]:
                plan_filename = nlp_utils.generate_output_filename(
                    simulation_index, round_num, agent_id, "plan"
                )
                plan_path = output_dir / plan_filename
                if nlp_utils.save_json_result(plan_result, plan_path):
                    thread_print(thread_id, index + 1, f"[SAVE] {plan_filename}", total_samples, max_threads)
                    results["plan_file"] = plan_filename
        else:
            thread_print(thread_id, index + 1, "[ERROR] Plan evaluation failed:", total_samples, max_threads)
            for error in errors:
                thread_print(thread_id, index + 1, f"  - {error}", total_samples, max_threads)
    
    # Process Insight if enabled
    if cfg["evaluation_settings"]["evaluate_insight"]:
        thread_print(thread_id, index + 1, "[PROC] Evaluating INSIGHT...", total_samples, max_threads)
        insight_text = str(row_data.get('insight', 'No insight provided'))
        
        # Build prompt
        insight_prompt = nlp_utils.build_evaluation_prompt(
            system_prompt=system_prompt,
            evaluation_target="insight",
            target_text=insight_text,
            agent_info=row_data,
            config=cfg
        )
        
        # Call LLM
        insight_result = nlp_utils.call_llm_for_evaluation(
            prompt=insight_prompt,
            model_name=model_name,
            api_mode=api_mode
        )
        
        # Validate result
        is_valid, errors = nlp_utils.validate_evaluation_result(
            insight_result,
            cfg["mechanism_order"]
        )
        
        if is_valid:
            thread_print(thread_id, index + 1, "[DONE] Insight evaluation successful", total_samples, max_threads)
            results["insight_success"] = True
            
            # Add metadata
            insight_result["evaluation_target"] = "INSIGHT"
            insight_result["agent_info"] = {
                "llm_id": agent_id,
                "round": round_num,
                "market_type": row_data.get('market_type', 'N/A')
            }
            
            # Save to file if enabled
            if cfg["output_settings"]["save_individual_json"]:
                insight_filename = nlp_utils.generate_output_filename(
                    simulation_index, round_num, agent_id, "insight"
                )
                insight_path = output_dir / insight_filename
                if nlp_utils.save_json_result(insight_result, insight_path):
                    thread_print(thread_id, index + 1, f"[SAVE] {insight_filename}", total_samples, max_threads)
                    results["insight_file"] = insight_filename
        else:
            thread_print(thread_id, index + 1, "[ERROR] Insight evaluation failed:", total_samples, max_threads)
            for error in errors:
                thread_print(thread_id, index + 1, f"  - {error}", total_samples, max_threads)
    
    # Calculate and display processing time
    end_time = time.time()
    processing_time = end_time - start_time
    thread_print(thread_id, index + 1, f"[DONE] Completed in {processing_time:.2f} seconds", total_samples, max_threads)
    
    return results


def process_with_thread_id(args):
    """Wrapper function for parallel processing with thread ID"""
    idx, row_data, cfg, system_prompt, output_dir, timestamp, thread_id, total_samples, max_threads = args
    return process_single_row(idx, row_data, cfg, system_prompt, output_dir, timestamp, thread_id, total_samples, max_threads)


def main():
    """Main execution function."""
    start_time = time.time()
    
    # Load configuration first to get default values
    try:
        cfg = nlp_utils.load_config("nlp/nlp_config.json")
    except Exception as e:
        print(f"[ERROR] Failed to load default configuration: {e}")
        return 1
    
    parser = argparse.ArgumentParser(
        description="NLP Module"
    )
    parser.add_argument(
        "--input", "-i",
        default=cfg["file_settings"]["default_input_file"],
        help=f"Input Excel/CSV file path (default: {cfg['file_settings']['default_input_file']})"
    )
    parser.add_argument(
        "--output", "-o",
        default="nlp",
        help="Output directory for results (default: nlp)"
    )
    parser.add_argument(
        "--config", "-c",
        default="nlp/nlp_config.json",
        help="Configuration file path (default: nlp/nlp_config.json)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=None,
        help="Number of parallel workers (overrides config)"
    )
    
    args = parser.parse_args()
    
    # Print header
    tqdm.write("\n"+"="*30+"\n")
    tqdm.write("    NLP MODULE\n")
    tqdm.write("="*30+"\n")
    
    # Load configuration (may be different from default)
    try:
        cfg = nlp_utils.load_config(args.config)
        tqdm.write(f"[CONFIG] Configuration loaded")
    except Exception as e:
        tqdm.write(f"[ERROR] Failed to load configuration: {e}")
        return 1
    
    # Load system prompt
    try:
        system_prompt = nlp_utils.load_prompt_template(cfg)
        tqdm.write(f"[CONFIG] Prompt template loaded: {cfg['file_settings']['prompt_template']}")
    except Exception as e:
        tqdm.write(f"[ERROR] Failed to load prompt template: {e}")
        return 1
    
    # Override workers if specified
    if args.workers:
        cfg["processing_settings"]["max_workers"] = args.workers
    
    # Load input data
    input_path = Path(args.input)
    if not input_path.exists():
        tqdm.write(f"[ERROR] Input file not found: {input_path}")
        return 1
    
    try:
        if input_path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(input_path, engine='openpyxl')
        elif input_path.suffix.lower() == '.csv':
            df = pd.read_csv(input_path)
        else:
            tqdm.write(f"[ERROR] Unsupported file format: {input_path.suffix}")
            return 1
        
        tqdm.write(f"[INFO] Loaded input file: {len(df)} rows")
    except Exception as e:
        tqdm.write(f"[ERROR] Failed to load input file: {e}")
        return 1
    
    # Apply row limit if specified
    max_processing_rows = cfg["processing_settings"]["max_processing_rows"]
    if max_processing_rows is not None and len(df) > max_processing_rows:
        tqdm.write(f"[INFO] Limiting processing to {max_processing_rows} rows")
        df = df.head(max_processing_rows)
    
    # Validate required columns
    missing_cols = [col for col in ["simulation_index", "round", "llm", "plan", "insight"] if col not in df.columns]
    if missing_cols:
        tqdm.write(f"[ERROR] Missing required columns: {', '.join(missing_cols)}")
        return 1
    
    # Sort data by simulation_index, round, llm in ascending order
    tqdm.write(f"[INFO] Sorting data by simulation_index, round, llm...")
    df = df.sort_values(by=["simulation_index", "round", "llm"], ascending=True).reset_index(drop=True)
    
    # Setup output directory - create 'nlp' folder in same directory as input file
    if args.output == "nlp":
        # Use default: create 'nlp' folder in same directory as input file
        output_dir = input_path.parent / "nlp"
    else:
        # Use custom output directory
        output_dir = Path(args.output)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp
    timestamp = nlp_utils.get_timestamp()
    
    # Process data
    max_workers = cfg["processing_settings"]["max_workers"]
    total_samples = len(df)
    tqdm.write(f"\n[INFO] Starting evaluation with {max_workers} threads...")
    tqdm.write(f"{'='*60}\n")
    
    all_results = []
    
    if max_workers > 1:
        # Parallel processing
        with tqdm(total=total_samples, desc="Processing", unit="sample") as pbar:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                thread_counter = 1
                for idx, row in df.iterrows():
                    future = executor.submit(
                        process_with_thread_id,
                        (idx, row.to_dict(), cfg, system_prompt, output_dir, timestamp, thread_counter, total_samples, max_workers)
                    )
                    futures.append(future)
                    thread_counter = (thread_counter % max_workers) + 1
                
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        all_results.append(result)
                        pbar.update(1)
                    except Exception as e:
                        tqdm.write(f"[ERROR] Task failed with exception: {e}")
                        pbar.update(1)
    else:
        # Sequential processing
        with tqdm(total=total_samples, desc="Processing", unit="sample") as pbar:
            for idx, row in df.iterrows():
                try:
                    result = process_single_row(
                        idx, row.to_dict(), cfg, system_prompt, output_dir, timestamp, 1, total_samples, max_workers
                    )
                    all_results.append(result)
                    pbar.update(1)
                except Exception as e:
                    tqdm.write(f"[ERROR] Processing failed for row {idx}: {e}")
                    pbar.update(1)
    
    # Print summary
    tqdm.write("\n"+"="*30+"\n")
    tqdm.write("    SUMMARY\n")
    tqdm.write("="*30+"\n")
    
    total = len(all_results)
    plan_success = sum(1 for r in all_results if r["plan_success"])
    insight_success = sum(1 for r in all_results if r["insight_success"])
    
    tqdm.write(f"[INFO] Total Samples: {total}")
    tqdm.write(f"[INFO] Plan: {plan_success}/{total} ({plan_success/total*100:.2f}%)")
    tqdm.write(f"[INFO] Insight: {insight_success}/{total} ({insight_success/total*100:.2f}%)\n")
    
    tqdm.write(f"\n[DONE] All tasks complete!")
    
    # Calculate and display total processing time
    end_time = time.time()
    total_time = end_time - start_time
    tqdm.write(f"\n[INFO] Total processing time: {total_time:.2f} seconds")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())