"""
ERTS Scenario Encoder (Pipeline Step 1)
=======================================
Encodes raw ethical scenarios into the Ethical Consequence Space (ECS).

This is the formal encoding step that converts human-readable ethical
dilemmas into structured, machine-processable consequence vectors.

Patent-critical: This encoder defines the INPUT SPECIFICATION of the
perturbation system. Without a formal encoding, perturbations would
operate on unstructured data (which is not patentable).
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
import numpy as np

from .types import (
    ETHICAL_VARIABLES, NEGATIVE_VARIABLES, POSITIVE_VARIABLES,
    EthicalConsequenceVector, DeploymentDomain,
)


@dataclass
class EncodedAction:
    """An action encoded into the Ethical Consequence Space."""
    action_id: str
    description: str
    vector: EthicalConsequenceVector
    raw_consequences: Dict[str, float]


@dataclass
class EncodedScenario:
    """
    A fully encoded ethical scenario ready for perturbation.

    This is the formal input to the perturbation engine.
    It contains the scenario metadata plus ECS-encoded actions.
    """
    scenario_id: str
    title: str
    description: str
    domain: DeploymentDomain
    ethical_dimensions: List[str]
    actions: List[EncodedAction]
    metadata: Dict = field(default_factory=dict)

    def get_action(self, action_id: str) -> Optional[EncodedAction]:
        """Retrieve an action by ID."""
        for a in self.actions:
            if a.action_id == action_id:
                return a
        return None

    def num_actions(self) -> int:
        return len(self.actions)


# Domain mapping from category strings to DeploymentDomain enum
DOMAIN_MAP = {
    "autonomous_vehicles": DeploymentDomain.AUTONOMOUS_VEHICLES,
    "healthcare_ai": DeploymentDomain.HEALTHCARE,
    "hiring_bias": DeploymentDomain.HIRING,
    "financial_ai": DeploymentDomain.FINANCE,
    "military_ai": DeploymentDomain.MILITARY,
    "education_ai": DeploymentDomain.EDUCATION,
    "privacy_surveillance": DeploymentDomain.PRIVACY,
    "disaster_response": DeploymentDomain.GENERAL,
    "human_ai_interaction": DeploymentDomain.GENERAL,
    "corporate_pressure": DeploymentDomain.GENERAL,
    "moral_ambiguity": DeploymentDomain.GENERAL,
}


class ScenarioEncoder:
    """
    Encodes raw scenario dictionaries into the Ethical Consequence Space.

    Pipeline Step 1: Raw Scenario → EncodedScenario

    The encoding process:
    1. Parse scenario metadata (id, title, category, dimensions)
    2. Map category to DeploymentDomain
    3. For each action:
       a. Extract all consequence key-value pairs
       b. Clamp values to [0.0, 1.0]
       c. Fill missing variables with neutral default (0.5)
       d. Construct EthicalConsequenceVector
    4. Validate encoding integrity
    """

    def __init__(self, fill_missing: bool = True, default_value: float = 0.5):
        """
        Args:
            fill_missing: If True, missing ethical variables get default_value.
            default_value: Value for missing variables (0.5 = neutral).
        """
        self.fill_missing = fill_missing
        self.default_value = default_value
        self._encoding_log: List[Dict] = []

    def encode(self, scenario: Dict) -> EncodedScenario:
        """
        Encode a single raw scenario into the Ethical Consequence Space.

        Args:
            scenario: Raw scenario dict with 'id', 'actions', 'consequences', etc.

        Returns:
            EncodedScenario with all actions mapped to ECS vectors.

        Raises:
            ValueError: If scenario is missing required fields.
        """
        # Validate required fields
        if "id" not in scenario:
            raise ValueError("Scenario missing required 'id' field")
        if "actions" not in scenario or len(scenario["actions"]) < 2:
            raise ValueError(f"Scenario {scenario['id']}: needs at least 2 actions")

        # Map category to deployment domain
        category = scenario.get("category", "general")
        domain = DOMAIN_MAP.get(category, DeploymentDomain.GENERAL)

        # Encode each action
        encoded_actions = []
        for action in scenario["actions"]:
            raw_cons = action.get("consequences", {})

            # Build ECS vector with clamping and optional fill
            values = {}
            for var in ETHICAL_VARIABLES:
                if var in raw_cons:
                    values[var] = max(0.0, min(1.0, float(raw_cons[var])))
                elif self.fill_missing:
                    values[var] = self.default_value

            ecv = EthicalConsequenceVector(values=values)

            encoded_actions.append(EncodedAction(
                action_id=action.get("id", f"A{len(encoded_actions)+1}"),
                description=action.get("description", ""),
                vector=ecv,
                raw_consequences=dict(raw_cons),
            ))

        encoded = EncodedScenario(
            scenario_id=scenario["id"],
            title=scenario.get("title", ""),
            description=scenario.get("description", ""),
            domain=domain,
            ethical_dimensions=list(scenario.get("ethical_dimensions", [])),
            actions=encoded_actions,
            metadata={"original_category": category},
        )

        # Log encoding
        self._encoding_log.append({
            "scenario_id": scenario["id"],
            "domain": domain.value,
            "n_actions": len(encoded_actions),
            "variables_present": sum(
                1 for a in encoded_actions
                for v in ETHICAL_VARIABLES if v in a.raw_consequences
            ) / max(len(encoded_actions), 1),
        })

        return encoded

    def encode_batch(self, scenarios: List[Dict]) -> List[EncodedScenario]:
        """Encode multiple scenarios."""
        return [self.encode(s) for s in scenarios]

    def get_encoding_stats(self) -> Dict:
        """Return statistics about all encodings performed."""
        if not self._encoding_log:
            return {"total_encoded": 0}

        domains = {}
        for entry in self._encoding_log:
            d = entry["domain"]
            domains[d] = domains.get(d, 0) + 1

        return {
            "total_encoded": len(self._encoding_log),
            "domain_distribution": domains,
            "avg_variables_per_action": round(
                np.mean([e["variables_present"] for e in self._encoding_log]), 1
            ),
        }
