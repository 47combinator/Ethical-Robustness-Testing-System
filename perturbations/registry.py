"""
ERTS Perturbation Registry
===========================
Central registry for discovering and managing perturbation functions.
"""

from typing import Dict, List, Optional
from core.types import PerturbationType, DeploymentDomain
from perturbations.base import PerturbationFunction
from perturbations.semantic import ALL_PERTURBATION_FUNCTIONS


class PerturbationRegistry:
    """Central registry for all perturbation functions."""

    def __init__(self):
        self._functions: Dict[str, PerturbationFunction] = {
            pf.id: pf for pf in ALL_PERTURBATION_FUNCTIONS
        }

    def get(self, pf_id: str) -> Optional[PerturbationFunction]:
        return self._functions.get(pf_id)

    def get_all(self) -> List[PerturbationFunction]:
        return list(self._functions.values())

    def get_by_type(self, ptype: PerturbationType) -> List[PerturbationFunction]:
        return [pf for pf in self._functions.values()
                if pf.perturbation_type == ptype]

    def get_for_domain(self, domain: DeploymentDomain) -> List[PerturbationFunction]:
        return [pf for pf in self._functions.values()
                if pf.applies_to_domain(domain)]

    def get_type_counts(self) -> Dict[str, int]:
        counts = {}
        for pf in self._functions.values():
            t = pf.perturbation_type.value
            counts[t] = counts.get(t, 0) + 1
        return counts

    def __len__(self):
        return len(self._functions)

    def summary(self) -> str:
        lines = [f"ERTS Perturbation Registry: {len(self)} functions"]
        for ptype in PerturbationType:
            funcs = self.get_by_type(ptype)
            lines.append(f"  {ptype.value}: {len(funcs)} functions")
            for f in funcs:
                lines.append(f"    [{f.id}] {f.name} (severity={f.severity})")
        return "\n".join(lines)
