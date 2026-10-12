"""
NLP Behavioral Bias Evaluation Module

This module provides tools for analyzing LLM trading agent outputs
for behavioral and cognitive biases using natural language processing.

Main components:
- nlp_main.py: Command-line interface for running evaluations
- nlp_utils.py: Core utility functions and API calls
- nlp_prmt.txt: Evaluation prompt template
- nlp_config.json: Configuration settings

Usage:
    from nlp import nlp_utils
    
    # Load configuration
    cfg = nlp_utils.load_config()
    
    # Run evaluation
    result = nlp_utils.call_llm_for_evaluation(prompt, model_name, api_mode)

See README.md for detailed documentation.
"""

__version__ = "1.0.0"
__author__ = "AIT Project"

# Import main utilities for easy access
from . import nlp_utils

__all__ = ['nlp_utils']

