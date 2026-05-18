import subprocess
import unittest
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.engine import SigmaEngine
from app.routes.http import build_http_router
from app.routes.jsonrpc import build_jsonrpc_router
from app.rpc import RpcDispatcher
from app.errors import SigmaEngineException
from app.sigma_bundle import (
    InputSigmaIndicator,
    TranslateSigmaBundleRequest,
    build_sigma_translation_bundle,
    evaluate_sigma_bundle_conversions,
    format_derived_sigma_indicator_description,
    new_stix_id,
    normalize_input_sigma_indicator_for_bundle,
    translate_sigma_bundle,
)


SIGMA_RULE = (
    "title: Suspicious Cmd\n"
    "logsource:\n"
    "  category: process_creation\n"
    "detection:\n"
    "  selection:\n"
    "    Image|endswith: '\\\\cmd.exe'\n"
    "  condition: selection\n"
)


SOURCE_INDICATOR_ID = "indicator--22222222-2222-4222-8222-222222222222"
SOURCE_CONFIDENCE = 80


def _make_source_indicator(pattern: str = SIGMA_RULE) -> dict[str, Any]:
    return {
        "type": "indicator",
        "id": SOURCE_INDICATOR_ID,
        "name": "Sigma process creation example",
        "description": "Source Sigma rule",
        "pattern_type": "sigma",
        "pattern": pattern,
        "confidence": SOURCE_CONFIDENCE,
    }


class FakeSigmaEngine:
    def __init__(self) -> None:
        self.convert_calls: list[dict[str, Any]] = []
        self.fail_targets: set[str] = set()
        self.empty_targets: set[str] = set()

    def convert_rule(
        self,
        rule_text: str,
        target: str,
        pipeline: str | None = None,
        output_format: str | None = None,
        without_pipeline: bool = False,
    ) -> dict[str, Any]:
        self.convert_calls.append(
            {
                "target": target,
                "pipeline": pipeline,
                "without_pipeline": without_pipeline,
            }
        )
        if target in self.fail_targets:
            raise SigmaEngineException(f"conversion failed for {target}")
        if target in self.empty_targets:
            return {"target": target, "query": "", "pipeline": pipeline}
        return {
            "target": target,
            "query": f"converted_{target}",
            "pipeline": pipeline,
        }

    def sigma_available(self) -> bool:
        return True

    def list_backends(self, **kwargs: Any) -> list[str]:
        return ["splunk", "eql", "es-qs"]


