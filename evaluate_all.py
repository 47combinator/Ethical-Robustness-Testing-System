"""
Evaluate All Models (Mocks, Gemini, Ollama)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import ERTSPipeline
from adapters.mock_models import get_all_mock_models
from adapters.gemini_adapter import GeminiAdapter
from adapters.ollama_adapter import OllamaAdapter
from data.scenarios import get_demo_scenarios
from analysis.certification import DeploymentCertifier, CertificationLevel

def main():
    print("=" * 70)
    print("  ERTS -- Full Evaluation (Including Real LLMs)")
    print("=" * 70)

    scenarios = get_demo_scenarios()
    
    # 1. Load mock models
    models = get_all_mock_models()
    
    # 2. Load Gemini mock adapter
    models.append(GeminiAdapter())
    
    # 3. Load Ollama adapter (llama3.2:1b)
    # We'll just load one for now to keep the runtime reasonable, but this demonstrates the capability.
    models.append(OllamaAdapter(model_name="llama3.2:1b"))
    models.append(OllamaAdapter(model_name="mistral")) # Uncomment if mistral is pulled

    print(f"\n  Testing {len(models)} models: {[m.name for m in models]}")

    pipeline = ERTSPipeline(perturbations_per_scenario=5, seed=42)
    reports = pipeline.run_multiple(models, scenarios)

    pipeline.print_comparison(reports)

if __name__ == "__main__":
    main()
