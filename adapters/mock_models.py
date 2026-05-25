"""
ERTS Mock Ethical Models
=========================
Self-contained mock models for demonstration and testing.
These simulate 4 different ethical reasoning approaches.

These are STANDALONE — they do NOT depend on Model 1's codebase.
"""

import numpy as np
from typing import Dict, List
from core.types import DecisionResult, NEGATIVE_VARIABLES, POSITIVE_VARIABLES
from core.scenario import EncodedScenario
from adapters.base import ModelAdapter


class RuleBasedAdapter(ModelAdapter):
    """
    Mock rule-based ethical model.
    Scores actions by weighted sum of ethical variables,
    with negative variables inverted (lower harm = higher score).
    """

    @property
    def name(self) -> str:
        return "RuleBased"

    def evaluate(self, scenario: EncodedScenario) -> DecisionResult:
        scores = {}
        for action in scenario.actions:
            score = 0.0
            count = 0
            for var, val in action.vector.values.items():
                if var in NEGATIVE_VARIABLES:
                    score += (1.0 - val)  # Invert: lower harm = higher score
                elif var in POSITIVE_VARIABLES:
                    score += val
                count += 1
            scores[action.action_id] = score / max(count, 1)

        best_id = max(scores, key=scores.get)
        sorted_s = sorted(scores.values(), reverse=True)
        gap = sorted_s[0] - sorted_s[1] if len(sorted_s) > 1 else 0.5
        confidence = min(1.0, max(0.1, gap * 3 + 0.3))

        best_action = scenario.get_action(best_id)
        return DecisionResult(
            scenario_id=scenario.scenario_id,
            chosen_action_id=best_id,
            chosen_action_desc=best_action.description if best_action else "",
            confidence=round(confidence, 4),
            action_scores=scores,
        )


class LearningBasedAdapter(ModelAdapter):
    """
    Mock learning-based model.
    Uses a simple weighted scoring with learned-like weights
    that emphasize harm and fairness (empirical pattern).
    """
    LEARNED_WEIGHTS = {
        "harm_to_others": -1.5,
        "harm_to_self": -0.5,
        "fairness_impact": 1.2,
        "benefit_score": 1.0,
        "welfare_impact": 0.8,
        "safety_risk": -1.0,
        "accountability_score": 0.6,
        "discrimination_level": -1.3,
        "deception_level": -0.7,
        "transparency_score": 0.5,
    }

    @property
    def name(self) -> str:
        return "LearningBased"

    def evaluate(self, scenario: EncodedScenario) -> DecisionResult:
        scores = {}
        for action in scenario.actions:
            score = 0.0
            for var, weight in self.LEARNED_WEIGHTS.items():
                val = action.vector.get(var, 0.5)
                score += val * weight
            scores[action.action_id] = score

        # Normalize to 0-1
        min_s = min(scores.values())
        max_s = max(scores.values())
        rng = max_s - min_s if max_s != min_s else 1.0
        scores = {k: (v - min_s) / rng for k, v in scores.items()}

        best_id = max(scores, key=scores.get)
        sorted_s = sorted(scores.values(), reverse=True)
        gap = sorted_s[0] - sorted_s[1] if len(sorted_s) > 1 else 0.5
        confidence = min(1.0, max(0.1, gap * 2 + 0.3))

        best_action = scenario.get_action(best_id)
        return DecisionResult(
            scenario_id=scenario.scenario_id,
            chosen_action_id=best_id,
            chosen_action_desc=best_action.description if best_action else "",
            confidence=round(confidence, 4),
            action_scores=scores,
        )


