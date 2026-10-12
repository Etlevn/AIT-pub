"""
JSON extraction utilities for LLM Trading Analysis project.
Extracted from ord.py to improve code organization.
"""

import json
import re
import ast
import config
from typing import Dict, Any, Optional

def extract_json(response_text):
    """
    Attempts to parse the response_text into JSON or Python literal format.
    Falls back to extracting a JSON block if full parse fails.
    Handles XML-like tags by removing them completely.
    """
    if response_text is None:
        print("[extract_json] Warning: response_text is None")
        return None
    
    response_text = re.sub(r'<[^>]*>', '', response_text)
    
    cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text.strip(), flags=re.IGNORECASE)
    cleaned_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', cleaned_text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        try:
            literal = ast.literal_eval(cleaned_text)
            if isinstance(literal, dict):
                return literal
        except Exception:
            pass
        print(f"[extract_json] Failed to parse full JSON or literal. Trying block fallback...")
        return extract_json_block(response_text)

def extract_json_block(text):
    """
    Attempts to extract the first valid JSON object from a larger text block.
    Useful when LLM returns explanation before or after the JSON.
    """
    import re
    
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern, text)
    matches.sort(key=len, reverse=True)
    
    for match in matches:
        try:
            parsed = json.loads(match)
            print(f"[extract_json_block] Successfully parsed JSON block of length {len(match)}")
            print(f"[extract_json_block] Parsed JSON keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'Not a dict'}")
            return parsed
        except json.JSONDecodeError as e:
            print(f"[extract_json_block] Failed to parse JSON block: {e}")
            continue
    
    brace_stack = []
    start = None
    in_string = False
    escape_next = False

    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        
            
        if char == '\\':
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '{':
                if not brace_stack:
                    start = i
                brace_stack.append('{')
            elif char == '}':
                if brace_stack:
                    brace_stack.pop()
                    if not brace_stack and start is not None:
                        json_candidate = text[start:i+1]
                        try:
                            return json.loads(json_candidate)
                        except json.JSONDecodeError as e:
                            print(f"[extract_json_block] Skipping invalid block: {e}")
                            continue

    print("[extract_json_block] No valid JSON block found.")
    return None

def try_get_valid_json(prompt_text, contents, max_attempts=3, model_name="gpt-4o", exp_run_dir=None, llm_id=None, round_num=None):
    """
    Tries to get a valid JSON response from the LLM.
    Includes retry logic for structured failure detection.
    Returns response_json or fallback raw_response.
    """
    # Import here to avoid circular import
    from ord import chat_with_llm
    import os
    import time
    
    for attempt in range(1, max_attempts + 1):
        print(f"[utils.py] Requesting response (attempt {attempt}/3)...")
        response_text = chat_with_llm(prompt_text, model_name)
        
        if response_text is None:
            print(f"[utils.py] Attempt {attempt} returned None response.")
            continue

        if response_text and config.DEBUG_CONFIG["save_raw_responses"]:
            if exp_run_dir:
                debug_dir = os.path.join(exp_run_dir, config.DEBUG_CONFIG["debug_directory"])
            else:
                debug_dir = config.DEBUG_CONFIG["debug_directory"]
            os.makedirs(debug_dir, exist_ok=True)
            
            if llm_id and round_num is not None:
                debug_filename = f"{debug_dir}/{llm_id}_r{round_num}_debug.txt"
            else:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                debug_filename = f"{debug_dir}/raw_response_attempt_{attempt}_{timestamp}.txt"
            
            with open(debug_filename, "w", encoding="utf-8") as f:
                f.write(f"=== RAW RESPONSE (Attempt {attempt}) ===\n")
                f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Model: {model_name}\n")
                f.write(f"Response Length: {len(response_text)} characters\n")
                f.write(f"Response Preview: {response_text[:200]}...\n")
                f.write("\n=== FULL RESPONSE ===\n")
                f.write(response_text)
                f.write("\n=== END RESPONSE ===\n")
            
            print(f"[utils.py] DEBUG: Raw response saved to {debug_filename}")
            print(f"[utils.py] Response length: {len(response_text)} characters")
            print(f"[utils.py] Response preview: {response_text[:100]}...")

        response_json = extract_json(response_text)
        if response_json is not None:
            print(f"[utils.py] JSON parsed successfully on attempt {attempt}.")
            print(f"[utils.py] Parsed JSON keys: {list(response_json.keys())}")
            return response_json
        else:
            print(f"[utils.py] Attempt {attempt} failed to parse JSON.")

    print(f"[utils.py] All attempts failed. Saving raw response.")
    return {"raw_response": response_text if response_text is not None else "Error: All attempts returned None"}

