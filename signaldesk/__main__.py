"""Synthetic CLI and deterministic offline web export."""

import argparse
import json
import sys

from .core import brief, case_by_id, dataset, evaluate
from .providers import ProviderError


def show(result):
    print(f"\nSIGNALDESK / SYNTHETIC ONLY / {result['case_id']}")
    print(result["title"])
    print(f"Status: {result['status']} | Backend: {result['provenance']['backend']}")
    print(f"Hypothesis: {result['hypothesis'] or 'Unknown'}")
    for evidence in result["evidence"]:
        print(f"  [{evidence['id']}] {evidence['metric']} = {evidence['value']}")
    for i, step in enumerate(result["steps"], 1):
        print(f"  {i}. {step['text']} [{step['source']}]")
    if result["reason"]:
        print(result["reason"])
    print(f"Actions executed: {result['actions_executed']} | Input SHA256: {result['input_sha256'][:12]}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tape-library incident briefs with runbook citations (emulated or synthetic data)")
    parser.add_argument("command", choices=["demo", "list", "case", "evaluate", "export-web"])
    parser.add_argument("case_id", nargs="?")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--split", choices=["heldout", "smoke", "training", "challenge"], default="heldout")
    parser.add_argument("--backend", choices=["offline", "nebius"], default="offline")
    parser.add_argument("--model", help="Current NVIDIA catalog ID; required for Nebius")
    parser.add_argument("--endpoint", choices=["global", "us-central1"])
    parser.add_argument("--token-fd", type=int, help="Retired compatibility flag; never read")
    args = parser.parse_args(argv)
    if args.command == "case" and not args.case_id:
        parser.error("case requires a synthetic case ID")
    if args.command != "case" and args.case_id:
        parser.error("only case accepts a case ID")
    if args.backend == "nebius" and args.command != "case":
        parser.error("Nebius calls require a single explicit synthetic case")
    if args.backend == "offline" and (args.model or args.token_fd is not None):
        parser.error("model and token-fd apply only to the Nebius backend")
    if args.backend == "nebius":
        parser.error("Legacy FD CLI retired before credential access; use scripts/signaldesk_live_eval.sh with broker-injected NEBIUS_API_KEY")
    try:
        if args.command == "export-web":
            from .web import render
            print(render(), end="")
            return 0
        if args.command == "evaluate":
            if args.split == "challenge":
                from .challenge import evaluate_challenge
                result = evaluate_challenge()
                print(json.dumps(result, indent=2))
                return 0 if result["quality_gates_passed"] else 1
            result = evaluate(args.split)
            print(json.dumps(result, indent=2))
            # A missed case remains in the report. Quality gates aren't a demand
            # to tune against held-out labels until the result is perfect.
            metrics = result["metrics"]
            return 0 if ((metrics["precision"] or 0) >= 0.8
                         and (metrics["recall"] or 0) >= 0.65
                         and metrics["unknown_rejection_rate"] in (None, 1.0)) else 1
        if args.command == "list":
            print("\n".join(c["id"] for c in dataset()["cases"]))
            return 0
        case = case_by_id(args.case_id) if args.command == "case" else None
        cases = [case] if case else [case_by_id(i) for i in
                  ("load-demo", "clean-demo", "ltfs-demo", "unknown-demo", "injection-demo")]
        results = [brief(c) for c in cases]
        if args.json:
            print(json.dumps(results[0] if case else results, indent=2))
        else:
            for result in results:
                show(result)
        return 0
    except (ValueError, OSError, ProviderError):
        print("Unable to produce a brief: invalid fixture, selection or provider access. No action executed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
