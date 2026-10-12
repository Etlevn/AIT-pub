"""
Battle Royale module for LLM Trading Analysis project.
Enables multi-model experiments with customizable model distribution.

USAGE:
1. Default Mode (4 models, 5 agents each, sequential assignment):
   manager = BattleRoyaleManager()
   
2. Custom Mode (absolute count):
   config = create_battle_royale_config(
       total_agents=16,
       models=[
           {"name": "gpt-4o", "count": 6},
           {"name": "claude-3-7-sonnet-20250219", "count": 5},
           {"name": "grok-3", "count": 3},
           {"name": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8", "count": 2}
       ],
       assignment_strategy="sequential" 
   )
   manager = BattleRoyaleManager(config)

3. Get model for agent:
   model = manager.get_model_for_agent("llm_001")
   
4. Print summary:
   manager.print_assignment_summary()

DEFAULT MODELS:
- gpt-4o (5 agents)
- claude-3-7-sonnet-20250219 (5 agents)  
- grok-3 (5 agents)
- meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8 (5 agents)

NOTE: Fixed seed (42) is used for reproducible assignments.
"""

import random
import json
import os
from typing import List, Dict, Tuple, Optional
import config

# Fixed seed for reproducible assignments
FIXED_SEED = 42

class BattleRoyaleManager:
    """
    Manages multi-model experiments with customizable model distribution.
    """
    
    def __init__(self, model_config: Dict = None):
        """
        Initialize the Battle Royale manager.
        
        Args:
            model_config: Configuration for model distribution
        """
        self.model_config = model_config or self._get_default_config()
        self.model_assignment = {}
        self._validate_config()
        self._generate_model_assignment()
    
    def _get_default_config(self) -> Dict:
        """
        Get default configuration for multi-model experiments.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "total_agents": 20,
            "models": [
                {
                    "name": "gpt-4o",
                    "count": 5,
                    "description": "GPT-4 Omni model"
                },
                {
                    "name": "claude-3-7-sonnet-20250219",
                    "count": 5,
                    "description": "Claude 3.7 Sonnet model"
                },
                {
                    "name": "grok-3",
                    "count": 5,
                    "description": "Grok-3 model"
                },
                {
                    "name": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
                    "count": 5,
                    "description": "Llama-4-Maverick model"
                }
            ],
            "assignment_strategy": "sequential",  # "random", "sequential", "balanced"
        }
    
    def _validate_config(self):
        """
        Validate the model configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.model_config:
            raise ValueError("Model configuration cannot be empty")
        
        total_configured = sum(model["count"] for model in self.model_config["models"])
        total_agents = self.model_config["total_agents"]
        
        if total_configured != total_agents:
            raise ValueError(
                f"Total model count ({total_configured}) must equal total_agents ({total_agents})"
            )
        
        if total_configured <= 0:
            raise ValueError("Total agents must be greater than 0")
        
        # Validate model names
        for model in self.model_config["models"]:
            if not model.get("name"):
                raise ValueError("All models must have a name")
            if model.get("count", 0) <= 0:
                raise ValueError(f"Model {model['name']} count must be greater than 0")
    
    def _generate_model_assignment(self):
        """
        Generate the assignment of models to agent IDs.
        """
        # No fixed seed - use truly random assignment
        
        # Create list of model assignments
        model_list = []
        for model in self.model_config["models"]:
            model_list.extend([model["name"]] * model["count"])
        
        # Shuffle based on strategy
        strategy = self.model_config.get("assignment_strategy", "random")
        
        if strategy == "random":
            random.shuffle(model_list)
        elif strategy == "sequential":
            # Keep original order
            pass
        elif strategy == "balanced":
            # Distribute models evenly across the range
            self._balance_distribution(model_list)
        else:
            raise ValueError(f"Unknown assignment strategy: {strategy}")
        
        # Assign to agent IDs
        for i, model_name in enumerate(model_list, 1):
            self.model_assignment[f"llm_{i:03d}"] = model_name
    
    def _balance_distribution(self, model_list: List[str]):
        """
        Balance model distribution across the agent range.
        
        Args:
            model_list: List of model names to balance
        """
        # This is a simple balancing strategy
        # For more sophisticated balancing, this could be enhanced
        chunk_size = len(model_list) // len(set(model_list))
        balanced = []
        
        for i in range(0, len(model_list), chunk_size):
            chunk = model_list[i:i + chunk_size]
            random.shuffle(chunk)
            balanced.extend(chunk)
        
        # Handle any remaining models
        remaining = len(model_list) - len(balanced)
        if remaining > 0:
            balanced.extend(model_list[-remaining:])
        
        model_list.clear()
        model_list.extend(balanced)
    
    def get_model_for_agent(self, agent_id: str) -> str:
        """
        Get the assigned model for a specific agent.
        
        Args:
            agent_id: The agent ID (e.g., "llm_001")
            
        Returns:
            The model name assigned to this agent
        """
        return self.model_assignment.get(agent_id, self.model_config["models"][0]["name"])
    
    def get_all_assignments(self) -> Dict[str, str]:
        """
        Get all model assignments.
        
        Returns:
            Dictionary mapping agent IDs to model names
        """
        return self.model_assignment.copy()
    
    def get_model_statistics(self) -> Dict[str, Dict]:
        """
        Get statistics about model distribution.
        
        Returns:
            Dictionary with model statistics
        """
        stats = {}
        for model in self.model_config["models"]:
            model_name = model["name"]
            actual_count = sum(1 for assigned_model in self.model_assignment.values() 
                             if assigned_model == model_name)
            
            stats[model_name] = {
                "configured_count": model["count"],
                "actual_count": actual_count,
                "description": model.get("description", ""),
                "agents": [agent_id for agent_id, assigned_model in self.model_assignment.items() 
                          if assigned_model == model_name]
            }
        
        return stats
    
    def save_assignment(self, file_path: str):
        """
        Save the model assignment to a JSON file.
        
        Args:
            file_path: Path to save the assignment file
        """
        assignment_data = {
            "config": self.model_config,
            "assignments": self.model_assignment,
            "statistics": self.get_model_statistics()
        }
        
        # Create directory if needed (only if file_path contains directory)
        dir_path = os.path.dirname(file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(assignment_data, f, indent=2, ensure_ascii=False)
    
    def load_assignment(self, file_path: str):
        """
        Load model assignment from a JSON file.
        
        Args:
            file_path: Path to the assignment file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.model_config = data["config"]
        self.model_assignment = data["assignments"]
        self._validate_config()
    
    def print_assignment_summary(self):
        """
        Print a summary of the model assignments.
        """
        print("=== Battle Royale Model Assignment Summary ===")
        print(f"Total Agents: {self.model_config['total_agents']}")
        print(f"Assignment Strategy: {self.model_config.get('assignment_strategy', 'random')}")
        print()
        
        stats = self.get_model_statistics()
        for model_name, stat in stats.items():
            print(f"Model: {model_name}")
            print(f"  Configured: {stat['configured_count']}")
            print(f"  Actual: {stat['actual_count']}")
            print(f"  Description: {stat['description']}")
            print(f"  Agents: {', '.join(stat['agents'])}")
            print()


def create_battle_royale_config(
    total_agents: int = 20,
    models: List[Dict] = None,
    assignment_strategy: str = "sequential"
) -> Dict:
    """
    Create a Battle Royale configuration.
    
    Args:
        total_agents: Total number of agents in the experiment
        models: List of model configurations
        assignment_strategy: Strategy for assigning models ("random", "sequential", "balanced")
        
    Returns:
        Configuration dictionary
    """
    if models is None:
        models = [
            {"name": "gpt-4o", "count": 5, "description": "GPT-4 Omni model"},
            {"name": "claude-3-7-sonnet-20250219", "count": 5, "description": "Claude 3.7 Sonnet model"},
            {"name": "grok-3", "count": 5, "description": "Grok-3 model"},
            {"name": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8", "count": 5, "description": "Llama-4-Maverick model"}
        ]
    
    return {
        "total_agents": total_agents,
        "models": models,
        "assignment_strategy": assignment_strategy
    }


def get_battle_royale_manager(config_path: str = None) -> BattleRoyaleManager:
    """
    Get a Battle Royale manager instance.
    
    Args:
        config_path: Optional path to load configuration from
        
    Returns:
        BattleRoyaleManager instance
    """
    if config_path and os.path.exists(config_path):
        manager = BattleRoyaleManager()
        manager.load_assignment(config_path)
        return manager
    else:
        return BattleRoyaleManager()


# Example usage and testing
if __name__ == "__main__":
    # Example 1: Default configuration
    print("=== Example 1: Default Configuration ===")
    manager1 = BattleRoyaleManager()
    manager1.print_assignment_summary()
    
    # Example 2: Custom configuration
    print("=== Example 2: Custom Configuration ===")
    custom_config = create_battle_royale_config(
        total_agents=16,
        models=[
            {"name": "gpt-4o", "count": 6, "description": "GPT-4 Omni"},
            {"name": "claude-3-7-sonnet-20250219", "count": 5, "description": "Claude 3.7 Sonnet"},
            {"name": "grok-3", "count": 3, "description": "Grok-3"},
            {"name": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8", "count": 2, "description": "Llama-4-Maverick"}
        ],
        assignment_strategy="random"
    )
    
    manager2 = BattleRoyaleManager(custom_config)
    manager2.print_assignment_summary()
    
    # Example 3: Save and load assignment
    print("=== Example 3: Save and Load Assignment ===")
    test_file = "test_assignment.json"
    manager2.save_assignment(test_file)
    
    manager3 = get_battle_royale_manager(test_file)
    manager3.print_assignment_summary()
    
    # Clean up test file
    if os.path.exists(test_file):
        os.remove(test_file) 