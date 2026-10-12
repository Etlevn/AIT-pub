import os
import init
import prep
import ord
import proc
import mkt
import pfl
import config
import br  # Battle Royale module

# === Experiment Configuration ===
WORK_DIR = config.BASE_DIR  # <-- Use config file

# Get model configuration
NUM_LLMs = config.get_llm_count()  # Auto-calculate from Battle Royale config if enabled

def run_experiment(mode="main", model_name=None, battle_manager=None):
    """
    Unified function to run either prac or main experiment.
    Only difference lies in the prompt generation module (prac vs ord).
    
    Args:
        mode: "main", "prac", or "refl"
        model_name: Model name (used in single model mode, ignored in Battle Royale mode)
        battle_manager: Battle Royale manager instance (optional)
    """
    experiment_config = init.get_experiment_config()
    total_rounds = experiment_config["practice_rounds"] if mode == "prac" else experiment_config["total_rounds"]

    if total_rounds == 0:
        print(f"[main.py] Skipping {mode} experiment: 0 rounds configured.")
        return

    # Step 1: Create experiment directory
    exp_run_dir = init.initialize_experiment(WORK_DIR)
    print(f"[main.py] Initialized {mode} experiment at: {exp_run_dir}")

    # Step 2: Prepare Round 0 files
    print(f"[main.py] Preparing Round 0 market & portfolio files for {mode}...")
    prep.prepare_round_zero(NUM_LLMs,total_rounds, mode=mode)

    # Step 2.5: Initialize configuration based on experiment mode
    if config.EXPERIMENT_MODE == "br":
        print(f"[main.py] Battle Royale mode enabled")
        print(f"[main.py] Assignment strategy: {battle_manager.model_config['assignment_strategy']}")
        if battle_manager.model_config.get('seed'):
            print(f"[main.py] Random seed: {battle_manager.model_config['seed']}")
        
        # Save Battle Royale configuration
        br_config_file = os.path.join(exp_run_dir, "br_config.json")
        battle_manager.save_assignment(br_config_file)
        print(f"[main.py] Battle Royale config saved to: {br_config_file}")
        
        # Print model assignment summary
        print("\n[main.py] Model Assignment Summary:")
        battle_manager.print_assignment_summary()
    elif config.EXPERIMENT_MODE == "sgl":
        # Get model name from config if not provided
        if model_name is None:
            model_name = config.SINGLE_MODEL_CONFIG["model_name"]
        
        print(f"[main.py] Single model mode enabled, using model: {model_name}")
        
        # Save Single model configuration
        sgl_config = {
            "model_name": model_name,
            "num_llms": NUM_LLMs,
            "description": config.SINGLE_MODEL_CONFIG.get("description", ""),
            "service_name": config.SINGLE_MODEL_CONFIG.get("service_name", ""),
            "mode": "single"
        }
        sgl_config_file = os.path.join(exp_run_dir, "sgl_config.json")
        import json
        with open(sgl_config_file, 'w', encoding='utf-8') as f:
            json.dump(sgl_config, f, indent=2, ensure_ascii=False)
        print(f"[main.py] Single model config saved to: {sgl_config_file}")
    else:
        raise ValueError(f"Invalid EXPERIMENT_MODE: {config.EXPERIMENT_MODE}")

    for round_num in range(1, total_rounds + 1):
        print(f"\n=== {mode.upper()} ROUND {round_num} ===")

        # Step 3: Run LLM round using appropriate prompt module
        if battle_manager:
            # Battle Royale mode: pass battle_manager to ord
            ord.run_experiment_round(exp_run_dir, round_num, NUM_LLMs, total_rounds, mode=mode, model_name=model_name, battle_manager=battle_manager)
        else:
            # Single model mode: use default model_name
            ord.run_experiment_round(exp_run_dir, round_num, NUM_LLMs, total_rounds, mode=mode, model_name=model_name)

        # Step 3.5: Post-round JSON check and fix (before processing)
        if config.AUTO_JSON_FIX["enabled"]:
            import json_fix
            fix_results = json_fix.post_round_json_fix(
                exp_run_dir,
                round_num,
                NUM_LLMs,
                create_backup=config.AUTO_JSON_FIX.get("create_backup", True)
            )
            if fix_results.get("fixed_files", 0) > 0:
                print(f"[main.py] Fixed {fix_results['fixed_files']} JSON files in round {round_num}")

        # Step 4: Process output and update order book
        proc.prepare_next_round(WORK_DIR, exp_run_dir, round_num, NUM_LLMs)

        # Step 5: Market price clearing
        mkt.compute_market_price(exp_run_dir, round_num)

        # Step 6: Portfolio + market text file generation
        pfl.compute_market_and_portfolio_all(WORK_DIR, exp_run_dir, round_num, NUM_LLMs, total_rounds)
        
        # Step 6.5: Collect Expected Parrot HTML files
        try:
            import collect_ep_html
            collect_ep_html.collect_ep_html_files(WORK_DIR)
        except Exception as e:
            print(f"[main.py] Warning: Failed to collect HTML files: {e}")

    # Step 7: After all prac rounds, run reflection prompt
    if mode == "prac":
        reflection_round = total_rounds + 1
        print(f"\n[main.py] Running reflection step after practice rounds...")
        if battle_manager:
            ord.run_experiment_round(exp_run_dir, reflection_round, NUM_LLMs, total_rounds, mode="refl", model_name=model_name, battle_manager=battle_manager)
        else:
            ord.run_experiment_round(exp_run_dir, reflection_round, NUM_LLMs, total_rounds, mode="refl", model_name=model_name)

