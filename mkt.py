import os
import pandas as pd

import init

def compute_market_price(exp_run_dir, round_num):
    """
    Computes the market clearing price based on submitted LLM orders.
    Follows Henning et al. (2025): maximize transaction volume, or use midpoint if no trades.
    """
    print(f"\n[mkt.py] Computing market price and executed orders for round {round_num}...")

    market_dir = init.EXP_MARKET_DIR
    order_book_path = os.path.join(market_dir, f"r{round_num}.csv")
    mkt_csv_path = os.path.join(market_dir, "mkt.csv")

    if not os.path.exists(order_book_path):
        print(f"Error: Order book {order_book_path} not found.")
        return None

    # Load order book
    df_orders = pd.read_csv(order_book_path)
    df_orders = df_orders[df_orders["b/s"] != "NA"].copy()

    # Load previous market price
    df_mkt = pd.read_csv(mkt_csv_path)
    prev_price_row = df_mkt[df_mkt["round"] == round_num - 1]
    prev_price = prev_price_row["mkt"].values[0] if not prev_price_row.empty else df_mkt.iloc[0]["mkt"]

    if df_orders.empty:
        print("[mkt.py] No valid orders submitted. Market price remains unchanged.")
        market_price = prev_price
    else:
        # Extract bid/ask prices
        buy_orders = df_orders[df_orders["b/s"] == "BUY"]
        sell_orders = df_orders[df_orders["b/s"] == "SELL"]

        all_prices = sorted(set(df_orders["prc"]))

        max_volume = 0
        market_price_candidates = []

        # Volume-maximizing price search (collect all prices with max volume)
        for price in all_prices:
            q_bid = buy_orders[buy_orders["prc"] >= price]["num"].sum()
            q_ask = sell_orders[sell_orders["prc"] <= price]["num"].sum()
            volume = min(q_bid, q_ask)
            if volume > max_volume:
                max_volume = volume
                market_price_candidates = [price]
            elif volume == max_volume:
                market_price_candidates.append(price)

        if max_volume > 0:
            # Compute average of candidate prices and round down
            market_price = int(sum(market_price_candidates) / len(market_price_candidates))
            print(f"[mkt.py] Market cleared at price: {market_price} with volume: {max_volume}")
        else:
            if not buy_orders.empty and not sell_orders.empty:
                best_bid = buy_orders["prc"].max()
                best_ask = sell_orders["prc"].min()
                market_price = round((best_bid + best_ask) / 2, 2)
                print(f"[mkt.py] No trades. Market price set to midpoint: {market_price}")
            else:
                market_price = prev_price
                print("[mkt.py] Only one-sided market. Price unchanged.")

    # ==== Trade Execution ====
    df_orders["mkt"] = market_price
    df_orders["ord"] = 0
    df_orders["deal"] = 0

    executed_volume = 0

    buy_queue = []
    sell_queue = []

    for idx, row in df_orders.iterrows():
        if row["b/s"] == "BUY" and row["prc"] >= market_price:
            buy_queue.append((idx, row["num"]))
        elif row["b/s"] == "SELL" and row["prc"] <= market_price:
            sell_queue.append((idx, row["num"]))

    i, j = 0, 0
    while i < len(buy_queue) and j < len(sell_queue):
        buy_idx, buy_qty = buy_queue[i]
        sell_idx, sell_qty = sell_queue[j]
        executed_qty = min(buy_qty, sell_qty)
        executed_volume += executed_qty

        df_orders.at[buy_idx, "ord"] += executed_qty
        df_orders.at[buy_idx, "deal"] = market_price
        df_orders.at[sell_idx, "ord"] += executed_qty
        df_orders.at[sell_idx, "deal"] = market_price

        if buy_qty > executed_qty:
            buy_queue[i] = (buy_idx, buy_qty - executed_qty)
            j += 1
        elif sell_qty > executed_qty:
            sell_queue[j] = (sell_idx, sell_qty - executed_qty)
            i += 1
        else:
            i += 1
            j += 1

    # Save updated order book
    df_orders.to_csv(order_book_path, index=False)
    print(f"[mkt.py] Updated order book with executed trades saved to {order_book_path}")

    # Save new market price with volume
    df_mkt_new = pd.DataFrame({
        "round": [round_num],
        "mkt": [market_price],
        "vol": [executed_volume]
    })
    df_mkt_new.to_csv(mkt_csv_path, mode="a", header=False, index=False)

    print(f"[mkt.py] Market summary saved — Round {round_num}: Price = {market_price}, Volume = {executed_volume}")