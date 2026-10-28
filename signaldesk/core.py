"""Pure inference and evidence validation. Never executes suggested steps."""

from collections import Counter
from copy import deepcopy
from importlib.resources import files
import hashlib
import json
import math
import re


def dataset():
    return json.loads(files("signaldesk").joinpath("data.json").read_text(encoding="utf-8"))


def corpus(split):
    if split not in {"training", "heldout"}:
        raise ValueError("Unknown corpus split")
    return json.loads(files("signaldesk").joinpath(split + ".json").read_text(encoding="utf-8"))


def case_by_id(case_id):
    for case in dataset()["cases"]:
        if case["id"] == case_id:
            return case
    raise ValueError("Unknown synthetic case ID; use list to see available fixtures")


def tokens(text):
    return re.findall(r"[a-z]+", text.lower())


class LocalClassifier:
    """Laplace-smoothed multinomial naive Bayes, trained only on fixture training text.

    This small baseline is real statistical inference, not a generative model and
    not NVIDIA inference. Posterior scores are uncalibrated; evidence gates decide
    whether a candidate may be shown.
    """

    name = "offline-naive-bayes"

    def __init__(self, runbooks):
        self.counts = {
            rb["id"]: Counter() for rb in runbooks
        }
        self.examples = {rb["id"]: 0 for rb in runbooks}
        # Only training text is learned. Held-out labels/text are never read here.
        for case in corpus("training")["cases"]:
            self.counts[case["expected"]].update(tokens(case["text"]))
            self.examples[case["expected"]] += 1
        self.vocabulary = set().union(*(set(c) for c in self.counts.values()))

    def select(self, case):
        observed = [t for t in tokens(case["text"]) if t in self.vocabulary]
        scores = {}
        for rb_id, counts in self.counts.items():
            denominator = sum(counts.values()) + len(self.vocabulary)
            scores[rb_id] = math.log(self.examples[rb_id] / sum(self.examples.values()))
            scores[rb_id] += sum(math.log((counts[t] + 1) / denominator) for t in observed)
        best = max(scores, key=scores.get)
        confidence = 1 / sum(math.exp(s - scores[best]) for s in scores.values())
        overlap = len(set(observed) & set(self.counts[best]))
        if overlap < 2 or confidence < 0.65:
            best = None
        return {"runbook_id": best, "evidence_ids": [e["id"] for e in case["evidence"]]}, {
            "backend": self.name, "score": round(confidence, 4),
            "score_note": "Uncalibrated classifier posterior; not a correctness probability"
        }


def validate_selection(selection, case, runbooks):
    """Models choose IDs only; every rendered instruction comes from a runbook."""
    if not isinstance(selection, dict) or set(selection) != {"runbook_id", "evidence_ids"}:
        raise ValueError("Selection must contain exactly runbook_id and evidence_ids")
    rb_id, ids = selection["runbook_id"], selection["evidence_ids"]
    if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
        raise ValueError("Evidence IDs must be a list of strings")
    evidence = {e["id"]: e for e in case["evidence"]}
    if len(ids) != len(set(ids)) or any(i not in evidence for i in ids):
        raise ValueError("Evidence reference is duplicate or absent from this case")
    if rb_id is None:
        return None, "No supported runbook; collect more evidence and ask an operator"
    if not isinstance(rb_id, str):
        raise ValueError("Runbook ID must be a string or null")
    rb = next((r for r in runbooks if r["id"] == rb_id), None)
    if rb is None:
        raise ValueError("Unknown runbook reference")
    def corroborates(e, book):
        value = e["value"]
        return (e["metric"] == book["metric"] and type(value) in (int, float)
                and math.isfinite(value) and value >= book["minimum"]
                and (book.get("unit") != "percent" or value <= 100))

    abnormal = {r["id"] for r in runbooks
                if any(corroborates(e, r) for e in case["evidence"])}
    if len(abnormal) > 1:
        return None, "Multiple failure families have abnormal telemetry; ask an operator to isolate the fault"
    supporting = []
    for evidence_id in ids:
        e = evidence[evidence_id]
        if corroborates(e, rb):
            supporting.append(evidence_id)
    if not supporting:
        return None, "Candidate lacks corroborating telemetry; ask an operator"
    return (rb, supporting), None


def brief(case, provider=None):
    runbooks = dataset()["runbooks"]
    provider = provider or LocalClassifier(runbooks)
    selection, provenance = provider.select(deepcopy(case))
    accepted, reason = validate_selection(selection, case, runbooks)
    fingerprint = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()
    result = {
        "case_id": case["id"], "title": case["title"], "synthetic": True,
        "input_sha256": fingerprint, "provenance": provenance,
        "status": "supported-hypothesis" if accepted else "needs-human",
        "runbook_id": None, "hypothesis": None, "evidence": [], "steps": [],
        "reason": reason, "actions_executed": 0
    }
    if accepted:
        rb, supporting = accepted
        result.update({
            "runbook_id": rb["id"], "hypothesis": rb["title"],
            "evidence": [e for e in case["evidence"] if e["id"] in supporting],
            "steps": [{"text": s, "source": rb["id"]} for s in rb["steps"]]
        })
    return result


def evaluate(split="heldout"):
    cases = corpus(split)["cases"] if split != "smoke" else dataset()["cases"]
    rows = []
    provider = LocalClassifier(dataset()["runbooks"])
    for case in cases:
        result = brief(case, provider)
        rows.append({"case_id": case["id"], "expected": case["expected"],
                     "actual": result["runbook_id"],
                     "correct": result["runbook_id"] == case["expected"],
                     "reason": result["reason"], "kind": case.get("kind", "smoke"),
                     "score": result["provenance"]["score"]})
    accepted = sum(r["actual"] is not None for r in rows)
    known = sum(r["expected"] is not None for r in rows)
    correct_supported = sum(r["correct"] and r["actual"] is not None for r in rows)
    abstained = len(rows) - accepted
    correct_abstained = sum(r["correct"] and r["actual"] is None for r in rows)
    per_family = {}
    for rb in dataset()["runbooks"]:
        label = rb["id"]
        tp = sum(r["actual"] == label and r["expected"] == label for r in rows)
        predicted = sum(r["actual"] == label for r in rows)
        expected = sum(r["expected"] == label for r in rows)
        per_family[label] = {"correct": tp, "predicted": predicted, "expected": expected,
                            "precision": tp / predicted if predicted else None,
                            "recall": tp / expected if expected else None}
    metrics = {"accepted": accepted, "known": known, "correct_supported": correct_supported,
               "abstained": abstained, "correct_abstained": correct_abstained,
               "precision": correct_supported / accepted if accepted else None,
               "recall": correct_supported / known if known else None,
               "abstention_rate": abstained / len(rows) if rows else None,
               "unknown_rejection_rate": correct_abstained / (len(rows)-known) if len(rows)>known else None}
    return {"backend": "offline-naive-bayes", "synthetic_only": True,
            "split": split, "note": "Separately authored synthetic set, same AI author; no external validation or model comparison",
            "correct": sum(r["correct"] for r in rows), "total": len(rows),
            "metrics": metrics, "per_family": per_family, "cases": rows}
