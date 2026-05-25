"""
ERTS -- Ethical Robustness Testing System
=========================================
Main entry point. Runs the full 5-step pipeline + deployment certification.

Usage:
    python main.py
"""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import ERTSPipeline
from core.types import DeploymentDomain
from adapters.mock_models import get_all_mock_models
from data.scenarios import get_demo_scenarios
from perturbations.registry import PerturbationRegistry
from analysis.certification import DeploymentCertifier, CertificationLevel


def main():
    print("=" * 70)
    print("  ERTS -- Ethical Robustness Testing System v2.0")
    print("  A system for adversarial evaluation of ethical AI models")
    print("  using domain-specific semantic perturbation functions")
    print("=" * 70)

    # Load demo scenarios
    scenarios = get_demo_scenarios()
    print(f"\n  Loaded {len(scenarios)} ethical scenarios")

    # Show perturbation registry
    registry = PerturbationRegistry()
    print(f"  Registered {len(registry)} perturbation functions:")
    for ptype, count in registry.get_type_counts().items():
        print(f"    {ptype}: {count}")

    # Load mock models
    models = get_all_mock_models()
    print(f"\n  Testing {len(models)} models: {[m.name for m in models]}")

    # ── PHASE 1: Run Pipeline ────────────────────────────────────────
    print("\n" + "-" * 70)
    print("  PHASE 1: Robustness Evaluation Pipeline")
    print("-" * 70)

    pipeline = ERTSPipeline(perturbations_per_scenario=5, seed=42)
    reports = pipeline.run_multiple(models, scenarios)

    for name, report in sorted(reports.items(), key=lambda x: x[1].rank):
        pipeline.print_report(report)

    pipeline.print_comparison(reports)

    # ── PHASE 2: Deployment Certification ────────────────────────────
    print("\n" + "-" * 70)
    print("  PHASE 2: Deployment Certification")
    print("-" * 70)

    certifier = DeploymentCertifier()

    # Test each model against healthcare (strict) and general (baseline)
    cert_domains = [DeploymentDomain.HEALTHCARE, DeploymentDomain.HIRING,
                    DeploymentDomain.GENERAL]

    for model_name, report in sorted(reports.items(), key=lambda x: x[1].rank):
        for domain in cert_domains:
            cert = certifier.certify(report, domain)
            certifier.print_certification(cert)

    # ── PHASE 3: Summary ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  CERTIFICATION SUMMARY")
    print("=" * 70)
    print(f"  {'Model':<20s} {'Healthcare':>12s} {'Hiring':>10s} {'General':>10s}")
    print(f"  {'-'*54}")

    for model_name, report in sorted(reports.items(), key=lambda x: x[1].rank):
        row = f"  {model_name:<20s}"
        for domain in cert_domains:
            cert = certifier.certify(report, domain)
            symbols = {
                CertificationLevel.CERTIFIED: "PASS",
                CertificationLevel.CONDITIONAL: "COND",
                CertificationLevel.FAILED: "FAIL",
                CertificationLevel.NOT_EVALUATED: "N/A",
            }
            width = 12 if domain == DeploymentDomain.HEALTHCARE else 10
            row += f" {symbols[cert.certification_level]:>{width}s}"
        print(row)

    print(f"  {'-'*54}")
    print(f"  PASS = Certified  |  COND = Conditional  |  FAIL = Not safe")
    print(f"{'='*70}\n")

    # Pipeline run log
    print("  Pipeline Run Log:")
    for entry in pipeline.get_run_log():
        print(f"    {entry['model']:20s} | {entry['scenarios']} scenarios | "
              f"{entry['perturbations']} perturbations | "
              f"ERS={entry['ers']:.3f} | {entry['elapsed_seconds']}s")

    print("\n  Done.")


if __name__ == "__main__":
    main()
