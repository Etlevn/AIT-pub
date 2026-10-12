import json
import os
import re
import ast

import init
import prompt
import utils
import valid
import config

from dotenv import load_dotenv
load_dotenv()
from edsl import Model, QuestionFreeText, Survey

def chat_with_llm(prompt, model_name="gpt-4o"):
    """
    Unified function to call LLM API based on configuration.
    Supports Expected Parrot, OpenAI, and DeepSeek APIs.
    """
    api_mode = config.API_CONFIG["api_mode"]
    
    if api_mode == "expected_parrot":
        return chat_with_parrot(prompt, model_name)
    elif api_mode == "openai":
        return chat_with_openai(prompt, model_name)
    elif api_mode == "deepseek":
        return chat_with_deepseek(prompt, model_name)
    else:
        raise ValueError(f"Unknown API mode: {api_mode}")

def get_service_name_for_model(model_name):
    """
    Get service name for a model from configuration.
    Uses different logic for Battle Royale mode vs single model mode.
    """
    if config.EXPERIMENT_MODE == "br" and "custom_models" in config.BATTLE_ROYALE_CONFIG:
        for model_config in config.BATTLE_ROYALE_CONFIG["custom_models"]:
            if model_config["name"] == model_name:
                return model_config.get("service_name")
        return None
    else:
        return config.SINGLE_MODEL_CONFIG.get("service_name")

def chat_with_parrot(prompt, model_name="gpt-4o"):
    """
    Sends a prompt to Expected Parrot via EDSL Model interface.
    """
    try:
        import os
        ep_api_key = config.API_CONFIG["expected_parrot_api_key"]
        if ep_api_key:
            os.environ["EXPECTED_PARROT_API_KEY"] = ep_api_key
        
        service_name = get_service_name_for_model(model_name)
        
        if service_name and service_name.strip():
            print(f"[ord.py] Using service '{service_name}' for model '{model_name}'")
            model = Model(model_name, service_name=service_name)
        else:
            print(f"[ord.py] No service specified for model '{model_name}', using default")
            model = Model(model_name)
            
        question = QuestionFreeText(
            question_name="llm_response",
            question_text=prompt
        )
        survey = Survey(questions=[question])
        results = survey.by(model).run()
        
        answer = results[0].answer
        if isinstance(answer, dict) and "llm_response" in answer:
            return answer["llm_response"]
        elif answer is None:
            return "Error: Received None response from model"
        else:
            return str(answer)
    except Exception as e:
        return f"Error: {e}"

def chat_with_deepseek(prompt, model_name="deepseek-chat"):
    """
    Sends a request to DeepSeek's model and returns the response.
    """
    try:
        from openai import OpenAI
        api_key = config.API_CONFIG["deepseek_api_key"]
        if not api_key:
            return "Error: DeepSeek API key not configured"
        
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

def chat_with_openai(prompt, model_name="gpt-4o"):
    """
    Sends a request to OpenAI's model and returns the response.
    """
    try:
        import openai
        api_key = config.API_CONFIG["openai_api_key"]
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

