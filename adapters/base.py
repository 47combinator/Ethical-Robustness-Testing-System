"""
ERTS Model Adapter Interface (Pipeline Step 3)
================================================
Abstract interface for wrapping any ethical AI model.

The adapter pattern decouples ERTS from specific model implementations.
Any model — rule-based, neural network, RLHF, virtue-based, or even
a third-party API — can be tested by implementing this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, List
from core.types import DecisionResult
from core.scenario import EncodedScenario


class ModelAdapter(ABC):
    """
    Abstract interface for ethical AI models under test.

    Any model can be tested by ERTS if it implements:
    1. evaluate(scenario) → DecisionResult
    2. name property

    This is what makes ERTS a TESTING INFRASTRUCTURE, not a model.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable model name."""
        ...

    @abstractmethod
    def evaluate(self, scenario: EncodedScenario) -> DecisionResult:
        """
        Run the model on a scenario and return its decision.

        Args:
            scenario: ECS-encoded scenario (may be original or perturbed)

        Returns:
            DecisionResult with chosen action, confidence, and scores
        """
        ...

    def evaluate_batch(self, scenarios: List[EncodedScenario]) -> List[DecisionResult]:
        """Evaluate multiple scenarios."""
        return [self.evaluate(s) for s in scenarios]
