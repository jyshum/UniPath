"""
Ablation eval runner. Tests 3 configurations on ground truth data:
  A: llama3.2:3b + free-form
  B: llama3.2:3b + structured output
  C: qwen3:4b + structured output

Usage: python3 -m eval.runner
"""
import json
import time
import ollama
from pathlib import Path
from eval.schemas import AdmissionExtraction
from eval.metrics import field_accuracy, relevance_accuracy, FIELDS
from pipeline.reddit_agent import EXTRACTION_PROMPT

GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"

CONFIGS = {
    "A_llama_freeform": {"model": "llama3.2", "structured": False},
    "B_llama_structured": {"model": "llama3.2", "structured": True},
    "C_qwen3_structured": {"model": "qwen3:4b", "structured": True},
}


def extract_freeform(model: str, post_text: str) -> AdmissionExtraction | None:
    """Extract using free-form JSON (current approach)."""
    prompt = EXTRACTION_PROMPT.format(post_text=post_text[:2000])
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
        )
        raw = response["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        data = json.loads(raw)
        return AdmissionExtraction(**data)
    except Exception:
        return None


def extract_structured(model: str, post_text: str) -> AdmissionExtraction | None:
    """Extract using Ollama structured output mode."""
    prompt = EXTRACTION_PROMPT.format(post_text=post_text[:2000])
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=AdmissionExtraction.model_json_schema(),
            options={"temperature": 0},
        )
        raw = response["message"]["content"].strip()
        return AdmissionExtraction.model_validate_json(raw)
    except Exception as e:
        print(f"  Extraction error: {e}")
        return None


def run_config(name: str, config: dict, records: list[dict]) -> dict:
    """Run a single config against all records, return aggregated metrics."""
    extract_fn = extract_structured if config["structured"] else extract_freeform
    model = config["model"]

    total = len(records)
    json_valid = 0
    relevance_correct = 0
    field_correct = {f: 0 for f in FIELDS}
    field_total = {f: 0 for f in FIELDS}
    latencies = []

    predictions = []

    for i, record in enumerate(records):
        post_text = record["post_text"]
        truth = AdmissionExtraction(**record["expected"])

        start = time.time()
        predicted = extract_fn(model, post_text)
        elapsed = time.time() - start
        latencies.append(elapsed)

        if predicted is None:
            predictions.append({"index": i, "predicted": None, "valid": False})
            continue

        json_valid += 1
        predictions.append({
            "index": i,
            "predicted": predicted.model_dump(),
            "valid": True,
        })

        if relevance_accuracy(predicted, truth):
            relevance_correct += 1

        if truth.relevant and predicted.relevant:
            acc = field_accuracy(predicted, truth)
            for field, correct in acc.items():
                field_total[field] += 1
                if correct:
                    field_correct[field] += 1

        print(f"  [{name}] {i+1}/{total} ({elapsed:.1f}s)")

    results = {
        "config": name,
        "model": model,
        "structured": config["structured"],
        "total": total,
        "json_valid": json_valid,
        "json_valid_pct": round(json_valid / total * 100, 1),
        "relevance_accuracy_pct": round(relevance_correct / total * 100, 1),
        "field_accuracy": {
            f: round(field_correct[f] / field_total[f] * 100, 1) if field_total[f] > 0 else None
            for f in FIELDS
        },
        "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "total_time_s": round(sum(latencies), 1),
        "predictions": predictions,
    }
    return results


def main():
    if not GROUND_TRUTH_PATH.exists():
        print(f"Ground truth not found at {GROUND_TRUTH_PATH}")
        print("Create ground_truth.jsonl with hand-labeled records first.")
        return

    records = [json.loads(line) for line in GROUND_TRUTH_PATH.read_text().strip().splitlines()]
    print(f"Loaded {len(records)} ground truth records\n")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for name, config in CONFIGS.items():
        print(f"\n{'='*50}")
        print(f"Running config: {name} (model={config['model']}, structured={config['structured']})")
        print(f"{'='*50}")
        results = run_config(name, config, records)
        all_results[name] = results

        # Save individual results
        result_path = RESULTS_DIR / f"{name}.json"
        result_path.write_text(json.dumps(results, indent=2))
        print(f"  Saved to {result_path}")

    # Print comparison table
    print(f"\n\n{'='*70}")
    print("COMPARISON SUMMARY")
    print(f"{'='*70}")
    print(f"{'Config':<25} {'JSON Valid':>10} {'Relevance':>10} {'Avg Latency':>12}")
    print("-" * 70)
    for name, r in all_results.items():
        print(f"{name:<25} {r['json_valid_pct']:>9}% {r['relevance_accuracy_pct']:>9}% {r['avg_latency_s']:>10}s")

    print(f"\nField-level accuracy:")
    print(f"{'Config':<25}", end="")
    for f in FIELDS:
        print(f" {f:>10}", end="")
    print()
    print("-" * (25 + 11 * len(FIELDS)))
    for name, r in all_results.items():
        print(f"{name:<25}", end="")
        for f in FIELDS:
            val = r["field_accuracy"][f]
            print(f" {val:>9}%" if val is not None else f" {'N/A':>10}", end="")
        print()

    # Save comparison
    comparison_path = RESULTS_DIR / "comparison.json"
    comparison_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nFull results saved to {comparison_path}")


if __name__ == "__main__":
    main()
