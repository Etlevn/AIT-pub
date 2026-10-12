"""
Order validation utilities for LLM Trading Analysis project.
Extracted from ord.py to improve code organization.
"""

def validate_orders(submitted_orders, limit_price_min, limit_price_max, max_quantity):
    """
    Validates submitted orders. Returns True if all orders are valid.
    Valid orders must:
      - Be a list
      - Each order must have quantity > 0 and <= max_quantity
      - Each order's limit_price must lie within [limit_price_min, limit_price_max]
    """
    if not isinstance(submitted_orders, list):
        return False

    for order in submitted_orders:
        quantity = order.get("quantity", 0)
        price = order.get("limit_price", 0)

        if not isinstance(quantity, int) or not isinstance(price, (int, float)):
            return False
        if quantity <= 0 or quantity > max_quantity:
            return False
        if not (limit_price_min <= price <= limit_price_max):
            return False

    return True

def attempt_valid_orders(prompt_text, limit_price_min, limit_price_max, max_quantity=5, max_retries=3, model_name="gpt-4o"):
    """
    Tries up to `max_retries` times to get a valid order JSON using the given prompt.
    Returns response_json (parsed or clipped if necessary), and whether it was clipped.
    """
    # Import here to avoid circular import
    from ord import chat_with_llm
    import json
    import re
    
    response_json = None
    for attempt in range(1, max_retries + 1):
        print(f"[valid.py] Retrying for valid orders (attempt {attempt})...")
        response_text = chat_with_llm(prompt_text, model_name)
        
        if response_text is None:
            print(f"[valid.py] Attempt {attempt} returned None response, skipping...")
            continue
        
        try:
            cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text.strip(), flags=re.IGNORECASE)
            response_json = json.loads(cleaned_text)
            if validate_orders(response_json.get("submitted_orders", []), limit_price_min, limit_price_max, max_quantity):
                print(f"[valid.py] Valid orders received on retry attempt {attempt}.")
                return response_json, False
            else:
                print(f"[valid.py] Retry {attempt} returned invalid orders.")
        except json.JSONDecodeError:
            print(f"[valid.py] Retry {attempt} failed to parse JSON.")
    # After retries, clip
    print(f"[valid.py] Orders remain invalid after retries. Clipping to boundary.")
    if not isinstance(response_json, dict):
        return {"raw_response": response_text if response_text is not None else "Error: All validation attempts failed"}, False

    fixed_orders = []
    for order in response_json.get("submitted_orders", []):
        order_type = order.get("order_type", "")
        quantity = order.get("quantity", 0)
        price = order.get("limit_price", 0)
        valid_quantity = min(max(1, int(quantity)), max_quantity)
        valid_price = min(max(limit_price_min, int(price)), limit_price_max)
        fixed_orders.append({
            "order_type": order_type,
            "quantity": valid_quantity,
            "limit_price": valid_price
        })
    response_json["submitted_orders"] = fixed_orders
    return response_json, True

def ensure_valid_orders(response_json, prompt_text, limit_price_min, limit_price_max, max_quantity=5, model_name="gpt-4o"):
    """
    Ensures that the submitted_orders field contains valid orders.
    If invalid, retry LLM response; if still invalid, clip to boundary.
    Returns a corrected response_json.
    """
    if "raw_response" in response_json:
        return response_json  # Do not process raw_response fallback

    if validate_orders(response_json.get("submitted_orders", []), limit_price_min, limit_price_max, max_quantity):
        return response_json  # Already valid

    print(f"[valid.py] Orders invalid. Retrying to get valid orders...")
    response_json, was_clipped = attempt_valid_orders(prompt_text, limit_price_min, limit_price_max, max_quantity, model_name=model_name)
    return response_json 