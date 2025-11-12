"""Configuration utilities."""

import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to config.yaml file

    Returns:
        Configuration dictionary
    """
    # Load environment variables
    load_dotenv()

    # Load YAML config
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    # Override with environment variables
    config['openai_api_key'] = os.getenv('OPENAI_API_KEY')
    config['default_model'] = os.getenv('DEFAULT_MODEL', config.get('agent', {}).get('model', 'gpt-4o-mini'))

    return config


def get_benchmark_config(config: Dict[str, Any], benchmark_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific benchmark.

    Args:
        config: Full configuration dictionary
        benchmark_name: Name of the benchmark

    Returns:
        Benchmark-specific configuration
    """
    benchmarks = config.get('benchmarks', {})
    return benchmarks.get(benchmark_name.lower(), {})
