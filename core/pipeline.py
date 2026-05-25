"""
ERTS Pipeline Orchestrator
============================
The complete 5-step closed pipeline.

This is the CORE INVENTION:

  Input: Ethical Scenario + Target Model
    → Step 1: Encode into Ethical Consequence Space
    → Step 2: Apply Perturbation Functions
    → Step 3: Evaluate with Target Model (normal + perturbed)
    → Step 4: Compute Decision Deviation
    → Step 5: Classify Robustness
  Output: Ethical Robustness Score

Patent framing: This pipeline is a MACHINE PROCESS, not an idea.
It takes structured input, applies defined transformations, produces
measurable output. Every step is deterministic and reproducible.
"""

import time
from typing import Dict, List, Optional
from core.types import PerturbationType, DeviationReport, RobustnessReport
from core.scenario import ScenarioEncoder, EncodedScenario
from perturbations.base import PerturbationEngine, PerturbationFunction
from perturbations.registry import PerturbationRegistry
from perturbations.constraints import PerturbationConstraints
from adapters.base import ModelAdapter
from analysis.deviation import DeviationAnalyzer
from analysis.robustness import RobustnessClassifier


class ERTSPipeline:
    """
    The Ethical Robustness Testing System Pipeline.

    A closed, 5-step process for evaluating the ethical robustness
    of any AI decision-making model.

    Usage:
        pipeline = ERTSPipeline()
        report = pipeline.run(model, scenarios)
    """

    def __init__(self,
                 perturbations_per_scenario: int = 5,
                 seed: int = 42,
                 max_perturbation_budget: float = 2.0,
                 max_single_delta: float = 0.5):
        """
        Initialize the pipeline with configuration.

        Args:
            perturbations_per_scenario: How many perturbations to apply per scenario
            seed: Random seed for reproducibility
            max_perturbation_budget: Max total L1 perturbation per action
            max_single_delta: Max change to any single ethical variable
        """
        # Step 1: Encoder
        self.encoder = ScenarioEncoder()

        # Step 2: Perturbation engine with constraints
        self.constraints = PerturbationConstraints(
            max_perturbation_budget=max_perturbation_budget,
            max_single_variable_delta=max_single_delta,
        )
        self.perturbation_engine = PerturbationEngine(
            constraints=self.constraints, seed=seed
        )
        self.registry = PerturbationRegistry()

        # Step 4-5: Analysis
        self.deviation_analyzer = DeviationAnalyzer()
        self.robustness_classifier = RobustnessClassifier()

        self.perturbations_per_scenario = perturbations_per_scenario
        self._run_log: List[Dict] = []

    def run(self, model: ModelAdapter,
            scenarios: List[Dict],
            perturbation_ids: Optional[List[str]] = None) -> RobustnessReport:
        """
        Execute the full 5-step pipeline on one model.

        Args:
            model: The ethical AI model to test (via ModelAdapter interface)
            scenarios: Raw scenario dictionaries
            perturbation_ids: Optional specific perturbation IDs to use.
                              If None, uses diverse automatic selection.

        Returns:
            RobustnessReport with the Ethical Robustness Score
        """
        start_time = time.time()

        # ── STEP 1: Encode ──────────────────────────────────────────
        encoded = self.encoder.encode_batch(scenarios)

        # Select perturbation functions
        if perturbation_ids:
            perturbations = [self.registry.get(pid) for pid in perturbation_ids
                              if self.registry.get(pid)]
        else:
            perturbations = self.registry.get_all()

        # ── STEP 2: Generate perturbed scenarios ────────────────────
        perturbed_scenarios = self.perturbation_engine.generate_test_suite(
            encoded, perturbations, per_scenario=self.perturbations_per_scenario
        )

        # ── STEP 3: Evaluate with target model ──────────────────────
        # 3a: Normal evaluation
        normal_results = {}
        for enc_scenario in encoded:
            result = model.evaluate(enc_scenario)
            normal_results[enc_scenario.scenario_id] = result

        # 3b: Perturbed evaluation
        perturbed_results = []
        for pert_scenario in perturbed_scenarios:
            result = model.evaluate(pert_scenario)
            perturbed_results.append({
                "result": result,
                "original_id": pert_scenario.metadata.get("original_id", ""),
                "perturbation_id": pert_scenario.metadata.get("perturbation_id", ""),
                "perturbation_type": pert_scenario.metadata.get("perturbation_type", ""),
                "perturbation_severity": pert_scenario.metadata.get("perturbation_severity", 0),
            })

        # ── STEP 4: Compute deviations ──────────────────────────────
        deviation_reports = []
        for pert_data in perturbed_results:
            original_id = pert_data["original_id"]
            normal = normal_results.get(original_id)
            if not normal:
                continue

            ptype_str = pert_data["perturbation_type"]
            try:
                ptype = PerturbationType(ptype_str)
            except ValueError:
                ptype = PerturbationType.CONSEQUENCE_REFRAMING

            report = self.deviation_analyzer.analyze(
                normal=normal,
                perturbed=pert_data["result"],
                perturbation_type=ptype,
                perturbation_severity=pert_data["perturbation_severity"],
                perturbation_id=pert_data["perturbation_id"],
            )
            deviation_reports.append(report)

        # ── STEP 5: Classify robustness ─────────────────────────────
        robustness = self.robustness_classifier.classify(
            model.name, deviation_reports
        )

        elapsed = time.time() - start_time

        # Log the run
        self._run_log.append({
            "model": model.name,
            "scenarios": len(scenarios),
            "perturbations": len(perturbed_scenarios),
            "deviations": len(deviation_reports),
            "failures": robustness.total_failures,
            "ers": robustness.overall_robustness_score,
            "elapsed_seconds": round(elapsed, 2),
        })

        return robustness

    def run_multiple(self, models: List[ModelAdapter],
                     scenarios: List[Dict]) -> Dict[str, RobustnessReport]:
        """
        Run the pipeline on multiple models for comparison.

        Returns:
            Dict mapping model name → RobustnessReport, with rankings.
        """
        reports = {}
        for model in models:
            reports[model.name] = self.run(model, scenarios)

        # Assign rankings
        ranked = sorted(reports.items(),
                         key=lambda x: -x[1].overall_robustness_score)
        for i, (name, _) in enumerate(ranked):
            reports[name].rank = i + 1

        return reports

    def get_run_log(self) -> List[Dict]:
        """Return log of all pipeline executions."""
        return list(self._run_log)

    def print_report(self, report: RobustnessReport):
        """Pretty-print a robustness report."""
        print(f"\n{'='*60}")
        print(f"  ETHICAL ROBUSTNESS REPORT: {report.model_name}")
        print(f"{'='*60}")
        print(f"  Overall ERS: {report.overall_robustness_score:.3f}")
        print(f"  Rank: #{report.rank}")
        print(f"  Interpretation: {report.interpretation}")
        print(f"\n  Sub-Metrics:")
        print(f"    Ethical Consistency:     {report.ethical_consistency:.3f}")
        print(f"    Manipulation Resistance: {report.manipulation_resistance:.3f}")
        print(f"    Fairness Preservation:   {report.fairness_preservation:.3f}")
        print(f"    Harm Avoidance:          {report.harm_avoidance:.3f}")
        print(f"    Confidence Stability:    {report.confidence_stability:.3f}")
        print(f"\n  Tests: {report.total_tests} | Failures: {report.total_failures}")
        if report.failures_by_type:
            print(f"  Failure Types: {report.failures_by_type}")
        if report.resistance_by_perturbation:
            print(f"\n  Resistance by Perturbation Type:")
            for ptype, resist in sorted(report.resistance_by_perturbation.items()):
                bar = "#" * int(resist * 20) + "-" * (20 - int(resist * 20))
                print(f"    {ptype:40s} {bar} {resist:.0%}")
        print(f"{'='*60}\n")

    def print_comparison(self, reports: Dict[str, RobustnessReport]):
        """Pretty-print a multi-model comparison."""
        print(f"\n{'='*70}")
        print(f"  ERTS — MULTI-MODEL ROBUSTNESS COMPARISON")
        print(f"{'='*70}")
        print(f"  {'Model':<20s} {'ERS':>6s} {'Consist':>8s} {'Resist':>8s} "
              f"{'Fair':>6s} {'Harm':>6s} {'Rank':>5s}")
        print(f"  {'-'*60}")

        for name, r in sorted(reports.items(),
                                key=lambda x: -x[1].overall_robustness_score):
            print(f"  {name:<20s} {r.overall_robustness_score:>6.3f} "
                  f"{r.ethical_consistency:>8.3f} {r.manipulation_resistance:>8.3f} "
                  f"{r.fairness_preservation:>6.3f} {r.harm_avoidance:>6.3f} "
                  f"{'#'+str(r.rank):>5s}")

        print(f"{'='*70}\n")
