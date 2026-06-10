# ═══════════════════════════════════════════════════════════════════════
# Copyright (c) 2025 Pratyush Chaudhari. All rights reserved.
#
# This source code is part of the Ethical Robustness Testing System (ERTS).
# Research paper: https://zenodo.org/records/20544025
#
# LICENSE: This code is provided for academic study and personal
# learning ONLY. Commercial use, corporate deployment, or any use
# intended to generate revenue is strictly prohibited without
# explicit written permission from the author.
# ═══════════════════════════════════════════════════════════════════════

"""
ERTS — Test Real AI Models
============================
Run ERTS against real-world AI models and produce publication-ready results.

Usage:
    1. Set your Gemini API key:
       set GEMINI_API_KEY=your_key_here

    2. Run:
       python test_real_models.py
"""

import os
import sys
import json
import time

from core.pipeline import ERTSPipeline
from core.types import DeploymentDomain
from data.scenarios import get_demo_scenarios
from analysis.certification import DeploymentCertifier
from adapters.mock_models import (
    RuleBasedAdapter, LearningBasedAdapter,
    RLHFAdapter, VirtueEthicsAdapter
)


def test_gemini(pipeline, scenarios, certifier):
    """Test Google Gemini models."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n  [SKIP] GEMINI_API_KEY not set. Set it with:")
        print("    set GEMINI_API_KEY=your_key_here")
        return {}

    from adapters.llm_adapter import GeminiAdapter

    gemini_models = [
        ("gemini-2.0-flash", "Gemini-2.0-Flash"),
    ]

    reports = {}
    for model_id, label in gemini_models:
        print(f"\n  Testing {label}...")
        try:
            adapter = GeminiAdapter(
                api_key=api_key,
                model=model_id,
                model_label=label,
                delay=1.5  # Rate limit: 1.5s between calls
            )
            report = pipeline.run(adapter, scenarios)
            pipeline.print_report(report)

            # Certify
            for domain in [DeploymentDomain.HEALTHCARE, DeploymentDomain.HIRING, DeploymentDomain.GENERAL]:
                cert = certifier.certify(report, domain)
                certifier.print_certification(cert)

            reports[label] = report
            print(f"  {label}: ERS = {report.overall_robustness_score:.3f} | "
                  f"Failures = {report.total_failures}/{report.total_tests}")

        except Exception as e:
            print(f"  [ERROR] {label}: {e}")

    return reports


def test_ollama(pipeline, scenarios, certifier):
    """Test Ollama local models."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            available = [m["name"] for m in data.get("models", [])]
    except Exception:
        print("\n  [SKIP] Ollama not running. Start it with: ollama serve")
        return {}

    if not available:
        print("\n  [SKIP] No Ollama models found. Pull one with: ollama pull llama3.2")
        return {}

    from adapters.llm_adapter import OllamaAdapter

    print(f"\n  Ollama models available: {', '.join(available)}")

    reports = {}
    for model_name in available[:3]:  # Test up to 3 models
        label = f"Ollama-{model_name.split(':')[0]}"
        print(f"\n  Testing {label}...")
        try:
            adapter = OllamaAdapter(model=model_name, model_label=label)
            report = pipeline.run(adapter, scenarios)
            pipeline.print_report(report)

            for domain in [DeploymentDomain.HEALTHCARE, DeploymentDomain.HIRING, DeploymentDomain.GENERAL]:
                cert = certifier.certify(report, domain)
                certifier.print_certification(cert)

            reports[label] = report

        except Exception as e:
            print(f"  [ERROR] {label}: {e}")

    return reports


def test_mock_models(pipeline, scenarios, certifier):
    """Test our 4 built-in models (baseline)."""
    models = [
        RuleBasedAdapter(),
        LearningBasedAdapter(),
        RLHFAdapter(),
        VirtueEthicsAdapter(),
    ]

    reports = pipeline.run_multiple(models, scenarios)
    pipeline.print_comparison(reports)

    for model_name, report in reports.items():
        for domain in [DeploymentDomain.HEALTHCARE, DeploymentDomain.HIRING, DeploymentDomain.GENERAL]:
            cert = certifier.certify(report, domain)
            certifier.print_certification(cert)

    return reports


def save_results(all_reports, filename="results.json"):
    """Save all results to JSON for the research paper."""
    output = {}
    for name, report in all_reports.items():
        output[name] = {
            "ers": round(report.overall_robustness_score, 3),
            "ethical_consistency": round(report.ethical_consistency, 3),
            "manipulation_resistance": round(report.manipulation_resistance, 3),
            "fairness_preservation": round(report.fairness_preservation, 3),
            "harm_avoidance": round(report.harm_avoidance, 3),
            "confidence_stability": round(report.confidence_stability, 3),
            "total_tests": report.total_tests,
            "total_failures": report.total_failures,
            "failures_by_type": report.failures_by_type,
            "failures_by_severity": report.failures_by_severity,
            "resistance_by_perturbation": {
                k: round(v, 3) for k, v in report.resistance_by_perturbation.items()
            },
        }

    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {path}")
    return output


def main():
    print("=" * 70)
    print("  ERTS — Real-World AI Model Evaluation")
    print("=" * 70)

    scenarios = get_demo_scenarios()
    pipeline = ERTSPipeline(perturbations_per_scenario=5, seed=42)
    certifier = DeploymentCertifier()
    all_reports = {}

    # Phase 1: Mock models (baseline)
    print("\n" + "=" * 70)
    print("  PHASE 1: Baseline Models (Built-in)")
    print("=" * 70)
    mock_reports = test_mock_models(pipeline, scenarios, certifier)
    all_reports.update(mock_reports)

    # Phase 2: Gemini
    print("\n" + "=" * 70)
    print("  PHASE 2: Google Gemini")
    print("=" * 70)
    gemini_reports = test_gemini(pipeline, scenarios, certifier)
    all_reports.update(gemini_reports)

    # Phase 3: Ollama
    print("\n" + "=" * 70)
    print("  PHASE 3: Ollama Local Models")
    print("=" * 70)
    ollama_reports = test_ollama(pipeline, scenarios, certifier)
    all_reports.update(ollama_reports)

    # Save all results
    print("\n" + "=" * 70)
    print("  SAVING RESULTS")
    print("=" * 70)
    save_results(all_reports)

    # Final comparison
    if len(all_reports) > 1:
        print("\n" + "=" * 70)
        print("  FINAL COMPARISON — ALL MODELS")
        print("=" * 70)
        ranked = sorted(all_reports.items(), key=lambda x: -x[1].overall_robustness_score)
        print(f"\n  {'Rank':<6} {'Model':<25} {'ERS':<8} {'Consist':<10} "
              f"{'Fair':<8} {'Harm':<8} {'Failures':<10}")
        print(f"  {'-' * 75}")
        for i, (name, r) in enumerate(ranked):
            print(f"  #{i+1:<5} {name:<25} {r.overall_robustness_score:<8.3f} "
                  f"{r.ethical_consistency:<10.3f} {r.fairness_preservation:<8.3f} "
                  f"{r.harm_avoidance:<8.3f} {r.total_failures}/{r.total_tests}")

    print("\n  Done.")


if __name__ == "__main__":
    main()
