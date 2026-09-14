import json
import tempfile
import unittest
from pathlib import Path

from src.state.poster_state import ModelConfig, TimingMetrics
from src.workflow.pipeline import save_timing_log
from utils.langgraph_utils import LangGraphAgent


class ModelCallTrackingTests(unittest.TestCase):
    def test_vision_failure_is_not_retried_as_text(self):
        agent = LangGraphAgent.__new__(LangGraphAgent)

        def fail_vision(messages):
            raise RuntimeError("vision endpoint unavailable")

        agent._step_vision = fail_vision
        message = json.dumps(
            [
                {"type": "text", "text": "analyze"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,AA=="},
                },
            ]
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "vision endpoint unavailable",
        ):
            agent.step(message)

    def test_metrics_distinguish_successful_and_failed_calls(self):
        metrics = TimingMetrics()
        metrics.add_api_call(
            "claim_writer",
            "text",
            10,
            5,
            model_provider="local_text",
            model_name="text-model",
        )
        metrics.add_api_call(
            "color_agent",
            "vision",
            0,
            0,
            success=False,
            error="connection refused",
            model_provider="local_vision",
            model_name="vision-model",
        )

        self.assertEqual(2, metrics.get_api_call_count())
        self.assertEqual(1, metrics.get_api_call_count(True))
        self.assertEqual(1, metrics.get_api_call_count(False))

        with tempfile.TemporaryDirectory() as temp_dir:
            report = save_timing_log(
                {
                    "output_dir": temp_dir,
                    "timing_metrics": metrics,
                    "text_model": ModelConfig(
                        "text-model",
                        "local_text",
                    ),
                    "vision_model": ModelConfig(
                        "vision-model",
                        "local_vision",
                    ),
                }
            )

            self.assertEqual(2, report["overall"]["total_api_calls"])
            self.assertEqual(1, report["overall"]["successful_api_calls"])
            self.assertEqual(1, report["overall"]["failed_api_calls"])
            self.assertEqual(2, report["model_info"]["attempted_model_count"])
            self.assertEqual(1, report["model_info"]["successful_model_count"])
            self.assertEqual(
                1,
                report["model_usage"][
                    "local_vision/vision-model"
                ]["failed"],
            )
            self.assertTrue(
                (Path(temp_dir) / "timing_cost_log.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
