#!/usr/bin/env python3
"""
NLP Utilities Module for Behavioral Bias Evaluation
Provides helper functions for text processing, API calls, and result handling.
"""

import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# Add parent directory to path to import project modules
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
import ord


def load_prompt_template(config: Dict[str, Any] = None) -> str:
    """Load the NLP evaluation prompt template."""
    if config is None:
        config = load_config()
    
    prompt_filename = config["file_settings"]["prompt_template"]
    prompt_file = CURRENT_DIR / prompt_filename
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_file}")
    
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read()


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load NLP evaluation configuration."""
    if config_path is None:
        config_file = CURRENT_DIR / "nlp_config.json"
    else:
        config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    
    return cfg


def truncate_text(text: str, max_length: int = 2000) -> str:
    """Truncate text to specified maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def build_evaluation_prompt(
    system_prompt: str,
    evaluation_target: str,
    target_text: str,
    agent_info: Dict[str, Any],
    config: Dict[str, Any] = None
) -> str:
    """
    Build a complete evaluation prompt for API call using template substitution.
    
    Args:
        system_prompt: Base system prompt with mechanism definitions
        evaluation_target: "plan" or "insight"
        target_text: Text to be evaluated
        agent_info: Dictionary with agent metadata (llm, round, market_type, etc.)
        config: Configuration dictionary (not used in current implementation)
        
    Returns:
        Complete prompt string with placeholders substituted
    """
    return build_prompt(system_prompt, evaluation_target, target_text, agent_info)


def build_prompt(
    system_prompt: str,
    evaluation_target: str,
    target_text: str,
    agent_info: Dict[str, Any]
) -> str:
    """Build prompt using template substitution with placeholders"""
    # Extract agent info
    lm_id = agent_info.get('llm', 'N/A')
    round_num = agent_info.get('round', 'N/A')
    market_type = agent_info.get('market_type', 'N/A')
    
    # For template format, we need to substitute placeholders directly
    # Since the template expects both plan and insights, we'll use the target_text for both
    # Use safe_substitute to avoid KeyError for unmatched placeholders
    from string import Template
    
    # Convert the system_prompt to use Template format
    # Replace {placeholder} with $placeholder for Template
    template_str = system_prompt.replace('{LM_id}', '${LM_id}')
    template_str = template_str.replace('{round}', '${round}')
    template_str = template_str.replace('{market_type}', '${market_type}')
    template_str = template_str.replace('{price_info}', '${price_info}')
    template_str = template_str.replace('{recent_returns}', '${recent_returns}')
    template_str = template_str.replace('{plan_text}', '${plan_text}')
    template_str = template_str.replace('{insights_text}', '${insights_text}')
    
    # Create template and substitute
    template = Template(template_str)
    prompt = template.safe_substitute(
        LM_id=lm_id,
        round=round_num,
        market_type=market_type,
        price_info="N/A",  # Not available in current data
        recent_returns="N/A",  # Not available in current data
        plan_text=target_text if evaluation_target == "plan" else "N/A",
        insights_text=target_text if evaluation_target == "insight" else "N/A"
    )
    
    return prompt


