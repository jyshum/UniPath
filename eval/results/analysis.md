# Ablation Eval Results — 2026-04-28

## Configs Tested

| Config | Model | Output Mode | Records | Time |
|--------|-------|-------------|---------|------|
| A | llama3.2:3b | Free-form JSON | 50 | 125.8s |
| B | llama3.2:3b | Structured output | 50 | 140.9s |
| C | qwen3:4b | Structured output | DNF | ~75s/record (disqualified) |

## Why qwen3:4b Was Disqualified

Qwen3:4b has built-in chain-of-thought "thinking" that cannot be reliably disabled via Ollama. First record took 263.5s. Even simple prompts took 50-75s vs 3s for llama3.2. At 25x slower, it's impractical for batch extraction.

## Results: Config A vs B

| Metric | A (freeform) | B (structured) |
|--------|-------------|----------------|
| JSON validity | 100% | 100% |
| Relevance accuracy | 96% | 96% |
| Avg latency | 2.52s | 2.82s |
| Decision accuracy | 100% | 100% |
| Core avg accuracy | 100% | 100% |
| Program accuracy | 80% | 80% |
| Province accuracy | 82.5% | 82.5% |
| Citizenship accuracy | 82.5% | 82.5% |
| School accuracy (raw) | 50% | 50% |
| EC raw accuracy (raw) | 22.5% | 22.5% |

## School Accuracy Note

The 50% "school accuracy" is misleading. Most mismatches are normalization variants:
- "Waterloo" vs "University of Waterloo"
- "McMaster" vs "McMaster University"
- "UofT" vs "University of Toronto"

The pipeline's `normalize_school()` already handles these. Only 1/20 mismatches was a genuine error (Sauder → "Western University" instead of "UBC").

**Effective school accuracy: ~97.5%** (after normalization)

## EC Raw Accuracy Note

The 22.5% is expected — exact string matching on free text will almost never match. The model extracts the right information but with slightly different wording ("robotics club, volunteering, and played varsity basketball" vs "robotics club, volunteering, varsity basketball"). Downstream EC tagging handles normalization.

## Winner: Config B (llama3.2:3b + structured output)

**Rationale:**
1. Identical accuracy to freeform
2. Guarantees valid JSON schema via Ollama's XGrammar constrained decoding
3. Eliminates manual JSON fence-stripping and parse error handling
4. Enables Pydantic `model_validate_json()` directly
5. Marginal latency increase (2.82s vs 2.52s) — acceptable
6. No model migration needed — same llama3.2:3b
