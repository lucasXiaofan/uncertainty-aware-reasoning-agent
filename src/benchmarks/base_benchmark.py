"""Base benchmark interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class BenchmarkResult:
    """Container for benchmark evaluation results."""
    benchmark_name: str
    accuracy: float
    confidence: float
    num_interactions: float
    total_cases: int
    detailed_results: List[Dict[str, Any]]


class BaseBenchmark(ABC):
    """Abstract base class for medical benchmarks."""

    def __init__(self, name: str, data_path: str = None):
        self.name = name
        self.data_path = data_path
        self.results = []

    @abstractmethod
    def load_data(self) -> List[Dict[str, Any]]:
        """
        Load benchmark data.

        Returns:
            List of test cases
        """
        pass

    @abstractmethod
    def evaluate(self, agent, test_cases: List[Dict[str, Any]]) -> BenchmarkResult:
        """
        Evaluate agent on benchmark.

        Args:
            agent: The agent to evaluate
            test_cases: List of test cases

        Returns:
            BenchmarkResult with metrics
        """
        pass

    def _calculate_accuracy(self, predictions: List[str], ground_truth: List[str]) -> float:
        """Calculate accuracy metric."""
        if not predictions or not ground_truth:
            return 0.0
        correct = sum(1 for p, g in zip(predictions, ground_truth) if p.lower() == g.lower())
        return correct / len(predictions)
