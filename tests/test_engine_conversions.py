import subprocess
import unittest

from app.config import Settings
from app.engine import SigmaEngine
from app.errors import SigmaEngineException, SigmaInputException


RULE_TEXT = "title: Rule\ndetection:\n  condition: true\n"


class StubSigmaEngine(SigmaEngine):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.next_result = subprocess.CompletedProcess(
            args=["sigma"], returncode=0, stdout="index=*", stderr=""
        )
        self.last_args = None

    def _run_sigma(self, args, **kwargs):  # type: ignore[override]
        self.last_args = list(args)
        return self.next_result


class EngineConversionsTests(unittest.TestCase):
    def test_convert_adds_without_pipeline_when_requested(self) -> None:
        settings = Settings(SIGMA_ALLOWED_BACKENDS="splunk,eql")
        engine = StubSigmaEngine(settings)

        result = engine.convert_rule(RULE_TEXT, target="splunk", without_pipeline=True)

        self.assertEqual(result["target"], "splunk")
        self.assertTrue(result["without_pipeline"])
        self.assertIn("--without-pipeline", engine.last_args)

    def test_convert_includes_pipeline_and_format(self) -> None:
        settings = Settings(
            SIGMA_ALLOWED_BACKENDS="splunk", SIGMA_ALLOWED_PIPELINES="windows"
        )
        engine = StubSigmaEngine(settings)

        result = engine.convert_rule(
            RULE_TEXT,
            target="splunk",
            pipeline="windows",
            output_format="default",
        )

        self.assertEqual(result["pipeline"], "windows")
        self.assertEqual(result["format"], "default")
        self.assertIn("-p", engine.last_args)
        self.assertIn("windows", engine.last_args)
        self.assertIn("-f", engine.last_args)
        self.assertIn("default", engine.last_args)

    def test_convert_rejects_disallowed_backend(self) -> None:
        settings = Settings(SIGMA_ALLOWED_BACKENDS="splunk")
        engine = StubSigmaEngine(settings)

        with self.assertRaises(SigmaInputException):
            engine.convert_rule(RULE_TEXT, target="eql")

    def test_convert_rejects_disallowed_pipeline(self) -> None:
        settings = Settings(
            SIGMA_ALLOWED_BACKENDS="splunk", SIGMA_ALLOWED_PIPELINES="windows"
        )
        engine = StubSigmaEngine(settings)

        with self.assertRaises(SigmaInputException):
            engine.convert_rule(RULE_TEXT, target="splunk", pipeline="linux")

    def test_convert_rejects_empty_conversion_output(self) -> None:
        settings = Settings(SIGMA_ALLOWED_BACKENDS="splunk")
        engine = StubSigmaEngine(settings)
        engine.next_result = subprocess.CompletedProcess(
            args=["sigma"], returncode=0, stdout="   ", stderr=""
        )

        with self.assertRaises(SigmaEngineException):
            engine.convert_rule(RULE_TEXT, target="splunk")


if __name__ == "__main__":
    unittest.main()