if __name__ == "__main__":
    init.initialize_experiment(WORK_DIR)
    experiment_config = init.get_experiment_config()

    # Print prompt file configuration
    experiment_start_path = config.get_prompt_file_path("experiment_start", init.INIT_PROMPT_DIR)
    order_forecast_end_path = config.get_prompt_file_path("order_forecast_end", init.INIT_PROMPT_DIR)
    mode_str = "BAS" if config.USE_BAS_MODE else "Normal"
    print(f"\n[config.py]Prompt Configuration ({mode_str} mode):")
    print(f"[config.py]experiment_start: {os.path.basename(experiment_start_path)}")
    print(f"[config.py]order_forecast_end: {os.path.basename(order_forecast_end_path)}")

    # Initialize experiment mode based on config
    battle_manager = None
    if config.EXPERIMENT_MODE == "br":
        print(f"\n[config.py] Initializing Battle Royale mode...")
        
        # Check if custom models are configured
        if "custom_models" in config.BATTLE_ROYALE_CONFIG:
            print(f"[config.py] Using custom model configuration")
            # Create Battle Royale configuration with custom models
            br_config = br.create_battle_royale_config(
                total_agents=NUM_LLMs,
                models=config.BATTLE_ROYALE_CONFIG["custom_models"],
                assignment_strategy=config.BATTLE_ROYALE_CONFIG["assignment_strategy"]
            )
        else:
            print(f"[config.py] Using default model configuration")
            # Create Battle Royale configuration with default models
            br_config = br.create_battle_royale_config(
                total_agents=NUM_LLMs,
                assignment_strategy=config.BATTLE_ROYALE_CONFIG["assignment_strategy"]
            )
        
        # Create Battle Royale manager
        battle_manager = br.BattleRoyaleManager(br_config)
        print(f"[config.py] Battle Royale initialized with {NUM_LLMs} agents")
    elif config.EXPERIMENT_MODE == "sgl":
        print(f"\n[config.py] Single model mode enabled, using model: {config.SINGLE_MODEL_CONFIG['model_name']}")
    else:
        raise ValueError(f"Invalid EXPERIMENT_MODE: {config.EXPERIMENT_MODE}. Must be 'br' or 'sgl'")

    # Optional: Run practice rounds
    if experiment_config.get("practice_rounds", 0) > 0:
        if config.EXPERIMENT_MODE == "sgl":
            run_experiment(mode="prac", model_name=config.SINGLE_MODEL_CONFIG["model_name"], battle_manager=battle_manager)
        else:
            run_experiment(mode="prac", battle_manager=battle_manager)

    # Always run main rounds
    if config.EXPERIMENT_MODE == "sgl":
        run_experiment(mode="main", model_name=config.SINGLE_MODEL_CONFIG["model_name"], battle_manager=battle_manager)
    else:
        run_experiment(mode="main", battle_manager=battle_manager)