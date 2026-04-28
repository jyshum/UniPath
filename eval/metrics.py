"""Scoring functions for extraction eval."""
from eval.schemas import AdmissionExtraction


FIELDS = ["school", "program", "decision", "core_avg", "ec_raw", "province", "citizenship"]


def field_accuracy(predicted: AdmissionExtraction, truth: AdmissionExtraction) -> dict[str, bool]:
    """Returns a dict of field_name -> whether predicted matches truth."""
    results = {}
    for field in FIELDS:
        pred_val = getattr(predicted, field)
        true_val = getattr(truth, field)
        if true_val is None:
            results[field] = pred_val is None
        elif field == "core_avg" and pred_val is not None and true_val is not None:
            results[field] = abs(pred_val - true_val) <= 1.0
        elif isinstance(true_val, str) and isinstance(pred_val, str):
            results[field] = pred_val.strip().lower() == true_val.strip().lower()
        else:
            results[field] = pred_val == true_val
    return results


def relevance_accuracy(predicted: AdmissionExtraction, truth: AdmissionExtraction) -> bool:
    """Whether predicted.relevant matches truth.relevant."""
    return predicted.relevant == truth.relevant
