import os
import json
import pandas as pd

import init

def extract_forecasts(output_dir, llm_id, round_num):
    """
    Extracts all price forecasts from the LLM's response JSON file.

    :param output_dir: Directory containing the LLM response files.
    :param llm_id: Identifier for the LLM agent (e.g., "llm_001").
    :param round_num: The current round number.
    :return: A list of tuples (round, forecasted_price).
    """
    output_file = os.path.join(output_dir, f"{llm_id}_r{round_num}.json")
    forecast_data = []

    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                llm_output = json.load(f)

                if "new_content" in llm_output and "price_forecasts" in llm_output["new_content"]:
                    forecasts = llm_output["new_content"]["price_forecasts"]

                    if isinstance(forecasts, list):
                        for forecast in forecasts:
                            round_forecast = int(forecast["round"])
                            forecast_price = forecast["forecasted_price"]
                            forecast_data.append((round_forecast, forecast_price))

        except json.JSONDecodeError:
            print(f"Warning: Could not parse JSON in {output_file}")

    return forecast_data

def load_initial_market_file(base_dir, llm_id):
    """
    Loads the initial market file from `init/r0` for Round 1.

    :param base_dir: Base directory of the project.
    :param llm_id: Identifier for the LLM agent (e.g., "llm_001").
    :return: Content of the `r0` market file as a string.
    """
    init_r0_dir = os.path.join(base_dir, "init", "r0")
    market_file_r0 = os.path.join(init_r0_dir, f"{llm_id}_r0_market.txt")

    if os.path.exists(market_file_r0):
        with open(market_file_r0, "r", encoding="utf-8") as f:
            return f.read()
    else:
        print(f"Warning: {market_file_r0} not found. Creating a new file from scratch.")
        return ""

