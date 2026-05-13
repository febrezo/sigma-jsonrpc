import unittest

from app.config import Settings
from app.errors import INVALID_PARAMS, METHOD_NOT_FOUND, RpcException
from app.rpc import RpcDispatcher


class FakeEngine:
    def __init__(self) -> None:
        self.last_list_pipelines_target = None
        self.last_without_pipeline = None

    def sigma_available(self) -> bool:
        return True

    def list_plugins(self):
        return []

    def list_backends(self):
        return ["splunk"]

    def list_pipelines(self, target=None):
        self.last_list_pipelines_target = target
        if target == "splunk":
            return ["splunk_windows"]
        return []

    def validate_rule(self, rule_text: str):
        class _Result:
            def model_dump(self):
                return {"valid": bool(rule_text), "errors": [], "warnings": []}

        return _Result()

    def convert_rule(self, rule_text: str, target: str, pipeline=None, output_format=None, without_pipeline=False):
        self.last_without_pipeline = without_pipeline
        return {
            "target": target,
            "query": f"converted:{rule_text[:8]}",
            "pipeline": pipeline,
            "format": output_format,
            "without_pipeline": without_pipeline,
            "metadata": {},
        }


class RpcDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        settings = Settings()
        self.engine = FakeEngine()
        self.dispatcher = RpcDispatcher(settings, self.engine)

    def test_unknown_method_returns_method_not_found(self) -> None:
        with self.assertRaises(RpcException) as ctx:
            self.dispatcher.dispatch("unknown.method", {})
        self.assertEqual(ctx.exception.code, METHOD_NOT_FOUND)

    def test_non_object_params_return_invalid_params(self) -> None:
        with self.assertRaises(RpcException) as ctx:
            self.dispatcher.dispatch("rpc.discover", ["bad"])
        self.assertEqual(ctx.exception.code, INVALID_PARAMS)

    def test_convert_missing_target_is_invalid_params(self) -> None:
        with self.assertRaises(RpcException) as ctx:
            self.dispatcher.dispatch(
                "sigma.convert",
                {"rule": "title: test\ndetection:\n  condition: true"},
            )
        self.assertEqual(ctx.exception.code, INVALID_PARAMS)

    def test_convert_success(self) -> None:
        result = self.dispatcher.dispatch(
            "sigma.convert",
            {
                "rule": "title: test\ndetection:\n  condition: true",
                "target": "splunk",
            },
        )
        self.assertEqual(result["target"], "splunk")
        self.assertIn("query", result)

    def test_discover_returns_expected_contract(self) -> None:
        result = self.dispatcher.dispatch("rpc.discover", {})
        self.assertIn("service", result)
        self.assertIn("version", result)
        self.assertIn("jsonrpc_endpoint", result)
        self.assertIn("methods", result)
        self.assertIn("sigma.convert", result["methods"])

    def test_pipelines_list_accepts_target(self) -> None:
        result = self.dispatcher.dispatch("sigma.pipelines.list", {"target": "splunk"})
        self.assertEqual(result["items"], ["splunk_windows"])
        self.assertEqual(self.engine.last_list_pipelines_target, "splunk")

    def test_convert_accepts_without_pipeline_flag(self) -> None:
        result = self.dispatcher.dispatch(
            "sigma.convert",
            {
                "rule": "title: test\ndetection:\n  condition: true",
                "target": "splunk",
                "without_pipeline": True,
            },
        )
        self.assertTrue(result["without_pipeline"])
        self.assertTrue(self.engine.last_without_pipeline)

    def test_convert_rejects_non_boolean_without_pipeline(self) -> None:
        with self.assertRaises(RpcException) as ctx:
            self.dispatcher.dispatch(
                "sigma.convert",
                {
                    "rule": "title: test\ndetection:\n  condition: true",
                    "target": "splunk",
                    "without_pipeline": "yes",
                },
            )
        self.assertEqual(ctx.exception.code, INVALID_PARAMS)


if __name__ == "__main__":
    unittest.main()
