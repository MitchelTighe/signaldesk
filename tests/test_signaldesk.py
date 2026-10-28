from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import urllib.error
from urllib.request import Request

from signaldesk.__main__ import main
from signaldesk.core import brief, case_by_id, dataset, corpus, evaluate, validate_selection
from signaldesk.providers import ENDPOINT, MAX_RESPONSE, NebiusProvider, ProviderError, send


def envelope(selection):
    return json.dumps({"choices": [{"message": {"content": json.dumps(selection)}}]}).encode()


class CoreTests(unittest.TestCase):
    def test_evaluation_has_six_supported_and_two_unknown_cases(self):
        result = evaluate("smoke")
        self.assertEqual((result["correct"], result["total"]), (8, 8))
        self.assertEqual(sum(r["actual"] is None for r in result["cases"]), 2)

    def test_eval_text_is_separate_from_training_examples(self):
        data = dataset()
        training = {c["text"] for c in corpus("training")["cases"]}
        self.assertTrue(all(c["text"] not in training for c in data["cases"]))

    def test_all_accepted_steps_have_real_citations_and_telemetry(self):
        sources = {rb["id"]: rb for rb in dataset()["runbooks"]}
        for case in dataset()["cases"]:
            with self.subTest(case=case["id"]):
                result = brief(case)
                self.assertEqual(result["actions_executed"], 0)
                if result["runbook_id"]:
                    rb = sources[result["runbook_id"]]
                    self.assertEqual([s["text"] for s in result["steps"]], rb["steps"])
                    self.assertTrue(all(s["source"] == rb["id"] for s in result["steps"]))
                    self.assertTrue(result["evidence"])
                    self.assertTrue(all(e in case["evidence"] for e in result["evidence"]))
                else:
                    self.assertEqual(result["steps"], [])

    def test_classifier_candidate_requires_corroborating_telemetry(self):
        case = case_by_id("load-demo")
        case["evidence"][0]["value"] = 25
        result = brief(case)
        self.assertEqual(result["status"], "needs-human")
        self.assertIn("corroborating", result["reason"])

    def test_bool_string_nan_and_missing_metrics_do_not_corroborate(self):
        for value in [True, "97", float("nan"), float("inf"), -1]:
            with self.subTest(value=value):
                case = case_by_id("load-demo")
                case["evidence"][0]["value"] = value
                self.assertIsNone(brief(case)["runbook_id"])
        case["evidence"] = []
        self.assertIsNone(brief(case)["runbook_id"])

    def test_unknown_and_injected_instruction_abstain(self):
        for case_id in ("unknown-demo", "injection-demo"):
            result = brief(case_by_id(case_id))
            self.assertEqual(result["status"], "needs-human")
            self.assertEqual(result["steps"], [])

    def test_bad_model_schema_and_invented_evidence_are_rejected(self):
        cases = [[], {"runbook_id": "RB-CLEAN"},
                 {"runbook_id": "RB-CLEAN", "evidence_ids": "E-C1"},
                 {"runbook_id": "RB-CLEAN", "evidence_ids": [1]},
                 {"runbook_id": "RB-CLEAN", "evidence_ids": ["E-FAKE"]},
                 {"runbook_id": "RB-CLEAN", "evidence_ids": ["E-C1", "E-C1"]},
                 {"runbook_id": ["RB-CLEAN"], "evidence_ids": []},
                 {"runbook_id": "RB-FAKE", "evidence_ids": []},
                 {"runbook_id": "RB-CLEAN", "evidence_ids": ["E-C1"], "steps": ["invented"]}]
        for selection in cases:
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                validate_selection(selection, case_by_id("clean-demo"), dataset()["runbooks"])

    def test_wrong_case_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_selection({"runbook_id":"RB-CLEAN", "evidence_ids":["E-L1"]},
                               case_by_id("clean-demo"), dataset()["runbooks"])

    def test_hash_is_deterministic_and_tracks_case_changes(self):
        case = case_by_id("clean-demo")
        first = brief(case)
        self.assertEqual(first, brief(deepcopy(case)))
        case["text"] += " changed"
        self.assertNotEqual(first["input_sha256"], brief(case)["input_sha256"])

    def test_offline_inference_never_uses_network(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(evaluate()["total"], 40)


class ProviderTests(unittest.TestCase):
    def test_request_and_grounded_response_use_documented_endpoint(self):
        seen = []

        def transport(request):
            seen.append(request)
            return envelope({"runbook_id":"RB-CLEAN", "evidence_ids":["E-C1"]})

        provider = NebiusProvider("nvidia/TEST-MODEL", "fixture-credential", transport)
        result = brief(case_by_id("clean-demo"), provider)
        request = seen[0]
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-credential")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "nvidia/TEST-MODEL")
        context = json.loads(payload["messages"][1]["content"])
        self.assertNotIn("expected", context["incident"])
        self.assertNotIn("training", context["runbooks"][0])
        self.assertEqual(result["runbook_id"], "RB-CLEAN")
        self.assertEqual(result["provenance"]["transport"], "injected-test-transport")
        self.assertNotIn("fixture-credential", json.dumps(result))

    def test_non_fixture_input_is_refused_before_transport(self):
        case = case_by_id("clean-demo")
        case["text"] = "Unapproved external input"
        provider = NebiusProvider("nvidia/TEST-MODEL", "fixture-credential",
                                  lambda request: self.fail("transport must not run"))
        with self.assertRaises(ProviderError):
            brief(case, provider)

    def test_malformed_api_envelopes_fail_without_silent_offline_fallback(self):
        for raw in [b"not json", b"{}", b'{"choices":[]}',
                    b'{"choices":[{"message":{"content":"not json"}}]}']:
            with self.subTest(raw=raw):
                provider = NebiusProvider("nvidia/TEST-MODEL", "fixture-credential", lambda req: raw)
                with self.assertRaises(ProviderError):
                    brief(case_by_id("clean-demo"), provider)

    def test_size_bound(self):
        provider = NebiusProvider("nvidia/TEST-MODEL", "fixture-credential",
                                  lambda req: b"x" * (MAX_RESPONSE + 1))
        with self.assertRaises(ProviderError):
            brief(case_by_id("clean-demo"), provider)

    def test_model_invented_action_is_not_rendered(self):
        provider = NebiusProvider("nvidia/TEST-MODEL", "fixture-credential",
            lambda req: envelope({"runbook_id":"RB-CLEAN", "evidence_ids":["E-C1"],
                                  "steps":["restart everything"]}))
        with self.assertRaises(ValueError):
            brief(case_by_id("clean-demo"), provider)

    def test_provider_cannot_override_metric_gate(self):
        provider = NebiusProvider("nvidia/TEST-MODEL", "fixture-credential",
            lambda req: envelope({"runbook_id":"RB-CLEAN", "evidence_ids":["E-L1"]}))
        result = brief(case_by_id("load-demo"), provider)
        self.assertEqual(result["status"], "needs-human")

    def test_invalid_model_or_credential_refused(self):
        for model, token in [("other/model", "fixture"), ("nvidia/model\n", "fixture"),
                             ("nvidia/model", ""), ("nvidia/model", "x\ny")]:
            with self.subTest(model=model), self.assertRaises(ProviderError):
                NebiusProvider(model, token)

    def test_transport_disables_proxy_redirects_and_bounds_timeout(self):
        raw_response = io.BytesIO(envelope({"runbook_id":None, "evidence_ids":[]}))
        with patch("urllib.request.build_opener") as build:
            build.return_value.open.return_value.__enter__.return_value = raw_response
            request = Request(ENDPOINT)
            send(request)
            args = build.call_args.args
            self.assertEqual(args[0].proxies, {})
            self.assertIsNone(args[1].redirect_request(None, None, 302, "", {}, "https://elsewhere.invalid"))
            build.return_value.open.assert_called_once_with(request, timeout=15)

    def test_transport_error_body_is_not_leaked(self):
        with patch("urllib.request.build_opener") as build:
            build.return_value.open.side_effect = urllib.error.URLError("fixture-sensitive-content")
            with self.assertRaises(ProviderError) as caught:
                send(Request(ENDPOINT))
            self.assertNotIn("fixture-sensitive-content", str(caught.exception))


class CLITests(unittest.TestCase):
    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_real_module_entrypoint_demo(self):
        result = subprocess.run([sys.executable, "-m", "signaldesk", "demo"],
                                cwd=Path(__file__).resolve().parents[1],
                                # 2026-10-18: a loaded, one-CPU rootless host exceeded 10s
                                # during cold startup. Keep a bounded deadline and all output assertions.
                                capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Actions executed: 0"), 5)
        self.assertIn("[RB-MOUNT]", result.stdout)
        self.assertIn("needs-human", result.stdout)

    def test_case_json(self):
        code, out, err = self.invoke("case", "ltfs-demo", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(json.loads(out)["runbook_id"], "RB-LTFS")

    def test_cli_exports_the_actual_offline_page(self):
        from signaldesk.web import render
        code, out, err = self.invoke("export-web")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, render())

    def test_unknown_fixture_is_a_clean_failure(self):
        code, out, err = self.invoke("case", "../../outside")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("No action executed", err)

    def test_evaluate_exit_status_and_output(self):
        code, out, _ = self.invoke("evaluate")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["total"], 40)

    def test_model_credential_not_accepted_in_offline_mode(self):
        with self.assertRaises(SystemExit) as caught:
            self.invoke("demo", "--token-fd", "3")
        self.assertEqual(caught.exception.code, 2)

    def test_nebius_requires_explicit_case_and_broker_descriptor(self):
        for args in [("demo", "--backend", "nebius"),
                     ("case", "clean-demo", "--backend", "nebius")]:
            with self.subTest(args=args), self.assertRaises(SystemExit) as caught:
                self.invoke(*args)
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