def compute_market_and_portfolio_all(base_dir, exp_run_dir, round_num, num_llms, total_rounds):
    """
    Computes market and portfolio data for all LLM agents in the specified round.
    """
    print(f"\n[pfl.py] Processing all LLMs for Round {round_num}...")

    config = init.get_experiment_config()

    interest_rate = config["interest_rate"]
    dividend_low = config["dividend_low"]
    dividend_high = config["dividend_high"]
    dividend_prob = config["dividend_prob"]
    dividend_per_share = dividend_low * dividend_prob + dividend_high * (1 - dividend_prob)
    initial_cash = config["initial_cash"]
    initial_shares = config["initial_stocks"]
    buyback_price = config["stock_value"]

    input_dir = os.path.join(exp_run_dir, "input", f"r{round_num}")
    output_dir = os.path.join(exp_run_dir, "output", f"r{round_num}")
    prev_input_dir = os.path.join(base_dir, "init", "r0") if round_num == 1 else os.path.join(exp_run_dir, "input", f"r{round_num - 1}")
    market_dir = os.path.join(exp_run_dir, "market")
    market_file = os.path.join(market_dir, "mkt.csv")
    orders_file = os.path.join(market_dir, f"r{round_num}.csv")

    os.makedirs(input_dir, exist_ok=True)

    df_mkt = pd.read_csv(market_file)
    prev_market_price = df_mkt[df_mkt["round"] == round_num - 1]["mkt"].values[0]
    current_market_price = df_mkt[df_mkt["round"] == round_num]["mkt"].values[0]

    df_orders = pd.read_csv(orders_file) if os.path.exists(orders_file) else pd.DataFrame(
        columns=["llm", "b/s", "num", "prc", "mkt", "ord", "deal"]
    )

    market_volume_row = df_mkt[df_mkt["round"] == round_num]
    market_volume = market_volume_row["vol"].values[0] if "vol" in df_mkt.columns and not market_volume_row.empty else 0

    for i in range(1, num_llms + 1):
        llm_id = f"llm_{i:03d}"

        prev_market_txt = os.path.join(prev_input_dir, f"{llm_id}_r{round_num - 1}_market.txt")
        prev_portfolio_txt = os.path.join(prev_input_dir, f"{llm_id}_r{round_num - 1}_portfolio.txt")

        if round_num == 1:
            initial_market_txt_path = os.path.join(prev_input_dir, f"{llm_id}_r0_market.txt")
            market_content = ""
            if os.path.exists(initial_market_txt_path):
                with open(initial_market_txt_path, "r", encoding="utf-8") as f:
                    market_content = f.read() + "\n"
            shares_owned = initial_shares
            cash_balance = initial_cash
        else:
            market_content = ""
            shares_owned = initial_shares
            cash_balance = initial_cash

            if os.path.exists(prev_market_txt):
                with open(prev_market_txt, "r", encoding="utf-8") as f:
                    market_content = f.read().strip() + "\n"
                    for line in market_content.splitlines():
                        if "Market price" in line:
                            try:
                                prev_market_price = float(line.split(":")[-1].strip())
                            except ValueError:
                                pass

            if os.path.exists(prev_portfolio_txt):
                with open(prev_portfolio_txt, "r", encoding="utf-8") as f:
                    for line in f.readlines():
                        if "# of shares owned" in line:
                            shares_owned = int(line.split(":")[-1].strip())
                        if "Current cash" in line:
                            cash_balance = float(line.split(":")[-1].strip())

        llm_trades = df_orders[df_orders["llm"] == llm_id] if not df_orders.empty else pd.DataFrame(
            columns=["b/s", "num", "ord", "deal"])

        if not llm_trades.empty:
            shares_bought = llm_trades[llm_trades["b/s"] == "BUY"]["ord"].sum()
            shares_sold = llm_trades[llm_trades["b/s"] == "SELL"]["ord"].sum()
            cash_spent = (llm_trades[llm_trades["b/s"] == "BUY"]["ord"] * llm_trades["deal"]).sum()
            cash_received = (llm_trades[llm_trades["b/s"] == "SELL"]["ord"] * llm_trades["deal"]).sum()

            shares_owned += shares_bought - shares_sold
            cash_balance += cash_received - cash_spent

        dividend_earned = shares_owned * dividend_per_share
        interest_earned = cash_balance * interest_rate
        stock_value = shares_owned * current_market_price
        expected_redemption = shares_owned * buyback_price
        cash_balance += interest_earned + dividend_earned
        remaining_rounds = total_rounds - round_num

        forecasts = extract_forecasts(output_dir, llm_id, round_num)

        market_txt_path = os.path.join(input_dir, f"{llm_id}_r{round_num}_market.txt")
        with open(market_txt_path, "w") as f:
            f.write(market_content)
            f.write(f"\nRound {round_num}:\n\n- Market + Portfolio Data:\n\n")
            f.write(f"  - Market price: {current_market_price}\n")
            f.write(f"  - Market volume: {market_volume}\n")
            f.write(f"  - # of shares owned: {shares_owned}\n")
            f.write(f"  - Current cash: {cash_balance:.2f}\n")
            f.write(f"  - Stock value: {stock_value:.2f}\n")
            f.write(f"  - Dividend earned: {dividend_earned:.2f}\n")
            f.write(f"  - Interest earned: {interest_earned:.2f}\n")

            f.write(f"  - Submitted orders:\n")
            submitted_orders = llm_trades[["b/s", "num", "prc"]].dropna()
            if submitted_orders.empty:
                f.write(f"    - No Submitted orders\n")
            else:
                for _, row in submitted_orders.iterrows():
                    f.write(f"    - {row['b/s']} {int(row['num'])} shares at {row['prc']}\n")

            f.write(f"  - Executed trades:\n")
            executed_trades = llm_trades[["b/s", "ord", "deal"]].dropna()
            if executed_trades.empty or executed_trades["ord"].sum() == 0:
                f.write(f"    - No executed trades\n")
            else:
                for _, row in executed_trades.iterrows():
                    f.write(f"    - {row['b/s']} {int(row['ord'])} shares at {row['deal']}\n")

            f.write("\n- Forecasts:\n\n")
            if forecasts:
                for round_val, price_forecast in sorted(forecasts):
                    f.write(f"  - Round {round_val} price forecast: {price_forecast}\n")
            else:
                f.write("  - No forecasts available\n")

        print(f"Saved {market_txt_path}")

        portfolio_txt_path = os.path.join(input_dir, f"{llm_id}_r{round_num}_portfolio.txt")
        with open(portfolio_txt_path, "w") as f:
            f.write(f"Your Portfolio (Round {round_num}, {remaining_rounds} rounds remaining):\n\n")
            f.write(f"- Market price (Previous Round): {current_market_price}\n")
            f.write(f"- Buyback price: {buyback_price}\n")
            f.write(f"- # of shares owned: {shares_owned}\n")
            f.write(f"- Current cash: {cash_balance:.2f}\n")
            f.write(f"- Stock value: {stock_value:.2f}\n")
            f.write(f"- Expected redemption value: {expected_redemption:.2f}\n")

        print(f"Saved {portfolio_txt_path}")