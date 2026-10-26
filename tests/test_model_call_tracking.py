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

    def test_joint_timing_is_not_reported_as_skipped_verification_after_record_pruning(self):
        metrics = TimingMetrics(pipeline_start=1, pipeline_end=101)
        metrics.record_component('joint_preparation', 70)
        metrics.record_component('joint_preparation', 10)
        metrics.record_component('space_draft', 2)
        # The bounded recent-event list must not define cumulative totals.
        metrics.iteration_timings.clear()
        with tempfile.TemporaryDirectory() as directory:
            state = {'output_dir': directory, 'timing_metrics': metrics,
                'text_model': ModelConfig('text', 'local_text'),
                'vision_model': ModelConfig('vision', 'local_vision'),
                'generation_route': 'optimization_family', 'joint_preparation': True}
            report = save_timing_log(state)
            self.assertEqual(80, report['component_timing']['joint_preparation']['time_seconds'])
            self.assertEqual(2, report['component_timing']['space_draft']['time_seconds'])
            self.assertIsNone(report['component_timing']['claim_verifier']['time_seconds'])
            self.assertEqual('included_in_joint_preparation', report['component_timing']['claim_verifier']['timing_scope'])
            state['joint_preparation'] = False
            legacy = save_timing_log(state)
            self.assertNotIn('joint_preparation', legacy['component_timing'])
            self.assertEqual(0, legacy['component_timing']['claim_verifier']['time_seconds'])


if __name__ == "__main__":
    unittest.main()
