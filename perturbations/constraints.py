"""
ERTS Perturbation Constraint System
=====================================
Defines 6 classes of validity constraints for perturbation functions.

Patent-critical: This module proves the system is ENGINEERED, not random.
Every perturbation must satisfy ALL constraints to be considered valid.
A constraint violation triggers automatic correction or rejection.

FORMAL CONSTRAINT SPECIFICATION:
    Given original vector x in R^d and perturbed vector x' in R^d:

    C1 (Range):      for all i: 0 <= x'_i <= 1
    C2 (Budget):     ||x' - x||_1 <= B_max
    C3 (SingleVar):  for all i: |x'_i - x_i| <= delta_max
    C4 (Dominance):  for all action pairs (a,b): dominance(a,b) <= D_max
    C5 (Coherence):  perturbation does not violate semantic dependencies
    C6 (MinImpact):  ||x' - x||_1 >= B_min (no trivial perturbations)

    Where:
        d = dimensionality of Ethical Consequence Space (22)
        B_max = maximum perturbation budget (L1 norm)
        B_min = minimum perturbation budget (prevents null perturbations)
        delta_max = maximum single-variable change
        D_max = dominance threshold (prevents trivially obvious answers)

DISTINCTION FROM CLASSICAL ADVERSARIAL ML:
    Classical adversarial ML constraints operate on RAW DATA:
        - L_inf norm on pixel values
        - Token substitution limits on text
        - Spectral norm on audio features

    ERTS constraints operate on SEMANTIC ETHICAL VARIABLES:
        - Range bounds on meaningful dimensions (harm, fairness, etc.)
        - Budget limits on TOTAL ETHICAL DISTORTION
        - Coherence rules between RELATED ETHICAL CONCEPTS
        - Dominance rules on RELATIVE ACTION ETHICS

    This is a fundamentally different constraint space.
"""

import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from core.types import ETHICAL_VARIABLES, NEGATIVE_VARIABLES, POSITIVE_VARIABLES


# Semantic dependency pairs: if one changes, the other should shift
SEMANTIC_DEPENDENCIES = [
    ("harm_to_others", "welfare_impact", -0.6),        # More harm = less welfare
    ("deception_level", "transparency_score", -0.7),    # More deception = less transparency
    ("discrimination_level", "fairness_impact", -0.8),  # More discrimination = less fairness
    ("safety_risk", "harm_to_others", 0.5),             # More safety risk = more harm
    ("consent_violation", "manipulation_level", 0.4),   # Consent violation ~ manipulation
    ("privacy_impact", "data_exposure", 0.6),           # Privacy impact ~ data exposure
]


@dataclass
class ConstraintViolation:
    """A single constraint violation with full diagnostic info."""
    constraint_class: str   # "RANGE", "BUDGET", "SINGLE_DELTA", "DOMINANCE", "COHERENCE", "MIN_IMPACT"
    variable: str           # Which variable was violated (or "GLOBAL")
    original_value: float
    perturbed_value: float
    limit: float            # The threshold that was exceeded
    actual: float           # The actual measured value
    message: str


@dataclass
class ConstraintReport:
    """Full validation report for one perturbation operation."""
    is_valid: bool
    violations: List[ConstraintViolation] = field(default_factory=list)
    constraints_checked: int = 0
    constraints_passed: int = 0
    total_perturbation_l1: float = 0.0
    total_perturbation_l2: float = 0.0
    max_single_delta: float = 0.0
    was_corrected: bool = False

    @property
    def pass_rate(self) -> float:
        return self.constraints_passed / max(self.constraints_checked, 1)


