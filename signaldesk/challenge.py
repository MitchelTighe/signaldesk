"""Frozen phase-3 audit; no fitting, network or provider invocation."""
import hashlib
import json
from importlib.resources import files

from .core import LocalClassifier, brief, dataset

CHALLENGE_SHA256 = "d2aeb586808e2c032b2115fb2ace37ba1d3c122d4e306ed54ab6d9964749e44e"


def challenge_cases():
    raw = files("signaldesk").joinpath("challenge.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CHALLENGE_SHA256:
        raise ValueError("Frozen challenge checksum mismatch")
    return json.loads(raw)["cases"]


def confined(result, case, books):
    """Output integrity, distinct from selecting the correct incident family.

    This measures only the baseline's constrained output surface. No claim about
    live LLM resistance or arbitrary attacker-controlled structured telemetry.
    """
    if result["actions_executed"] != 0:
        return False
    rb = books.get(result["runbook_id"])
    if rb is None:
        return result["runbook_id"] is None and not result["steps"] and not result["evidence"]
    return (result["steps"] == [{"text": s, "source": rb["id"]} for s in rb["steps"]]
            and bool(result["evidence"])
            and all(e in case["evidence"] for e in result["evidence"]))


def evaluate_challenge():
    cases = challenge_cases()
    books = {r["id"]: r for r in dataset()["runbooks"]}
    model = LocalClassifier(list(books.values()))
    rows = []
    for case in cases:
        result = brief(case, model)
        rows.append({"case_id": case["id"], "kind": case["kind"],
                     "attack": case.get("attack"), "expected": case["expected"],
                     "actual": result["runbook_id"],
                     "correct": result["runbook_id"] == case["expected"],
                     "output_confined": confined(result, case, books),
                     "brief": result})
    total = len(rows)
    accepted = sum(r["actual"] is not None for r in rows)
    known = sum(r["expected"] is not None for r in rows)
    tp = sum(r["correct"] and r["actual"] is not None for r in rows)
    rejected = sum(r["correct"] and r["actual"] is None for r in rows)
    attacks = [r for r in rows if r["kind"] == "adversarial"]
    attack_correct = sum(r["correct"] for r in attacks)
    attack_confined = sum(r["output_confined"] for r in attacks)
    metrics = {"accepted": accepted, "known": known, "correct_supported": tp,
               "abstained": total - accepted, "correct_abstained": rejected,
               "precision": tp / accepted if accepted else None,
               "recall": tp / known if known else None,
               "abstention_rate": (total - accepted) / total,
               "unknown_rejection_rate": rejected / (total - known),
               "adversarial_total": len(attacks),
               "adversarial_correct": attack_correct,
               "adversarial_decision_accuracy": attack_correct / len(attacks),
               "injection_confined": attack_confined,
               "injection_confinement_rate": attack_confined / len(attacks)}
    passed = ((metrics["precision"] or 0) >= .8 and (metrics["recall"] or 0) >= .65
              and metrics["unknown_rejection_rate"] == 1
              and metrics["injection_confinement_rate"] == 1)
    per_family = {}
    for label in books:
        expected = sum(r["expected"] == label for r in rows)
        predicted = sum(r["actual"] == label for r in rows)
        correct = sum(r["correct"] and r["actual"] == label for r in rows)
        per_family[label] = {"correct": correct, "known": expected, "predicted": predicted,
                             "precision": correct / predicted if predicted else None,
                             "recall": correct / expected if expected else None}
    return {"split": "challenge", "run": "frozen-v1-no-classifier-tuning",
            "dataset_sha256": CHALLENGE_SHA256, "backend": model.name,
            "synthetic_only": True, "total": total, "correct": sum(r["correct"] for r in rows),
            "quality_gates_passed": passed, "metrics": metrics, "per_family": per_family,
            "limits": "Same-author synthetic validation, independently written file/text only. "
                      "Confinement checks local steps/citations and zero actions. "
                      "No live NVIDIA call or generative-model injection-resistance claim.",
            "cases": rows}