def run_experiment_round(exp_run_dir, round_num, num_llms, total_rounds, mode, model_name="gpt-4o", battle_manager=None):
    """
    Runs a single round of the experiment:
    - Reads input files from `exp/[timestamp]/input/rX/` (or `init/r0/` for round 1)
    - Loads experiment prompt and conditions from `init/prompt/`
    - Calls the LLM API to simulate agent trading
    - Saves results to `exp/[timestamp]/output/rX/`
    
    Args:
        exp_run_dir: Experiment directory
        round_num: Current round number
        num_llms: Number of LLM agents
        total_rounds: Total number of rounds
        mode: Experiment mode ("main", "prac", "refl")
        model_name: Default model name (used when battle_manager is None)
        battle_manager: Battle Royale manager instance (optional)
    """

    experiment_start_content = read_file(config.get_prompt_file_path("experiment_start", init.INIT_PROMPT_DIR))
    experiment_conditions_content = read_file(config.get_prompt_file_path("experiment_conditions", init.INIT_PROMPT_DIR))
    order_forecast_start_content = read_file(config.get_prompt_file_path("order_forecast_start", init.INIT_PROMPT_DIR))
    order_forecast_end_content = read_file(config.get_prompt_file_path("order_forecast_end", init.INIT_PROMPT_DIR))
    order_forecast_template_content = read_file(config.get_prompt_file_path("order_forecast_template", init.INIT_PROMPT_DIR))

    for i in range(1, num_llms + 1):
        llm_id = f"llm_{i:03d}"
        file_paths = generate_filenames(exp_run_dir, llm_id, round_num)

        if battle_manager:
            agent_model = battle_manager.get_model_for_agent(llm_id)
        else:
            agent_model = model_name
        
        print(f"[{mode}] Processing {llm_id} using model: {agent_model}")

        plans_content = read_file(file_paths["plans"])
        insights_content = read_file(file_paths["insights"])
        reflection_content = read_file(file_paths["reflection"])
        market_content = read_file(file_paths["market"])
        portfolio_content = read_file(file_paths["portfolio"])

        try:
            mkt_path = os.path.join(exp_run_dir, "output", f"r{round_num - 1}", "mkt.csv")
            with open(mkt_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                last_price_line = lines[-1]
                last_price = float(last_price_line.strip().split(",")[1])
        except Exception:
            last_price = 14.0

        limit_price_min = max(1, int(last_price * 0.5))
        limit_price_max = int(last_price * 2.0)

        contents = {
            "experiment_start": experiment_start_content,
            "experiment_conditions": experiment_conditions_content,
            "order_forecast_start": order_forecast_start_content,
            "order_forecast_end": order_forecast_end_content,
            "order_forecast_template": order_forecast_template_content,
            "plans": plans_content,
            "insights": insights_content,
            "reflection": reflection_content,
            "market": market_content,
            "portfolio": portfolio_content
        }

        if mode == "main":
            prompt_text = prompt.build_prompt_main(file_paths, contents, round_num, total_rounds, limit_price_min, limit_price_max)
        elif mode == "prac":
            prompt_text = prompt.build_prompt_prac(file_paths, contents, round_num, total_rounds, limit_price_min, limit_price_max)
        elif mode == "refl":
            prompt_text = prompt.build_prompt_refl(file_paths, contents)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        if mode == "refl":
            response = chat_with_llm(prompt_text, agent_model)
            response_text = response.strip() if isinstance(response, str) else str(response).strip()
            
            reflection_dir = os.path.join(init.INIT_DIR, "prac")
            os.makedirs(reflection_dir, exist_ok=True)
            reflection_filename = os.path.join(reflection_dir, f"{llm_id}_r0_reflection.txt")
            with open(reflection_filename, "w", encoding="utf-8") as f:
                f.write(response_text)
            print(f"[refl] Saved {llm_id}'s reflection to {reflection_filename}")
            continue

        max_attempts = 3
        attempt = 1
        while attempt <= max_attempts:
            response_json = utils.try_get_valid_json(prompt_text, contents, model_name=agent_model, exp_run_dir=exp_run_dir, llm_id=llm_id, round_num=round_num)
            
            while pause_on_server_error(llm_id, round_num, response_json):
                print(f"[ord.py] Retrying {llm_id} in round {round_num} after server/network error...")
                response_json = utils.try_get_valid_json(prompt_text, contents, model_name=agent_model, exp_run_dir=exp_run_dir, llm_id=llm_id, round_num=round_num)
            
            try:
                if isinstance(response_json, dict) and "llm_response" in response_json:
                    raw_response = response_json["llm_response"]
                    if isinstance(raw_response, str):
                        try:
                            inner = json.loads(raw_response)
                            if isinstance(inner, dict):
                                response_json = inner
                            else:
                                raise ValueError("llm_response is not a JSON object")
                        except Exception:
                            raise ValueError("Invalid JSON string in llm_response")
                    elif isinstance(raw_response, dict):
                        response_json = raw_response
                    else:
                        raise ValueError("llm_response is neither string nor dict")
                break
            except ValueError as ve:
                print(f"\n[RETRY] Attempt {attempt}/3: Detected invalid JSON in 'llm_response' for {llm_id} in round {round_num}")
                if attempt < max_attempts:
                    print(f"[ord.py] Retrying {llm_id} (attempt {attempt + 1}/3) in round {round_num} after invalid response...")
                    attempt += 1
                    continue
                else:
                    response_json = {"raw_response": str(response_json)}
                    break
        max_quantity = 5
        response_json = valid.ensure_valid_orders(response_json, prompt_text, limit_price_min, limit_price_max, max_quantity, model_name=agent_model)

        exp_output_dir = os.path.join(exp_run_dir, "output", f"r{round_num}")
        os.makedirs(exp_output_dir, exist_ok=True)
        output_filename = os.path.join(exp_output_dir, f"{llm_id}_r{round_num}.json")

        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(response_json, f, indent=4)

        print(f"[{mode}] Response for {llm_id} in round {round_num} saved to {output_filename}")
        print()

def pause_on_server_error(llm_id, round_num, response_data):
    """
    Unified function to detect network/server errors and pause for manual retry.
    Handles Expected Parrot job failures, connection errors, timeouts, and API errors.
    """
    error_detected = False
    error_type = ""
    error_details = ""
    
    if isinstance(response_data, str):
        if "Job failed." in response_data:
            error_detected = True
            error_type = "PARROT JOB FAILURE"
            error_details = response_data[:500]
        elif "Error:" in response_data and any(keyword in response_data for keyword in [
            "timeout", "connection", "network", "server", "HTTPSConnectionPool", "Read timed out"
        ]):
            error_detected = True
            error_type = "NETWORK/CONNECTION ERROR"
            error_details = response_data[:500]
    
    elif isinstance(response_data, dict):
        if "raw_response" in response_data:
            raw_resp = response_data["raw_response"]
            if isinstance(raw_resp, str):
                if "Job failed." in raw_resp:
                    error_detected = True
                    error_type = "PARROT JOB FAILURE"
                    error_details = raw_resp[:500]
                elif "Error:" in raw_resp and any(keyword in raw_resp for keyword in [
                    "timeout", "connection", "network", "server", "HTTPSConnectionPool", 
                    "Read timed out", "All attempts returned None", "Received None response"
                ]):
                    error_detected = True
                    error_type = "NETWORK/CONNECTION ERROR"
                    error_details = raw_resp[:500]
    
    if error_detected:
        print(f"\n[CRITICAL] {error_type} DETECTED")
        print(f"Agent: {llm_id} | Round: {round_num}")
        print(f"Error Details: {error_details}")
        print("Program is now PAUSED due to server/network error.")
        input("Press Enter when the issue is resolved to retry this agent...\n")
        return True
    
    return False

def read_file(file_path):
    """Reads a file and returns its content. If the file is missing, returns an empty string."""
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found. Using empty content.")
        return ""
    
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    
    if "reflection" in file_path:
        from utils import parse_reflection_content
        return parse_reflection_content(content)
    
    return content

def generate_filenames(exp_run_dir,llm_id, current_round):
    """
    Generates file paths for a given LLM.
    - If `current_round == 1`, read from `init/r0/`
    - If `current_round > 1`, read from `exp/[timestamp]/input/rX/`
    """
    previous_round = current_round - 1
    if current_round == 1:
        data_dir = init.INIT_R0_DIR
    else:
        data_dir = os.path.join(exp_run_dir, "input", f"r{previous_round}")

    return {
        "plans": os.path.join(data_dir, f"{llm_id}_r{previous_round}_plans.txt"),
        "insights": os.path.join(data_dir, f"{llm_id}_r{previous_round}_insights.txt"),
        "reflection": os.path.join(data_dir, f"{llm_id}_r{previous_round}_reflection.txt"),
        "market": os.path.join(data_dir, f"{llm_id}_r{previous_round}_market.txt"),
        "portfolio": os.path.join(data_dir, f"{llm_id}_r{previous_round}_portfolio.txt")
    }