class RLHFAdapter(ModelAdapter):
    """
    Mock RLHF model.
    Simulates reward-optimizing behavior with slight sycophancy tendency
    (over-weights benefit/accountability, under-weights harm).
    """

    @property
    def name(self) -> str:
        return "RLHF"

    def evaluate(self, scenario: EncodedScenario) -> DecisionResult:
        scores = {}
        for action in scenario.actions:
            v = action.vector.values
            # RLHF tends to over-optimize for "looks good" variables
            reward = (
                v.get("benefit_score", 0.5) * 1.8
                + v.get("welfare_impact", 0.5) * 1.4
                + v.get("accountability_score", 0.5) * 1.2
                - v.get("harm_to_others", 0.5) * 1.0
                - v.get("safety_risk", 0.5) * 0.8
                - v.get("deception_level", 0.5) * 0.6
            )
            scores[action.action_id] = reward

        min_s = min(scores.values())
        max_s = max(scores.values())
        rng = max_s - min_s if max_s != min_s else 1.0
        scores = {k: (v - min_s) / rng for k, v in scores.items()}

        best_id = max(scores, key=scores.get)
        sorted_s = sorted(scores.values(), reverse=True)
        gap = sorted_s[0] - sorted_s[1] if len(sorted_s) > 1 else 0.5
        confidence = min(1.0, max(0.1, gap * 1.5 + 0.3))

        best_action = scenario.get_action(best_id)
        return DecisionResult(
            scenario_id=scenario.scenario_id,
            chosen_action_id=best_id,
            chosen_action_desc=best_action.description if best_action else "",
            confidence=round(confidence, 4),
            action_scores=scores,
        )


class VirtueEthicsAdapter(ModelAdapter):
    """
    Mock virtue ethics model.
    Scores actions against 8 Aristotelian virtues with context-adaptive weights.
    """
    VIRTUES = {
        "compassion":    {"keys": ["harm_to_others", "welfare_impact", "collateral_damage"], "direction": "negative", "weight": 0.85},
        "justice":       {"keys": ["fairness_impact", "discrimination_level"], "direction": "mixed", "weight": 0.80},
        "honesty":       {"keys": ["deception_level", "transparency_score"], "direction": "mixed", "weight": 0.75},
        "responsibility":{"keys": ["accountability_score", "welfare_impact"], "direction": "positive", "weight": 0.80},
        "courage":       {"keys": ["harm_to_self", "safety_risk"], "direction": "negative", "weight": 0.60},
        "prudence":      {"keys": ["safety_risk", "proportionality_score"], "direction": "mixed", "weight": 0.70},
        "temperance":    {"keys": ["restrictiveness", "proportionality_score"], "direction": "mixed", "weight": 0.55},
        "benevolence":   {"keys": ["benefit_score", "welfare_impact"], "direction": "positive", "weight": 0.75},
    }

    @property
    def name(self) -> str:
        return "VirtueEthics"

    def evaluate(self, scenario: EncodedScenario) -> DecisionResult:
        scores = {}
        for action in scenario.actions:
            v = action.vector.values
            total = 0.0
            for virtue_name, virtue in self.VIRTUES.items():
                virtue_score = 0.0
                for key in virtue["keys"]:
                    val = v.get(key, 0.5)
                    if virtue["direction"] == "negative":
                        virtue_score += (1.0 - val)
                    elif virtue["direction"] == "positive":
                        virtue_score += val
                    else:  # mixed
                        if key in NEGATIVE_VARIABLES:
                            virtue_score += (1.0 - val)
                        else:
                            virtue_score += val
                virtue_score /= max(len(virtue["keys"]), 1)
                total += virtue_score * virtue["weight"]
            scores[action.action_id] = total

        min_s = min(scores.values())
        max_s = max(scores.values())
        rng = max_s - min_s if max_s != min_s else 1.0
        scores = {k: round((v - min_s) / rng, 4) for k, v in scores.items()}

        best_id = max(scores, key=scores.get)
        sorted_s = sorted(scores.values(), reverse=True)
        gap = sorted_s[0] - sorted_s[1] if len(sorted_s) > 1 else 0.5
        confidence = min(1.0, max(0.1, gap * 3 + 0.3))

        best_action = scenario.get_action(best_id)
        return DecisionResult(
            scenario_id=scenario.scenario_id,
            chosen_action_id=best_id,
            chosen_action_desc=best_action.description if best_action else "",
            confidence=round(confidence, 4),
            action_scores=scores,
        )


def get_all_mock_models() -> List[ModelAdapter]:
    """Get all 4 mock models for testing."""
    return [
        RuleBasedAdapter(),
        LearningBasedAdapter(),
        RLHFAdapter(),
        VirtueEthicsAdapter(),
    ]
