import os
import json
import pandas as pd

def prepare_next_round(base_dir, exp_run_dir, round_num, num_llms):
    """
    Processes LLM trading results, extracts plans, insights, and submitted orders,
    and saves them into the corresponding input directory.

    :param base_dir: Root directory of the project
    :param exp_run_dir: The experiment directory
    :param round_num: The current round number
    :param num_llms: The number of LLM agents
    """
    print(f"\n[proc.py] Processing results for round {round_num}...")

    prev_output_dir = os.path.join(exp_run_dir, "output", f"r{round_num}")
    next_input_dir = os.path.join(exp_run_dir, "input", f"r{round_num}")
    market_dir = os.path.join(exp_run_dir, "market")
    os.makedirs(next_input_dir, exist_ok=True)
    os.makedirs(market_dir, exist_ok=True)

    orders_data = []

    for i in range(1, num_llms + 1):
        llm_id = f"llm_{i:03d}"
        json_file = os.path.join(prev_output_dir, f"{llm_id}_r{round_num}.json")

        print(f"[proc.py] Checking LLM output file: {json_file}")

        if not os.path.exists(json_file):
            print(f"Warning: Missing LLM output for {llm_id} in round {round_num}")
            orders_data.append([llm_id, "NA", 0, 0])  # Fill with NA but keep numeric fields as 0
            continue

        with open(json_file, "r", encoding="utf-8") as file:
            try:
                llm_data = json.load(file)
                
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON format in {json_file}")
                orders_data.append([llm_id, "NA", 0, 0])
                continue

        plans_content = llm_data.get("new_content", {}).get("PLANS.txt", "").strip()
        insights_content = llm_data.get("new_content", {}).get("INSIGHTS.txt", "").strip()

        plans_file = os.path.join(next_input_dir, f"{llm_id}_r{round_num}_plans.txt")
        insights_file = os.path.join(next_input_dir, f"{llm_id}_r{round_num}_insights.txt")

        with open(plans_file, "w", encoding="utf-8") as f:
            f.write(plans_content)
        print(f"Saved {plans_file}")

        with open(insights_file, "w", encoding="utf-8") as f:
            f.write(insights_content)
        print(f"Saved {insights_file}")

        submitted_orders = llm_data.get("submitted_orders", [])
        if not submitted_orders:
            print(f"LLM {llm_id} did not submit any orders, filling with NA")
            orders_data.append([llm_id, "NA", 0, 0])
        else:
            for order in submitted_orders:
                orders_data.append([
                    llm_id,
                    order["order_type"],
                    order["quantity"],
                    order["limit_price"]
                ])

        r0_dir = os.path.join(base_dir, "init", "r0")
        reflection_src = os.path.join(r0_dir, f"{llm_id}_r0_reflection.txt")
        reflection_dest = os.path.join(next_input_dir, f"{llm_id}_r{round_num}_reflection.txt")

        if os.path.exists(reflection_src):
            with open(reflection_src, "r", encoding="utf-8") as src_file:
                content = src_file.read()

            with open(reflection_dest, "w", encoding="utf-8") as dest_file:
                dest_file.write(content)

            print(f"Copied reflection file to {reflection_dest}")
        else:
            print(f"Warning: Reflection file not found for {llm_id} in `r0`")

    market_order_file = os.path.join(market_dir, f"r{round_num}.csv")
    df_orders = pd.DataFrame(orders_data, columns=["llm", "b/s", "num", "prc"])
    df_orders.to_csv(market_order_file, index=False)
    print(f"[proc.py] Saved raw order book to {market_order_file}")