def pause_on_null_response(llm_id, round_num, response_json):
    """
    Detects if the response is a null response, even if it appears inside a stringified JSON in 'raw_response'.
    Pauses execution for user intervention.
    """
    if isinstance(response_json, str):
        if response_json.strip() in ('"{\\"llm_response\\": null}"', '\'{"llm_response": null}\''):
            pass

    if isinstance(response_json, dict):
        if "llm_response" in response_json and response_json["llm_response"] is None:
            print(f"\n[CRITICAL] NULL RESPONSE DETECTED")
            print(f"Agent: {llm_id} | Round: {round_num}")
            print("Likely cause: Parrot job failed and returned `null` response.")
            input("Press Enter when ready to retry...\n")
            return True

        if "raw_response" in response_json and isinstance(response_json["raw_response"], str):
            try:
                inner = json.loads(response_json["raw_response"])
                if isinstance(inner, dict) and "llm_response" in inner and inner["llm_response"] is None:
                    print(f"\n[CRITICAL] NULL RESPONSE DETECTED (stringified)")
                    print(f"Agent: {llm_id} | Round: {round_num}")
                    print("Likely cause: Parrot job failed and returned `null` inside stringified JSON.")
                    input("Press Enter when ready to retry...\n")
                    return True
            except Exception:
                pass

        if "raw_response" in response_json and isinstance(response_json["raw_response"], str):
            raw_str = response_json["raw_response"]
            try:
                literal = ast.literal_eval(raw_str)
                if isinstance(literal, dict) and "llm_response" in literal and literal["llm_response"] is None:
                    print(f"\n[CRITICAL] NULL RESPONSE DETECTED (literal)")
                    print(f"Agent: {llm_id} | Round: {round_num}")
                    print("Likely cause: Parrot job failed and returned `None` via literal dict.")
                    input("Press Enter when ready to retry...\n")
                    return True
            except Exception:
                pass

    return False 

def parse_reflection_content(content: str) -> str:
    """
    Parse reflection content, handle all possible formats
    Logic is completely consistent with successfully fixing all files
    
    Args:
        content: Original reflection content
        
    Returns:
        Parsed plain text content
    """
    if not content or content.strip() == "":
        return ""
    
    content = content.strip()
    
    if not content.startswith("{") and not content.startswith("'{"):
        return content
    
    if content == "{'llm_response': None}" or content == '{"llm_response": null}':
        return ""
    
    if (content.startswith("{") and content.endswith("}")) or (content.startswith("{'") and content.endswith("'}")):
        try:
            parsed = ast.literal_eval(content)
            if isinstance(parsed, dict) and "llm_response" in parsed:
                response = parsed["llm_response"]
                if response is None:
                    return ""
                return str(response)
        except (ValueError, SyntaxError):
            pass
    
    if content.startswith("{") and content.endswith("}"):
        try:
            import json
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "llm_response" in parsed:
                response = parsed["llm_response"]
                if response is None:
                    return ""
                return str(response)
        except json.JSONDecodeError:
            pass
    
    if "llm_response" in content:
        try:
            import re
            pattern = r"'llm_response':\s*\"(.*)\""
            match = re.search(pattern, content, re.DOTALL)
            if match:
                extracted = match.group(1)
                # Handle escape characters
                extracted = extracted.replace('\\n', '\n').replace('\\t', '\t')
                if extracted == "None" or extracted == "":
                    return ""
                    return extracted
            
            pattern = r"'llm_response':\s*'(.*)'"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                extracted = match.group(1)
                # Handle escape characters
                extracted = extracted.replace('\\n', '\n').replace('\\t', '\t')
                if extracted == "None" or extracted == "":
                    return ""
                return extracted
        except Exception:
            pass
    
    return content 