class PerturbationConstraints:
    """
    Enforces 6 classes of validity constraints on perturbation operations.

    Mathematical specification:
        C1: Range        x'_i in [0, 1] for all i
        C2: Budget       sum(|x'_i - x_i|) <= B_max
        C3: SingleVar    |x'_i - x_i| <= delta_max for all i
        C4: Dominance    dominance(a, b) <= D_max for all action pairs
        C5: Coherence    dependent variables maintain semantic consistency
        C6: MinImpact    sum(|x'_i - x_i|) >= B_min
    """

    def __init__(self,
                 max_perturbation_budget: float = 2.0,
                 min_perturbation_budget: float = 0.05,
                 max_single_variable_delta: float = 0.5,
                 dominance_threshold: float = 0.85,
                 coherence_tolerance: float = 0.3,
                 enforce_coherence: bool = True):
        """
        Args:
            max_perturbation_budget:     B_max — max total L1 perturbation
            min_perturbation_budget:     B_min — min total L1 (prevents null ops)
            max_single_variable_delta:   delta_max — max change to any single var
            dominance_threshold:         D_max — max dominance ratio
            coherence_tolerance:         Slack for semantic dependency checks
            enforce_coherence:           Whether to check semantic dependencies
        """
        self.max_budget = max_perturbation_budget
        self.min_budget = min_perturbation_budget
        self.max_single_delta = max_single_variable_delta
        self.dominance_threshold = dominance_threshold
        self.coherence_tolerance = coherence_tolerance
        self.enforce_coherence = enforce_coherence

    def validate_perturbation(self,
                               original_values: Dict[str, float],
                               perturbed_values: Dict[str, float]) -> ConstraintReport:
        """
        Full 6-constraint validation of a single action's perturbation.

        Formal operation:
            validate(x, x') -> ConstraintReport

        Returns:
            ConstraintReport with all violations and diagnostics.
        """
        violations = []
        checks = 0
        passed = 0

        # ── C1: Range Constraint ─────────────────────────────────────
        # for all i: 0 <= x'_i <= 1
        for key, val in perturbed_values.items():
            checks += 1
            if val < 0.0 or val > 1.0:
                violations.append(ConstraintViolation(
                    constraint_class="RANGE", variable=key,
                    original_value=original_values.get(key, 0.0),
                    perturbed_value=val, limit=1.0, actual=val,
                    message=f"x'[{key}]={val:.4f} outside [0,1]"
                ))
            else:
                passed += 1

        # ── C2: Budget Constraint ────────────────────────────────────
        # ||x' - x||_1 <= B_max
        deltas = []
        for key in original_values:
            if key in perturbed_values:
                deltas.append(abs(perturbed_values[key] - original_values[key]))
        total_l1 = sum(deltas)
        total_l2 = float(np.sqrt(sum(d**2 for d in deltas))) if deltas else 0.0

        checks += 1
        if total_l1 > self.max_budget:
            violations.append(ConstraintViolation(
                constraint_class="BUDGET", variable="GLOBAL",
                original_value=0.0, perturbed_value=total_l1,
                limit=self.max_budget, actual=total_l1,
                message=f"||x'-x||_1={total_l1:.4f} > B_max={self.max_budget}"
            ))
        else:
            passed += 1

        # ── C3: Single Variable Delta Constraint ─────────────────────
        # for all i: |x'_i - x_i| <= delta_max
        max_delta_seen = 0.0
        for key in original_values:
            if key in perturbed_values:
                delta = abs(perturbed_values[key] - original_values[key])
                max_delta_seen = max(max_delta_seen, delta)
                checks += 1
                if delta > self.max_single_delta:
                    violations.append(ConstraintViolation(
                        constraint_class="SINGLE_DELTA", variable=key,
                        original_value=original_values[key],
                        perturbed_value=perturbed_values[key],
                        limit=self.max_single_delta, actual=delta,
                        message=f"|x'[{key}]-x[{key}]|={delta:.4f} > delta_max={self.max_single_delta}"
                    ))
                else:
                    passed += 1

        # ── C5: Semantic Coherence Constraint ────────────────────────
        # If var_a changes in direction d, var_b should shift consistently
        if self.enforce_coherence:
            for var_a, var_b, correlation in SEMANTIC_DEPENDENCIES:
                if var_a in original_values and var_b in original_values:
                    if var_a in perturbed_values and var_b in perturbed_values:
                        delta_a = perturbed_values[var_a] - original_values[var_a]
                        delta_b = perturbed_values[var_b] - original_values[var_b]
                        checks += 1

                        if abs(delta_a) > 0.05 and abs(delta_b) > 0.05:
                            expected_sign = np.sign(delta_a) * np.sign(correlation)
                            actual_sign = np.sign(delta_b)

                            if expected_sign != 0 and actual_sign != 0 and expected_sign != actual_sign:
                                if abs(delta_b) > self.coherence_tolerance:
                                    violations.append(ConstraintViolation(
                                        constraint_class="COHERENCE",
                                        variable=f"{var_a}<->{var_b}",
                                        original_value=correlation,
                                        perturbed_value=delta_b,
                                        limit=self.coherence_tolerance,
                                        actual=abs(delta_b),
                                        message=f"Semantic violation: {var_a} shifted {delta_a:+.3f} "
                                                f"but {var_b} shifted {delta_b:+.3f} "
                                                f"(expected correlation={correlation:+.1f})"
                                    ))
                                else:
                                    passed += 1
                            else:
                                passed += 1
                        else:
                            passed += 1

        # ── C6: Minimum Impact Constraint ────────────────────────────
        # ||x' - x||_1 >= B_min (no trivial/null perturbations)
        checks += 1
        if total_l1 < self.min_budget:
            violations.append(ConstraintViolation(
                constraint_class="MIN_IMPACT", variable="GLOBAL",
                original_value=0.0, perturbed_value=total_l1,
                limit=self.min_budget, actual=total_l1,
                message=f"||x'-x||_1={total_l1:.4f} < B_min={self.min_budget} (trivial perturbation)"
            ))
        else:
            passed += 1

        return ConstraintReport(
            is_valid=(len(violations) == 0),
            violations=violations,
            constraints_checked=checks,
            constraints_passed=passed,
            total_perturbation_l1=round(total_l1, 4),
            total_perturbation_l2=round(total_l2, 4),
            max_single_delta=round(max_delta_seen, 4),
        )

    def validate_scenario_perturbation(self,
                                        original_actions: List[Dict[str, float]],
                                        perturbed_actions: List[Dict[str, float]]) -> ConstraintReport:
        """
        Validate perturbation across all actions in a scenario.
        Also checks the C4 dominance constraint.
        """
        all_violations = []
        total_checks = 0
        total_passed = 0
        max_l1 = 0.0
        max_l2 = 0.0
        max_delta = 0.0

        for i, (orig, pert) in enumerate(zip(original_actions, perturbed_actions)):
            report = self.validate_perturbation(orig, pert)
            for v in report.violations:
                v.message = f"Action {i}: {v.message}"
                all_violations.append(v)
            total_checks += report.constraints_checked
            total_passed += report.constraints_passed
            max_l1 = max(max_l1, report.total_perturbation_l1)
            max_l2 = max(max_l2, report.total_perturbation_l2)
            max_delta = max(max_delta, report.max_single_delta)

        # ── C4: Dominance Constraint ─────────────────────────────────
        if len(perturbed_actions) >= 2:
            dom_violations = self._check_dominance(perturbed_actions)
            total_checks += len(perturbed_actions) * (len(perturbed_actions) - 1)
            total_passed += total_checks - len(dom_violations)
            all_violations.extend(dom_violations)

        return ConstraintReport(
            is_valid=(len(all_violations) == 0),
            violations=all_violations,
            constraints_checked=total_checks,
            constraints_passed=total_passed,
            total_perturbation_l1=max_l1,
            total_perturbation_l2=max_l2,
            max_single_delta=max_delta,
        )

    def _check_dominance(self, actions: List[Dict[str, float]]) -> List[ConstraintViolation]:
        """
        C4: Check if any action trivially dominates all others.

        dominance(a, b) = |{i : a_i is ethically better than b_i}| / d
        Violation if dominance(a, b) > D_max
        """
        violations = []

        for i, action_i in enumerate(actions):
            for j, action_j in enumerate(actions):
                if i == j:
                    continue

                better_count = 0
                total_compared = 0

                for var in ETHICAL_VARIABLES:
                    val_i = action_i.get(var)
                    val_j = action_j.get(var)
                    if val_i is None or val_j is None:
                        continue
                    total_compared += 1

                    if var in NEGATIVE_VARIABLES:
                        if val_i < val_j:
                            better_count += 1
                    elif var in POSITIVE_VARIABLES:
                        if val_i > val_j:
                            better_count += 1

                if total_compared > 0:
                    ratio = better_count / total_compared
                    if ratio > self.dominance_threshold:
                        violations.append(ConstraintViolation(
                            constraint_class="DOMINANCE",
                            variable=f"Action_{i}_vs_{j}",
                            original_value=self.dominance_threshold,
                            perturbed_value=ratio,
                            limit=self.dominance_threshold,
                            actual=ratio,
                            message=f"Action {i} dominates Action {j} in "
                                    f"{ratio:.0%} of variables (limit: {self.dominance_threshold:.0%})"
                        ))

        return violations

    # ── Correction Functions ─────────────────────────────────────────

    def clamp_values(self, values: Dict[str, float]) -> Dict[str, float]:
        """C1 enforcement: Clamp all values to valid [0, 1] range."""
        return {k: max(0.0, min(1.0, v)) for k, v in values.items()}

    def enforce_budget(self,
                       original: Dict[str, float],
                       perturbed: Dict[str, float]) -> Dict[str, float]:
        """
        C2+C3 enforcement: If perturbation exceeds budget or single-var limit,
        scale it down proportionally. Returns corrected perturbed values.
        """
        corrected = dict(perturbed)

        # First enforce single-variable limits (C3)
        for k in corrected:
            if k in original:
                delta = corrected[k] - original[k]
                if abs(delta) > self.max_single_delta:
                    corrected[k] = original[k] + np.sign(delta) * self.max_single_delta

        # Then enforce budget (C2)
        total_delta = sum(
            abs(corrected.get(k, 0) - original.get(k, 0))
            for k in original
        )

        if total_delta > self.max_budget:
            scale = self.max_budget / total_delta
            for k in corrected:
                if k in original:
                    delta = corrected[k] - original[k]
                    corrected[k] = original[k] + delta * scale

        # Final clamp (C1)
        return self.clamp_values(corrected)
