import os
import datetime
import json
import pandas as pd
import config

# Global directory variables
INIT_DIR = None
INIT_PROMPT_DIR = None
INIT_R0_DIR = None
EXP_INPUT_DIR = None
EXP_OUTPUT_DIR = None
EXP_MARKET_DIR = None

# Cached experiment config dictionary
_experiment_config = None

def get_experiment_config():
    """
    Returns experiment configuration from config.py.
    Uses internal cache to avoid redundant reads.
    """
    global _experiment_config
    if _experiment_config is not None:
        return _experiment_config

    # Use configuration from config.py
    _experiment_config = config.EXPERIMENT_CONFIG
    return _experiment_config

def initialize_experiment(WORK_DIR):
    """
    Initializes the experiment environment by:
    - Changing working directory
    - Creating timestamped exp/ folder with input/output/market subfolders
    - Setting global path variables (INIT_PROMPT_DIR, etc.)
    - Initializing mkt.csv with stock_value from configuration

    Returns:
        exp_run_dir (str): path to the current experiment run folder
    """
    global INIT_DIR, INIT_PROMPT_DIR, INIT_R0_DIR, EXP_INPUT_DIR, EXP_OUTPUT_DIR, EXP_MARKET_DIR

    os.chdir(WORK_DIR)

    # Define init folder structure
    INIT_DIR = os.path.join(WORK_DIR, "init")
    INIT_PROMPT_DIR = os.path.join(INIT_DIR, "prompt")
    INIT_R0_DIR = os.path.join(INIT_DIR, "r0")

    # Create exp/ folder if it doesn't exist
    EXP_DIR = os.path.join(WORK_DIR, "exp")
    os.makedirs(EXP_DIR, exist_ok=True)

    # Create timestamped experiment run folder
    time_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_run_dir = os.path.join(EXP_DIR, time_stamp)

    # Define subfolders
    EXP_INPUT_DIR = os.path.join(exp_run_dir, "input")
    EXP_OUTPUT_DIR = os.path.join(exp_run_dir, "output")
    EXP_MARKET_DIR = os.path.join(exp_run_dir, "market")

    # Create subfolders
    os.makedirs(EXP_INPUT_DIR, exist_ok=True)
    os.makedirs(EXP_OUTPUT_DIR, exist_ok=True)
    os.makedirs(EXP_MARKET_DIR, exist_ok=True)

    # Load stock_value from config
    stock_value = get_experiment_config()["stock_value"]

    # Initialize market price file (mkt.csv)
    mkt_csv_path = os.path.join(EXP_MARKET_DIR, "mkt.csv")
    pd.DataFrame({"round": [0], "mkt": [stock_value], "vol": [0]}).to_csv(mkt_csv_path, index=False)

    print(f"[init.py] Market price initialized at {stock_value} and saved to {mkt_csv_path}")

    return exp_run_dir