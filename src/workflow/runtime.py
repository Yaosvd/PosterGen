"""Project-local console/timing utilities; no classic workflow imports."""
import os
import sys
import re
import json
import time
from pathlib import Path
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from typing import TextIO, Callable
from dotenv import load_dotenv
from src.state.poster_state import PosterState
from utils.src.logging_utils import log_agent_info, log_agent_success, log_agent_error

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Only this project's optional credentials/configuration, never the source tree.
load_dotenv(PROJECT_ROOT / '.env', override=True)


def activate_project():
    """Bind relative fonts/prompts/output/storage to this independent project."""
    os.chdir(PROJECT_ROOT)


class TeeStream:
    """Write console output to both the original stream and a run log."""

    def __init__(self, console_stream: TextIO, log_stream: TextIO):
        self.console_stream = console_stream
        self.log_stream = log_stream

    def write(self, data: str) -> int:
        self.console_stream.write(data)
        self.log_stream.write(re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", data))
        return len(data)

    def flush(self):
        self.console_stream.flush()
        self.log_stream.flush()

    def isatty(self) -> bool:
        return self.console_stream.isatty()



@contextmanager
def tee_console_output(log_path: Path):
    """Mirror stdout and stderr into a line-buffered UTF-8 log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8", buffering=1) as log_file:
        stdout = TeeStream(sys.stdout, log_file)
        stderr = TeeStream(sys.stderr, log_file)
        with redirect_stdout(stdout), redirect_stderr(stderr):
            yield



def create_timing_wrapper(node_func: Callable, component_name: str) -> Callable:
    """Wrap agent node with timing tracking"""
    def wrapper(state: PosterState) -> PosterState:
        start_time = time.time()
        result = node_func(state)
        end_time = time.time()
        elapsed = round(end_time - start_time, 2)

        if component_name == "parser":
            result["timing_metrics"].parser_time = elapsed
        elif component_name == "evidence_builder":
            result["timing_metrics"].evidence_builder_time = elapsed
        elif component_name == "narrative_planner":
            result["timing_metrics"].narrative_planner_time = elapsed
        elif component_name == "claim_writer":
            result["timing_metrics"].claim_writer_time = elapsed
        elif component_name == "claim_verifier":
            result["timing_metrics"].claim_verifier_time = elapsed
        elif component_name == "curator":
            result["timing_metrics"].curator_time = elapsed
        elif component_name == "layout_optimizer":
            result["timing_metrics"].layout_optimizer_time = elapsed
        elif component_name == "color_agent":
            result["timing_metrics"].color_agent_time = elapsed
        elif component_name == "font_agent":
            result["timing_metrics"].font_agent_time = elapsed
        elif component_name == "section_title_designer":
            result["timing_metrics"].title_designer_time = elapsed
        elif component_name == "renderer":
            result["timing_metrics"].renderer_time = elapsed
        elif component_name == "critic":
            result["timing_metrics"].critic_time = elapsed

        return result
    return wrapper



def save_timing_log(state: PosterState):
    """Save timing and cost metrics to log file"""
    output_dir = Path(state["output_dir"])
    log_path = output_dir / "timing_cost_log.json"

    metrics = state["timing_metrics"]
    total_time = metrics.get_total_time()

    api_calls_by_agent = {}
    model_usage = {}
    total_input_tokens = 0
    total_output_tokens = 0

    for call in metrics.api_calls:
        if call.agent not in api_calls_by_agent:
            api_calls_by_agent[call.agent] = {
                "count": 0,
                "successful": 0,
                "failed": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "calls": []
            }
        api_calls_by_agent[call.agent]["count"] += 1
        status_key = (
            "successful"
            if call.success
            else "failed"
        )
        api_calls_by_agent[call.agent][status_key] += 1
        api_calls_by_agent[call.agent]["input_tokens"] += call.input_tokens
        api_calls_by_agent[call.agent]["output_tokens"] += call.output_tokens
        api_calls_by_agent[call.agent]["calls"].append({
            "type": call.call_type,
            "success": call.success,
            "model_provider": call.model_provider,
            "model_name": call.model_name,
            "input_tokens": call.input_tokens,
            "output_tokens": call.output_tokens,
            "timestamp": call.timestamp,
            "error": call.error,
        })

        model_key = (
            f"{call.model_provider}/{call.model_name}"
            if call.model_provider and call.model_name
            else "unknown"
        )
        if model_key not in model_usage:
            model_usage[model_key] = {
                "count": 0,
                "successful": 0,
                "failed": 0,
                "text": 0,
                "vision": 0,
            }
        model_usage[model_key]["count"] += 1
        model_usage[model_key][status_key] += 1
        if call.call_type in {"text", "vision"}:
            model_usage[model_key][call.call_type] += 1

        total_input_tokens += call.input_tokens
        total_output_tokens += call.output_tokens

    log_data = {
        "overall": {
            "total_runtime_seconds": total_time,
            "total_runtime_minutes": round(total_time / 60, 2),
            "total_api_calls": metrics.get_api_call_count(),
            "successful_api_calls": metrics.get_api_call_count(True),
            "failed_api_calls": metrics.get_api_call_count(False),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens
        },
        "component_timing": {
            "parser": {
                "time_seconds": round(metrics.parser_time, 2),
                "percentage": metrics.get_component_percentage(metrics.parser_time)
            },
            "evidence_builder": {
                "time_seconds": round(metrics.evidence_builder_time, 2),
                "percentage": metrics.get_component_percentage(
                    metrics.evidence_builder_time
                )
            },
            "narrative_planner": {
                "time_seconds": round(metrics.narrative_planner_time, 2),
                "percentage": metrics.get_component_percentage(
                    metrics.narrative_planner_time
                )
            },
            "claim_writer": {
                "time_seconds": round(metrics.claim_writer_time, 2),
                "percentage": metrics.get_component_percentage(
                    metrics.claim_writer_time
                )
            },
            "claim_verifier": {
                "time_seconds": round(metrics.claim_verifier_time, 2),
                "percentage": metrics.get_component_percentage(
                    metrics.claim_verifier_time
                )
            },
            "curator": {
                "time_seconds": round(metrics.curator_time, 2),
                "percentage": metrics.get_component_percentage(metrics.curator_time)
            },
            "layout_optimizer": {
                "time_seconds": round(metrics.layout_optimizer_time, 2),
                "percentage": metrics.get_component_percentage(metrics.layout_optimizer_time)
            },
            "color_agent": {
                "time_seconds": round(metrics.color_agent_time, 2),
                "percentage": metrics.get_component_percentage(metrics.color_agent_time)
            },
            "font_agent": {
                "time_seconds": round(metrics.font_agent_time, 2),
                "percentage": metrics.get_component_percentage(metrics.font_agent_time)
            },
            "title_designer": {
                "time_seconds": round(metrics.title_designer_time, 2),
                "percentage": metrics.get_component_percentage(metrics.title_designer_time)
            },
            "renderer": {
                "time_seconds": round(metrics.renderer_time, 2),
                "percentage": metrics.get_component_percentage(metrics.renderer_time)
            },
            "critic": {
                "time_seconds": round(metrics.critic_time, 2),
                "percentage": metrics.get_component_percentage(metrics.critic_time)
            }
        },
        "iteration_timing": metrics.iteration_timings,
        "api_calls_by_agent": api_calls_by_agent,
        "model_usage": model_usage,
        "model_info": {
            "text_model": f"{state['text_model'].provider}/{state['text_model'].model_name}",
            "vision_model": f"{state['vision_model'].provider}/{state['vision_model'].model_name}",
            "configured_model_count": len({
                (
                    state["text_model"].provider,
                    state["text_model"].model_name,
                ),
                (
                    state["vision_model"].provider,
                    state["vision_model"].model_name,
                ),
            }),
            "attempted_model_count": len(model_usage),
            "successful_model_count": sum(
                usage["successful"] > 0
                for usage in model_usage.values()
            ),
        }
    }

    if state.get('generation_route') == 'optimization_family':
        # Nested details, not additional top-level stages. These metrics cover
        # this process execution, including failed/retried physical requests;
        # historical journal totals may span earlier executions after resume.
        content = metrics.critic_content_request_time
        visual = metrics.critic_visual_request_time
        log_data['component_timing']['critic'].update(
            timing_scope='outer_stage_wall_time',
            breakdown={
                'content_model_requests_seconds': round(content, 3),
                'visual_model_requests_seconds': round(visual, 3),
                'local_processing_and_retry_wait_seconds': round(
                    max(0.0, metrics.critic_time - content - visual), 3),
            },
            breakdown_scope='included_in_critic; current_execution; model_invoke_wall_time')
        from utils.model_requests import summarize
        log_data['model_request_attempts'] = summarize(state['output_dir'])
        if state.get('joint_preparation'):
            for component in ('space_draft', 'joint_preparation', 'install_joint_candidate'):
                elapsed = getattr(metrics, component+'_time')
                log_data['component_timing'][component] = {
                    'time_seconds': round(elapsed, 2),
                    'percentage': metrics.get_component_percentage(elapsed),
                    'timing_scope': 'outer_stage_wall_time',
                }
            log_data['component_timing']['joint_preparation']['includes'] = [
                'family_search', 'bounded_edits', 'scientific_verification', 'verified_text_refit']
            # Verification runs inside joint preparation; zero would falsely
            # imply it was skipped. Physical per-request times remain journaled.
            log_data['component_timing']['claim_verifier'].update(
                time_seconds=None, percentage=None, timing_scope='included_in_joint_preparation')
            log_data['component_timing']['layout_optimizer']['timing_scope'] = 'adopted_candidate_compilation'
        if state.get('editorial_version') == 'poster_editorial_v1':
            log_data['content_contract'] = 'poster_editorial_v1'
            log_data['reading_policy'] = 'curator_owned_positions'
            for retired in ('evidence_builder','narrative_planner','claim_writer','claim_verifier','space_draft','install_joint_candidate'):
                log_data['component_timing'].pop(retired, None)
            elapsed = metrics.joint_preparation_time
            joint = log_data['component_timing'].setdefault('joint_preparation', {
                'time_seconds':round(elapsed, 2),
                'percentage':metrics.get_component_percentage(elapsed)})
            joint.update(
                includes=['measured_geometry','bounded_expansion_compression','freeze_current_outcome'] if elapsed else [],
                timing_scope='measured_editorial_preparation' if elapsed else 'not_started')
            for component in ('source_balancer',):
                elapsed=getattr(metrics,component+'_time')
                log_data['component_timing'][component]={
                    'time_seconds':round(elapsed,2),'percentage':metrics.get_component_percentage(elapsed),
                    'timing_scope':'included_in_joint_preparation'}
        if state.get('source_editorial_version') == 'source_editorial_v1':
            log_data['content_contract'] = 'sample_body_source_v1'
            log_data['reading_policy'] = 'visual_natural_reading_v1'
            for retired in ('evidence_builder', 'claim_writer', 'space_draft', 'install_joint_candidate'):
                log_data['component_timing'].pop(retired, None)
            for component in ('source_document', 'source_balancer', 'source_preview', 'source_install'):
                elapsed = getattr(metrics, component+'_time')
                log_data['component_timing'][component] = {
                    'time_seconds': round(elapsed,2), 'percentage': metrics.get_component_percentage(elapsed),
                    'timing_scope': 'included_in_joint_preparation' if component in {'source_balancer','source_preview'} else 'outer_stage_wall_time'}
            log_data['component_timing']['claim_verifier'].update(
                time_seconds=round(metrics.claim_verifier_time,2),
                percentage=metrics.get_component_percentage(metrics.claim_verifier_time),
                timing_scope='included_in_joint_preparation')



    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2)

    log_agent_success("pipeline", f"Timing log saved to: {log_path}")
    return log_data

