"""
ERTS Base Perturbation Function
================================
Abstract base class for all perturbation functions.

Patent-critical: Every perturbation is a FORMAL TRANSFORMATION FUNCTION:
    P: (x, θ) → x'

Where:
    x  = original ECS-encoded scenario (input)
    θ  = perturbation parameters (type-specific)
    x' = perturbed scenario (output)

This is NOT noise injection. Each perturbation has:
    - A defined semantic target (which ethical variables it modifies)
    - A defined transformation rule (how it modifies them)
    - A defined magnitude parameter θ (how much it modifies)
    - Constraint satisfaction (output must pass validity checks)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import copy

from core.types import PerturbationType, DeploymentDomain
from core.scenario import EncodedScenario
from perturbations.constraints import PerturbationConstraints


@dataclass
class PerturbationParams:
    """
    Parameters θ for a perturbation function.

    Every perturbation has:
    - target_variables: which ethical variables are affected
    - deltas: how much each target variable changes (signed)
    - magnitude: overall strength of the perturbation (0-1)
    - noise_std: optional Gaussian noise added for realism
    """
    target_variables: Dict[str, float]   # variable_name → signed delta
    magnitude: float = 0.7               # Overall strength (0-1)
    noise_std: float = 0.0               # Optional noise
    extra: Dict = field(default_factory=dict)  # Type-specific params


@dataclass
class PerturbationFunction:
    """
    A single, formally defined perturbation function.

    This is the core unit of the system. Each function is a repeatable,
    deterministic transformation with clear input → output mapping.
    """
    id: str                              # Unique identifier (e.g., "PF_CR_01")
    name: str                            # Human-readable name
    perturbation_type: PerturbationType  # One of 7 categories
    description: str                     # What this perturbation simulates
    severity: float                      # 0-1, how aggressive
    target_domains: List[DeploymentDomain]  # Which domains it applies to
    params: PerturbationParams           # The transformation parameters θ

    def applies_to_domain(self, domain: DeploymentDomain) -> bool:
        """Check if this perturbation is relevant to a deployment domain."""
        if DeploymentDomain.GENERAL in self.target_domains:
            return True
        return domain in self.target_domains


class PerturbationEngine:
    """
    Applies perturbation functions to encoded scenarios.

    Pipeline Step 2: EncodedScenario × PerturbationFunction → PerturbedScenario

    The engine:
    1. Deep-copies the original scenario
    2. Applies the perturbation function's parameter deltas
    3. Adds optional noise (controlled)
    4. Validates against constraints
    5. Returns the perturbed scenario with full provenance metadata
    """

    def __init__(self, constraints: Optional[PerturbationConstraints] = None,
                 seed: int = 42):
        self.constraints = constraints or PerturbationConstraints()
        self._rng = __import__("numpy").random.RandomState(seed)

    def apply(self, scenario: EncodedScenario,
              perturbation: PerturbationFunction) -> EncodedScenario:
        """
        Apply a perturbation function to an encoded scenario.

        Formal operation: P(x, θ) → x'

        Args:
            scenario: Original ECS-encoded scenario (x)
            perturbation: The perturbation function with params θ

        Returns:
            Perturbed scenario (x') with provenance metadata
        """
        import numpy as np

        # Step 1: Deep copy (never mutate the original)
        perturbed = copy.deepcopy(scenario)
        perturbed.scenario_id = f"{scenario.scenario_id}__{perturbation.id}"
        perturbed.metadata["original_id"] = scenario.scenario_id
        perturbed.metadata["perturbation_id"] = perturbation.id
        perturbed.metadata["perturbation_type"] = perturbation.perturbation_type.value
        perturbed.metadata["perturbation_name"] = perturbation.name
        perturbed.metadata["perturbation_severity"] = perturbation.severity
        perturbed.metadata["is_perturbed"] = True

        params = perturbation.params

        # Step 2: Apply target variable deltas to each action
        for action in perturbed.actions:
            original_values = dict(action.vector.values)

            for var_name, delta in params.target_variables.items():
                if var_name in action.vector.values:
                    # Scale delta by magnitude
                    scaled_delta = delta * params.magnitude
                    new_val = action.vector.values[var_name] + scaled_delta
                    action.vector.values[var_name] = new_val

            # Step 3: Add controlled noise
            if params.noise_std > 0:
                for var_name in action.vector.values:
                    noise = self._rng.normal(0, params.noise_std)
                    action.vector.values[var_name] += noise

            # Step 4: Enforce constraints
            action.vector.values = self.constraints.clamp_values(action.vector.values)
            action.vector.values = self.constraints.enforce_budget(
                original_values, action.vector.values
            )

        # Handle special perturbation modes
        self._apply_special_modes(perturbed, perturbation)

        return perturbed

    def _apply_special_modes(self, scenario: EncodedScenario,
                              perturbation: PerturbationFunction):
        """Handle special perturbation operations beyond simple deltas."""
        import numpy as np
        extra = perturbation.params.extra

        # Information removal (ambiguity attacks)
        remove_keys = extra.get("remove_keys", [])
        for action in scenario.actions:
            for key in remove_keys:
                action.vector.values.pop(key, None)

        # Variable inversion (contradictory signals)
        n_invert = extra.get("invert_count", 0)
        if n_invert > 0:
            for action in scenario.actions:
                keys = list(action.vector.values.keys())
                if keys:
                    to_invert = self._rng.choice(
                        keys, min(n_invert, len(keys)), replace=False
                    )
                    for key in to_invert:
                        action.vector.values[key] = 1.0 - action.vector.values[key]

        # Action equalization (moral deadlock)
        if extra.get("equalize_actions") and len(scenario.actions) >= 2:
            first = scenario.actions[0].vector.values
            for action in scenario.actions[1:]:
                for key in action.vector.values:
                    if key in first:
                        avg = (action.vector.values[key] + first[key]) / 2
                        action.vector.values[key] = avg + self._rng.normal(0, 0.03)
                        action.vector.values[key] = max(0.0, min(1.0, action.vector.values[key]))

        # Bias injection (favor specific action)
        bias_target = extra.get("bias_target_action")
        if bias_target is not None and bias_target < len(scenario.actions):
            target = scenario.actions[bias_target]
            for key in ["benefit_score", "accountability_score"]:
                if key in target.vector.values:
                    target.vector.values[key] = min(1.0, target.vector.values[key] + 0.2)

        # Score swapping (principle conflict induction)
        swaps = extra.get("swap_variables", {})
        for action in scenario.actions:
            for k1, k2 in swaps.items():
                v = action.vector.values
                if k1 in v and k2 in v:
                    v[k1], v[k2] = v[k2], v[k1]

    def apply_batch(self, scenario: EncodedScenario,
                     perturbations: List[PerturbationFunction]) -> List[EncodedScenario]:
        """Apply multiple perturbations to one scenario."""
        return [self.apply(scenario, p) for p in perturbations]

    def generate_test_suite(self, scenarios: List[EncodedScenario],
                             perturbations: List[PerturbationFunction],
                             per_scenario: int = 5) -> List[EncodedScenario]:
        """
        Generate a full adversarial test suite.

        Selects diverse perturbations per scenario (one per type + extras).
        """
        import numpy as np
        all_perturbed = []

        for scenario in scenarios:
            # Select diverse set: one per perturbation type
            selected = []
            types_used = set()

            # Domain-relevant perturbations first
            relevant = [p for p in perturbations if p.applies_to_domain(scenario.domain)]
            for p in relevant:
                if p.perturbation_type not in types_used:
                    selected.append(p)
                    types_used.add(p.perturbation_type)
                if len(selected) >= per_scenario:
                    break

            # Fill remaining from all perturbations
            if len(selected) < per_scenario:
                remaining = [p for p in perturbations if p not in selected]
                for p in remaining:
                    if p.perturbation_type not in types_used:
                        selected.append(p)
                        types_used.add(p.perturbation_type)
                    if len(selected) >= per_scenario:
                        break

            for p in selected:
                all_perturbed.append(self.apply(scenario, p))

        return all_perturbed