def extract_json_from_response(response_text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from LLM response.
    Handles markdown code blocks and other formatting.
    """
    if not response_text:
        return {"error": "Empty response"}
    
    # Try direct parsing first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    patterns = [
        r'```json\s*(.*?)\s*```',  # ```json ... ```
        r'```\s*(.*?)\s*```',       # ``` ... ```
        r'\{.*\}',                   # Any JSON object
    ]
    
    for pattern in patterns:
        try:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                json_str = match.group(1) if pattern.startswith('```') else match.group()
                return json.loads(json_str)
        except (json.JSONDecodeError, AttributeError):
            continue
    
    # If all parsing attempts fail
    return {
        "error": "Failed to extract valid JSON",
        "raw_response": response_text[:500]
    }


def call_llm_for_evaluation(
    prompt: str,
    model_name: str = "deepseek-chat",
    api_mode: str = "deepseek"
) -> Dict[str, Any]:
    """
    Call LLM API for evaluation with pause-on-error mechanism.
    
    Args:
        prompt: Complete prompt to send
        model_name: Model identifier
        api_mode: API mode (deepseek, openai, expected_parrot)
        
    Returns:
        Parsed JSON response or error dictionary
    """
    # Temporarily set API mode
    original_mode = config.API_CONFIG["api_mode"]
    config.API_CONFIG["api_mode"] = api_mode
    
    try:
        # Call the LLM
        response = ord.chat_with_llm(prompt, model_name)
        
        # Check for server/network errors and pause if needed
        if pause_on_api_error(response):
            print(f"[nlp_utils] Retrying after API error...")
            response = ord.chat_with_llm(prompt, model_name)
        
        # Extract and return JSON
        return extract_json_from_response(response)
        
    finally:
        # Restore original API mode
        config.API_CONFIG["api_mode"] = original_mode


def pause_on_api_error(response):
    """
    Detect API errors and pause for manual retry.
    Similar to ord.py's pause_on_server_error but adapted for NLP evaluation.
    """
    error_detected = False
    error_type = ""
    error_details = ""
    
    # Check for error responses
    if isinstance(response, str):
        if "Error:" in response and any(keyword in response for keyword in [
            "timeout", "connection", "network", "server", "HTTPSConnectionPool", 
            "Read timed out", "API key", "rate limit", "quota", "unauthorized"
        ]):
            error_detected = True
            error_type = "API/NETWORK ERROR"
            error_details = response[:500]
    
    if error_detected:
        print(f"\n[CRITICAL] {error_type} DETECTED")
        print(f"Error Details: {error_details}")
        print("Program is now PAUSED due to API/network error.")
        input("Press Enter when the issue is resolved to retry...\n")
        return True
    
    return False


def validate_evaluation_result(result: Dict[str, Any], expected_mechanisms: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate evaluation result structure.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Check for error field
    if "error" in result:
        errors.append(f"API error: {result.get('error')}")
        return False, errors
    
    # Check required fields
    required_fields = ["mechanism_assessments", "behavioral_bias_summary", "summary"]
    for field in required_fields:
        if field not in result:
            errors.append(f"Missing required field: {field}")
    
    # Check mechanism_assessments structure
    if "mechanism_assessments" in result:
        assessments = result["mechanism_assessments"]
        if not isinstance(assessments, list):
            errors.append("mechanism_assessments should be a list")
        elif len(assessments) != len(expected_mechanisms):
            errors.append(f"Expected {len(expected_mechanisms)} mechanisms, got {len(assessments)}")
        else:
            # Validate each assessment
            for i, assessment in enumerate(assessments):
                if not isinstance(assessment, dict):
                    errors.append(f"Assessment {i} is not a dictionary")
                    continue
                
                required_assessment_fields = [
                    "mechanism_id", "mechanism_category", "label", 
                    "confidence", "numeric_score", "evidence_sentences"
                ]
                for field in required_assessment_fields:
                    if field not in assessment:
                        errors.append(f"Assessment {i} missing field: {field}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def generate_output_filename(
    simulation_index: str,
    round_num: str,
    agent_id: str,
    evaluation_target: str
) -> str:
    """Generate standardized output filename using new format: {simulation_index}_{round}_{llm}_{plan/insight}.json"""
    return f"{simulation_index}_{round_num}_{agent_id}_{evaluation_target}.json"


def save_json_result(result: Dict[str, Any], output_path: Path) -> bool:
    """Save evaluation result to JSON file."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to save JSON: {e}")
        return False


def get_timestamp() -> str:
    """Get current timestamp in standard format."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def print_progress(current: int, total: int, agent_id: str, status: str = ""):
    """Print formatted progress message."""
    percentage = (current / total * 100) if total > 0 else 0
    print(f"  [{current}/{total}] ({percentage:.1f}%) - {agent_id} {status}")

