import os

import init

def prepare_round_zero(num_llms, total_rounds, mode="main"):
    """
    Generates initial market.txt and portfolio.txt for each LLM agent in round 0.
    Uses experiment conditions from experiment_conditions.json.
    Output files are saved in init/r0/
    """

    reflection_input_dir = os.path.join(init.INIT_DIR, "prac")

    config = init.get_experiment_config()
    r0_dir = init.INIT_R0_DIR
    os.makedirs(r0_dir, exist_ok=True)

    # Load experiment parameters
    market_price = config["stock_value"]
    initial_cash = config["initial_cash"]
    initial_stocks = config["initial_stocks"]
    dividend_low = config["dividend_low"]
    dividend_high = config["dividend_high"]
    dividend_prob = config["dividend_prob"]
    interest_rate = config["interest_rate"]
    buyback_price = config["stock_value"]

    # Compute derived metrics
    dividend_earned = initial_stocks * (dividend_low * dividend_prob + dividend_high * (1 - dividend_prob))
    interest_earned = initial_cash * interest_rate
    stock_value = initial_stocks * market_price
    expected_redemption = initial_stocks * buyback_price
    remaining_rounds = total_rounds
    market_volume = 0

    # Loop over each LLM and generate files
    for i in range(1, num_llms + 1):
        llm_id = f"llm_{i:03d}"

        # --- market.txt ---
        market_txt_path = os.path.join(r0_dir, f"{llm_id}_r0_market.txt")
        with open(market_txt_path, "w", encoding="utf-8") as f:
            f.write(f"""Round 0:

- Market + Portfolio Data:

  - Market price: {market_price}
  - Market volume: {market_volume}
  - # of shares owned: {initial_stocks}
  - Current cash: {initial_cash}
  - Stock value: {stock_value}
  - Dividend earned: {dividend_earned}
  - Interest earned: {interest_earned}
  - Submitted orders:
    - No Submitted orders
  - Executed trades:
    - No executed trades """)

        print(f"[prep.py] Created {market_txt_path}")

        # --- portfolio.txt ---
        portfolio_txt_path = os.path.join(r0_dir, f"{llm_id}_r0_portfolio.txt")
        with open(portfolio_txt_path, "w", encoding="utf-8") as f:
            f.write(f"""Your Portfolio (Round 0, {remaining_rounds} rounds remaining):

- Market price (Previous Round): {market_price}
- Buyback price: {buyback_price}
- # of shares owned: {initial_stocks}
- Current cash: {initial_cash}
- Stock value: {stock_value}
- Expected redemption value: {expected_redemption}""")

        print(f"[prep.py] Created {portfolio_txt_path}")

        # === plans.txt ===
        plans_txt_path = os.path.join(r0_dir, f"{llm_id}_r0_plans.txt")
        with open(plans_txt_path, "w", encoding="utf-8") as f:
            f.write("(NONE)\n")
        print(f"[prep.py] Created {plans_txt_path}")

        # === insights.txt ===
        insights_txt_path = os.path.join(r0_dir, f"{llm_id}_r0_insights.txt")
        with open(insights_txt_path, "w", encoding="utf-8") as f:
            f.write("(NONE)\n")
        print(f"[prep.py] Created {insights_txt_path}")

        # === reflection.txt ===
        reflection_src = os.path.join(reflection_input_dir, f"{llm_id}_r0_reflection.txt")
        reflection_dest = os.path.join(r0_dir, f"{llm_id}_r0_reflection.txt")

        if mode == "main":
            if os.path.exists(reflection_src):
                with open(reflection_src, "r", encoding="utf-8") as src_file:
                    content = src_file.read()
            else:
                content = "(NONE)\n"
                print(f"[prep.py] Reflection for {llm_id} not found in prac/. Creating default.")
        else:
            content = "(NONE)\n"
            print(f"[prep.py] [prac mode] Created default reflection for {llm_id}")

        with open(reflection_dest, "w", encoding="utf-8") as dest_file:
            dest_file.write(content)
        print(f"[prep.py] Created {reflection_dest}")