class StubSigmaBundleEngine(SigmaEngine):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.next_result = subprocess.CompletedProcess(
            args=["sigma"], returncode=0, stdout="converted_output", stderr=""
        )

    def _run_sigma(
        self, args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        return self.next_result


class SigmaBundleCoreTests(unittest.TestCase):
    def test_new_stix_id_format(self) -> None:
        bid = new_stix_id("bundle")
        self.assertTrue(bid.startswith("bundle--"))
        self.assertEqual(len(bid), len("bundle--") + 36)

        iid = new_stix_id("indicator")
        self.assertTrue(iid.startswith("indicator--"))

        rid = new_stix_id("relationship")
        self.assertTrue(rid.startswith("relationship--"))

    def test_normalize_input_indicator(self) -> None:
        raw = _make_source_indicator()
        indicator = InputSigmaIndicator.model_validate(raw)
        normalized = normalize_input_sigma_indicator_for_bundle(indicator)
        self.assertEqual(normalized["type"], "indicator")
        self.assertEqual(normalized["spec_version"], "2.1")
        self.assertEqual(normalized["id"], SOURCE_INDICATOR_ID)
        self.assertEqual(normalized["pattern_type"], "sigma")
        self.assertEqual(normalized["pattern"], SIGMA_RULE.strip())
        self.assertEqual(normalized["confidence"], SOURCE_CONFIDENCE)
        self.assertIn("sigma-jsonrpc", normalized.get("labels", []))
        self.assertIn("source", normalized.get("labels", []))
        self.assertIn("created", normalized)

    def test_format_derived_description(self) -> None:
        desc = format_derived_sigma_indicator_description("Source rule")
        self.assertIn("Source rule", desc)
        self.assertIn("automatically generated", desc)

        desc2 = format_derived_sigma_indicator_description(None)
        self.assertIn("Sigma rule", desc2)

    def test_input_validator_rejects_non_indicator_type(self) -> None:
        with self.assertRaises(Exception) as ctx:
            InputSigmaIndicator.model_validate(
                {
                    **{"id": "indicator--1", "pattern_type": "sigma", "pattern": "x"},
                    "type": "bundle",
                }
            )
        self.assertIn("only_indicator_object_supported", str(ctx.exception))

    def test_input_validator_rejects_non_sigma_pattern_type(self) -> None:
        with self.assertRaises(Exception) as ctx:
            InputSigmaIndicator.model_validate(
                {
                    **{"type": "indicator", "pattern": "x"},
                    "pattern_type": "stix",
                    "id": "indicator--1",
                }
            )
        self.assertIn("pattern_type_must_be_sigma", str(ctx.exception))

    def test_input_validator_rejects_empty_pattern(self) -> None:
        with self.assertRaises(Exception) as ctx:
            InputSigmaIndicator.model_validate(
                {
                    "type": "indicator",
                    "id": "indicator--1",
                    "pattern_type": "sigma",
                    "pattern": "   ",
                }
            )
        self.assertIn("pattern_required", str(ctx.exception))

    def test_request_validator_rejects_empty_targets(self) -> None:
        with self.assertRaises(Exception) as ctx:
            TranslateSigmaBundleRequest.model_validate(
                {
                    "indicator": _make_source_indicator(),
                    "targets": [],
                }
            )
        self.assertIn("target_required", str(ctx.exception))

    def test_evaluate_conversions_success(self) -> None:
        engine = FakeSigmaEngine()
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        conversions = evaluate_sigma_bundle_conversions(
            engine, source, ["splunk", "eql"], {}, True
        )
        self.assertEqual(len(conversions), 2)
        for c in conversions:
            self.assertTrue(c.success)
            self.assertIsNone(c.error)
            self.assertIn(c.target, ["splunk", "eql"])
            self.assertEqual(c.indicator["pattern"], f"converted_{c.target}")
            self.assertEqual(c.relationship["relationship_type"], "derived-from")
            self.assertEqual(c.relationship["source_ref"], c.indicator["id"])
            self.assertEqual(c.relationship["target_ref"], SOURCE_INDICATOR_ID)

    def test_evaluate_conversions_partial_failure(self) -> None:
        engine = FakeSigmaEngine()
        engine.fail_targets = {"eql"}
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        conversions = evaluate_sigma_bundle_conversions(
            engine, source, ["splunk", "eql"], {}, True
        )
        successes = [c for c in conversions if c.success]
        failures = [c for c in conversions if not c.success]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(successes[0].target, "splunk")
        self.assertEqual(failures[0].target, "eql")
        self.assertIsNotNone(failures[0].error)

    def test_evaluate_conversions_empty_output_is_failure(self) -> None:
        engine = FakeSigmaEngine()
        engine.empty_targets = {"splunk"}
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        conversions = evaluate_sigma_bundle_conversions(
            engine, source, ["splunk"], {}, True
        )
        self.assertEqual(len(conversions), 1)
        self.assertFalse(conversions[0].success)

    def test_build_bundle_includes_source(self) -> None:
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        bundle = build_sigma_translation_bundle(source, [], True, [])
        self.assertEqual(bundle["type"], "bundle")
        self.assertEqual(bundle["spec_version"], "2.1")
        self.assertIn(SOURCE_INDICATOR_ID, {o["id"] for o in bundle["objects"]})

    def test_build_bundle_excludes_source(self) -> None:
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        bundle = build_sigma_translation_bundle(source, [], False, [])
        self.assertEqual(bundle["type"], "bundle")
        self.assertNotIn(SOURCE_INDICATOR_ID, {o.get("id") for o in bundle["objects"]})

    def test_build_bundle_with_conversions(self) -> None:
        engine = FakeSigmaEngine()
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        conversions = evaluate_sigma_bundle_conversions(
            engine, source, ["splunk"], {}, True
        )
        bundle = build_sigma_translation_bundle(source, conversions, True, [])
        obj_ids = {o["id"] for o in bundle["objects"]}
        self.assertIn(SOURCE_INDICATOR_ID, obj_ids)
        self.assertIn(conversions[0].indicator["id"], obj_ids)
        self.assertIn(conversions[0].relationship["id"], obj_ids)
        relationships = [o for o in bundle["objects"] if o["type"] == "relationship"]
        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]["relationship_type"], "derived-from")
        self.assertEqual(relationships[0]["source_ref"], conversions[0].indicator["id"])
        self.assertEqual(relationships[0]["target_ref"], SOURCE_INDICATOR_ID)

    def test_upstream_objects_preserved_and_deduped(self) -> None:
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        upstream = [
            {"id": "indicator--upstream-1", "type": "indicator", "name": "up1"},
            {"id": SOURCE_INDICATOR_ID, "type": "indicator", "name": "dup"},
        ]
        bundle = build_sigma_translation_bundle(source, [], True, upstream)
        obj_ids = {o["id"] for o in bundle["objects"]}
        self.assertIn("indicator--upstream-1", obj_ids)
        self.assertEqual(
            len([o for o in bundle["objects"] if o["id"] == SOURCE_INDICATOR_ID]),
            1,
        )

    def test_all_conversions_fail_reports_error_status(self) -> None:
        engine = FakeSigmaEngine()
        engine.fail_targets = {"splunk"}
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        conversions = evaluate_sigma_bundle_conversions(
            engine, source, ["splunk"], {}, True
        )
        bundle = build_sigma_translation_bundle(source, conversions, True, [])
        self.assertEqual(bundle.get("status"), "error")
        self.assertEqual(
            bundle.get("comments"),
            ["No conversion results for the provided Sigma indicator"],
        )

    def test_partial_failure_reports_errors(self) -> None:
        engine = FakeSigmaEngine()
        engine.fail_targets = {"eql"}
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        conversions = evaluate_sigma_bundle_conversions(
            engine, source, ["splunk", "eql"], {}, True
        )
        bundle = build_sigma_translation_bundle(source, conversions, True, [])
        self.assertNotIn("status", bundle)
        self.assertIn("x_sigma_jsonrpc_conversion_errors", bundle)
        self.assertEqual(len(bundle["x_sigma_jsonrpc_conversion_errors"]), 1)
        self.assertEqual(
            bundle["x_sigma_jsonrpc_conversion_errors"][0]["target"], "eql"
        )

    def test_derived_indicators_have_metadata(self) -> None:
        engine = FakeSigmaEngine()
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        conversions = evaluate_sigma_bundle_conversions(
            engine, source, ["splunk"], {"splunk": "splunk_windows"}, False
        )
        ind = conversions[0].indicator
        self.assertEqual(ind["x_sigma_jsonrpc_target"], "splunk")
        self.assertEqual(ind["x_sigma_jsonrpc_pipeline"], "splunk_windows")
        self.assertFalse(ind["x_sigma_jsonrpc_without_pipeline"])
        self.assertEqual(ind["x_sigma_jsonrpc_source_indicator"], SOURCE_INDICATOR_ID)
        self.assertEqual(ind["x_sigma_jsonrpc_engine"], "sigma-cli")
        self.assertIn("sigma-jsonrpc", ind.get("labels", []))
        self.assertIn("auto-generated", ind.get("labels", []))
        self.assertIn("splunk", ind.get("labels", []))

    def test_integration_translate_sigma_bundle(self) -> None:
        engine = FakeSigmaEngine()
        indicator = InputSigmaIndicator.model_validate(_make_source_indicator())
        bundle = translate_sigma_bundle(
            engine=engine,
            indicator=indicator,
            targets=["splunk", "eql"],
        )
        self.assertEqual(bundle["type"], "bundle")
        self.assertEqual(bundle["spec_version"], "2.1")
        self.assertIn(SOURCE_INDICATOR_ID, {o["id"] for o in bundle["objects"]})
        indicators = [o for o in bundle["objects"] if o["type"] == "indicator"]
        relationships = [o for o in bundle["objects"] if o["type"] == "relationship"]
        self.assertEqual(len(indicators), 3)  # source + 2 derived
        self.assertEqual(len(relationships), 2)
        for rel in relationships:
            self.assertEqual(rel["relationship_type"], "derived-from")
            self.assertEqual(rel["target_ref"], SOURCE_INDICATOR_ID)

    def test_ids_are_unique_across_conversions(self) -> None:
        engine = FakeSigmaEngine()
        source = normalize_input_sigma_indicator_for_bundle(
            InputSigmaIndicator.model_validate(_make_source_indicator())
        )
        conversions = evaluate_sigma_bundle_conversions(
            engine, source, ["splunk", "eql", "es-qs"], {}, True
        )
        all_ids: list[str] = []
        for c in conversions:
            all_ids.append(c.indicator["id"])
            all_ids.append(c.relationship["id"])
        self.assertEqual(
            len(all_ids), len(set(all_ids)), msg="derived IDs must be unique"
        )


class SigmaBundleHttpApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(SIGMA_AUTH_REQUIRED=False)
        self.engine = FakeSigmaEngine()
        self.dispatcher = RpcDispatcher(self.settings, self.engine)  # type: ignore[arg-type]
        app = FastAPI()
        app.include_router(
            build_http_router(
                self.settings,
                self.engine,
                self.dispatcher,
                None,  # type: ignore[arg-type]
            )
        )
        self.client = TestClient(app)

    def test_endpoint_returns_bundle_with_indicators_and_relationships(self) -> None:
        payload = {
            "indicator": _make_source_indicator(),
            "targets": ["splunk", "eql"],
        }
        response = self.client.post("/api/translate/sigma-bundle", json=payload)
        self.assertEqual(response.status_code, 200)
        bundle = response.json()
        self.assertEqual(bundle["type"], "bundle")
        self.assertEqual(bundle["spec_version"], "2.1")
        obj_ids = {o["id"] for o in bundle["objects"]}
        self.assertIn(SOURCE_INDICATOR_ID, obj_ids)
        indicators = [o for o in bundle["objects"] if o["type"] == "indicator"]
        relationships = [o for o in bundle["objects"] if o["type"] == "relationship"]
        self.assertGreaterEqual(len(indicators), 2)
        self.assertEqual(len(relationships), 2)
        for rel in relationships:
            self.assertEqual(rel["relationship_type"], "derived-from")
            self.assertEqual(rel["target_ref"], SOURCE_INDICATOR_ID)

    def test_rejects_missing_auth(self) -> None:
        auth_settings = Settings(SIGMA_AUTH_REQUIRED=True, SIGMA_RPC_TOKEN="secret")
        auth_engine = FakeSigmaEngine()
        auth_dispatcher = RpcDispatcher(auth_settings, auth_engine)  # type: ignore[arg-type]
        app = FastAPI()
        app.include_router(
            build_http_router(
                auth_settings,
                auth_engine,
                auth_dispatcher,
                None,  # type: ignore[arg-type]
            )
        )
        client = TestClient(app)
        payload = {
            "indicator": _make_source_indicator(),
            "targets": ["splunk"],
        }
        response = client.post("/api/translate/sigma-bundle", json=payload)
        self.assertEqual(response.status_code, 401)

    def test_rejects_stix_pattern_type(self) -> None:
        payload = {
            "indicator": {
                **{"type": "indicator", "pattern": "[process:name = 'cmd.exe']"},
                "pattern_type": "stix",
                "id": "indicator--1",
            },
            "targets": ["splunk"],
        }
        response = self.client.post("/api/translate/sigma-bundle", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("pattern_type_must_be_sigma", response.text)

    def test_rejects_empty_pattern(self) -> None:
        payload = {
            "indicator": {
                "type": "indicator",
                "id": "indicator--1",
                "pattern_type": "sigma",
                "pattern": "   ",
            },
            "targets": ["splunk"],
        }
        response = self.client.post("/api/translate/sigma-bundle", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("pattern_required", response.text)

    def test_rejects_non_indicator_type(self) -> None:
        payload = {
            "indicator": {
                "type": "bundle",
                "id": "bundle--1",
                "pattern_type": "sigma",
                "pattern": "title: test",
            },
            "targets": ["splunk"],
        }
        response = self.client.post("/api/translate/sigma-bundle", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("only_indicator_object_supported", response.text)

    def test_rejects_empty_targets(self) -> None:
        payload = {
            "indicator": _make_source_indicator(),
            "targets": [],
        }
        response = self.client.post("/api/translate/sigma-bundle", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("target_required", response.text)

    def test_rejects_invalid_json(self) -> None:
        response = self.client.post(
            "/api/translate/sigma-bundle",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid_request_payload", response.text)

    def test_upstream_objects_preserved(self) -> None:
        upstream_id = "indicator--upstream-test"
        payload = {
            "indicator": _make_source_indicator(),
            "targets": ["splunk"],
            "upstream_objects": [
                {"id": upstream_id, "type": "indicator", "name": "upstream"}
            ],
        }
        response = self.client.post("/api/translate/sigma-bundle", json=payload)
        self.assertEqual(response.status_code, 200)
        bundle = response.json()
        obj_ids = {o["id"] for o in bundle["objects"]}
        self.assertIn(upstream_id, obj_ids)

    def test_partial_failure_includes_errors(self) -> None:
        self.engine.fail_targets = {"eql"}
        payload = {
            "indicator": _make_source_indicator(),
            "targets": ["splunk", "eql"],
        }
        response = self.client.post("/api/translate/sigma-bundle", json=payload)
        self.assertEqual(response.status_code, 200)
        bundle = response.json()
        self.assertIn("x_sigma_jsonrpc_conversion_errors", bundle)
        self.assertEqual(
            bundle["x_sigma_jsonrpc_conversion_errors"][0]["target"], "eql"
        )
        obj_ids = {o["id"] for o in bundle["objects"]}
        self.assertIn(SOURCE_INDICATOR_ID, obj_ids)

    def test_all_fail_returns_error_status(self) -> None:
        self.engine.fail_targets = {"splunk"}
        payload = {
            "indicator": _make_source_indicator(),
            "targets": ["splunk"],
        }
        response = self.client.post("/api/translate/sigma-bundle", json=payload)
        self.assertEqual(response.status_code, 200)
        bundle = response.json()
        self.assertEqual(bundle.get("status"), "error")
        self.assertEqual(bundle.get("objects", []), [])


class SigmaBundleRpcTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(SIGMA_AUTH_REQUIRED=False)
        self.engine = FakeSigmaEngine()
        self.dispatcher = RpcDispatcher(self.settings, self.engine)  # type: ignore[arg-type]
        app = FastAPI()
        app.include_router(build_jsonrpc_router(self.settings, self.dispatcher))
        self.client = TestClient(app)

    def test_rpc_sigma_indicator_bundle(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "sigma.indicator.bundle",
            "params": {
                "indicator": _make_source_indicator(),
                "targets": ["splunk"],
            },
        }
        response = self.client.post("/jsonrpc", json=payload)
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertEqual(result["type"], "bundle")
        self.assertEqual(result["spec_version"], "2.1")
        self.assertIn(SOURCE_INDICATOR_ID, {o["id"] for o in result["objects"]})

    def test_rpc_rejects_missing_indicator(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "sigma.indicator.bundle",
            "params": {"targets": ["splunk"]},
        }
        response = self.client.post("/jsonrpc", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.json())

    def test_rpc_discover_lists_method(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "rpc.discover",
            "params": {},
        }
        response = self.client.post("/jsonrpc", json=payload)
        result = response.json()["result"]
        self.assertIn("sigma.indicator.bundle", result["methods"])


if __name__ == "__main__":
    unittest.main()
