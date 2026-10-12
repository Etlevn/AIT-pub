def build_prompt_main(file_paths, contents, round_num, total_rounds, limit_price_min, limit_price_max):
    contents["order_forecast_end"] = contents["order_forecast_end"] \
        .replace("<MIN_LIMIT_PRICE>", str(limit_price_min)) \
        .replace("<MAX_LIMIT_PRICE>", str(limit_price_max))
    return f"""
{contents['experiment_start']}

{contents['experiment_conditions']}

{contents['order_forecast_start']}

Filename: {file_paths["plans"]}
++++++++++++++++++++
{contents["plans"]}
++++++++++++++++++++

Filename: {file_paths["insights"]}
++++++++++++++++++++
{contents["insights"]}
++++++++++++++++++++

Here is your practice round reflection:

Filename: {file_paths["reflection"]} (read-only)
++++++++++++++++++++
{contents["reflection"]}
++++++++++++++++++++

Here is the game history that you have access to:

Filename: {file_paths["market"]} (read-only)
++++++++++++++++++++
{contents["market"]}
++++++++++++++++++++

Here is your current portfolio information:

Filename: {file_paths["portfolio"]} (read-only)
++++++++++++++++++++
{contents["portfolio"]}
++++++++++++++++++++

{contents['order_forecast_end']}

[MAIN ROUND: {round_num}, Remaining: {total_rounds - round_num}]

[LIMIT PRICE RANGE: {limit_price_min} to {limit_price_max}]
[ORDER SIZE RANGE: 0 to 5 shares per order]
First, carefully read through the information provided. Now respond ONLY with the final JSON response.

Output your answer as a valid JSON object with this exact format:
{{
  "observations_and_thoughts": "...",
  "new_content": {{
    "PLANS.txt": "...",
    "INSIGHTS.txt": "...",
    "price_forecasts": [...]
  }},
  "submitted_orders": [...]
}}

You MUST respond with a single valid JSON object. Do NOT include any explanations, comments, markdown, triple backticks, escape sequences, or natural language outside the JSON.
{contents['order_forecast_template']}
"""

def build_prompt_prac(file_paths, contents, round_num, total_rounds, limit_price_min, limit_price_max):
    contents["order_forecast_end"] = contents["order_forecast_end"] \
        .replace("<MIN_LIMIT_PRICE>", str(limit_price_min)) \
        .replace("<MAX_LIMIT_PRICE>", str(limit_price_max))
    return f"""
{contents['experiment_start']}

{contents['experiment_conditions']}

{contents['order_forecast_start']}

Filename: {file_paths["plans"]}
++++++++++++++++++++
{contents["plans"]}
++++++++++++++++++++

Filename: {file_paths["insights"]}
++++++++++++++++++++
{contents["insights"]}
++++++++++++++++++++

Here is the game history that you have access to:

Filename: {file_paths["market"]} (read-only)
++++++++++++++++++++
{contents["market"]}
++++++++++++++++++++

Here is your current portfolio information:

Filename: {file_paths["portfolio"]} (read-only)
++++++++++++++++++++
{contents["portfolio"]}
++++++++++++++++++++

{contents['order_forecast_end']}

[PRACTICE ROUND: {round_num}, Remaining: {total_rounds - round_num}]

You are currently in PRACTICE ROUNDS. 
After completing the practice rounds, you will be asked to reflect on your practice experience. This reflection will be accessible to future versions of yourself during the main experiment. This can be helpful in passing along lessons learned to future versions of yourself. 
Practice round history and reflection should only be used to learn the experiment setting, and may not reflect actual market conditions in the main experiment.

[LIMIT PRICE RANGE: {limit_price_min} to {limit_price_max}]
[ORDER SIZE RANGE: 0 to 5 shares per order]
First, carefully read through the information provided. Now respond ONLY with the final JSON response.

Output your answer as a valid JSON object with this exact format:
{{
  "observations_and_thoughts": "...",
  "new_content": {{
    "PLANS.txt": "...",
    "INSIGHTS.txt": "...",
    "price_forecasts": [...]
  }},
  "submitted_orders": [...]
}}

You MUST respond with a single valid JSON object. Do NOT include any explanations, comments, markdown, triple backticks, escape sequences, or natural language outside the JSON.
{contents['order_forecast_template']}
"""

def build_prompt_refl(file_paths, contents):
    return f"""
{contents['experiment_start']}

{contents['experiment_conditions']}

You have now completed all the PRACTICE ROUNDS.
you are asked to reflect on your practice experience. This reflection will be accessible to future versions of yourself during the main experiment. This can be helpful in passing along lessons learned to future versions of yourself. 
Practice round history and reflection should only be used to learn the experiment setting, and may not reflect actual market conditions in the main experiment.

Here is the game history that you have access to:

Filename: {file_paths["market"]} (read-only)
++++++++++++++++++++
{contents["market"]}
++++++++++++++++++++

Here is your current portfolio information:

Filename: {file_paths["portfolio"]} (read-only)
++++++++++++++++++++
{contents["portfolio"]}
++++++++++++++++++++

Please write your reflection below.
"""

def build_json_fix_prompt(broken_text, contents):
    """
    Builds an instruction prompt to fix malformed JSON, optionally enforcing a known JSON structure.
    """
    return f"""
Below is the correct JSON structure you must follow. 
Make sure all required fields exist and follow this structure exactly.
Do not include comments or explanations. Return ONLY valid JSON.

Expected JSON Format:
--------------------
{contents['order_forecast_template']}
--------------------

The following is a malformed or incomplete JSON object, originally generated by an AI model. 
Your task is to fix any syntax or structural errors so that it becomes valid JSON.

Here is the invalid JSON:
--------------------
{broken_text}
--------------------
"""