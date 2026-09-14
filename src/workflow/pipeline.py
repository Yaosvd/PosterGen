"""
Main workflow pipeline for paper-to-poster generation
"""

import argparse
import os
import sys
import json
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Callable, TextIO

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# langgraph imports
from langgraph.graph import StateGraph, START, END

from src.state.poster_state import create_state, PosterState
from src.agents.parser import parser_node
from src.agents.evidence_builder import evidence_builder_node
from src.agents.narrative_planner import narrative_planner_node
from src.agents.claim_writer import claim_writer_node
from src.agents.claim_verifier import claim_verifier_node
from src.agents.grounded_curator import grounded_curator_node
from src.agents.layout_with_balancer import layout_with_balancer_node as layout_optimizer_node
from src.agents.section_title_designer import section_title_designer_node
from src.agents.color_agent import color_agent_node
from src.agents.font_agent import font_agent_node
from src.agents.renderer import renderer_node
from utils.src.logging_utils import log_agent_info, log_agent_success, log_agent_error

env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)


class TeeStream:
    """Write console output to both the original stream and a run log."""

    def __init__(self, console_stream: TextIO, log_stream: TextIO):
        self.console_stream = console_stream
        self.log_stream = log_stream

    def write(self, data: str) -> int:
        self.console_stream.write(data)
        self.log_stream.write(data)
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

        return result
    return wrapper

def create_workflow_graph() -> StateGraph:
    """Create the grounded academic poster workflow."""

    graph = StateGraph(PosterState)

    # --------------------------------------------------------
    # Scientific content pipeline
    # --------------------------------------------------------

    graph.add_node(
        "parser",
        create_timing_wrapper(
            parser_node,
            "parser",
        ),
    )

    graph.add_node(
        "evidence_builder",
        create_timing_wrapper(
            evidence_builder_node,
            "evidence_builder",
        ),
    )

    graph.add_node(
        "narrative_planner",
        create_timing_wrapper(
            narrative_planner_node,
            "narrative_planner",
        ),
    )

    graph.add_node(
        "claim_writer",
        create_timing_wrapper(
            claim_writer_node,
            "claim_writer",
        ),
    )

    graph.add_node(
        "claim_verifier",
        create_timing_wrapper(
            claim_verifier_node,
            "claim_verifier",
        ),
    )

    # GroundedCurator may arrange claims but cannot rewrite
    # the verified scientific text.
    graph.add_node(
        "curator",
        create_timing_wrapper(
            grounded_curator_node,
            "curator",
        ),
    )

    # --------------------------------------------------------
    # Existing visual design pipeline
    # --------------------------------------------------------

    graph.add_node(
        "color_agent",
        create_timing_wrapper(
            color_agent_node,
            "color_agent",
        ),
    )

    graph.add_node(
        "section_title_designer",
        create_timing_wrapper(
            section_title_designer_node,
            "section_title_designer",
        ),
    )

    graph.add_node(
        "layout_optimizer",
        create_timing_wrapper(
            layout_optimizer_node,
            "layout_optimizer",
        ),
    )

    graph.add_node(
        "font_agent",
        create_timing_wrapper(
            font_agent_node,
            "font_agent",
        ),
    )

    graph.add_node(
        "renderer",
        create_timing_wrapper(
            renderer_node,
            "renderer",
        ),
    )

    # --------------------------------------------------------
    # Graph
    #
    # Parser
    #   -> Evidence
    #   -> Narrative
    #   -> Claims
    #   -> Verification
    #   -> Grounded curation
    #   -> Existing design pipeline
    # --------------------------------------------------------

    graph.add_edge(
        START,
        "parser",
    )

    graph.add_edge(
        "parser",
        "evidence_builder",
    )

    graph.add_edge(
        "evidence_builder",
        "narrative_planner",
    )

    graph.add_edge(
        "narrative_planner",
        "claim_writer",
    )

    graph.add_edge(
        "claim_writer",
        "claim_verifier",
    )

    graph.add_edge(
        "claim_verifier",
        "curator",
    )

    graph.add_edge(
        "curator",
        "color_agent",
    )

    graph.add_edge(
        "color_agent",
        "section_title_designer",
    )

    graph.add_edge(
        "section_title_designer",
        "layout_optimizer",
    )

    graph.add_edge(
        "layout_optimizer",
        "font_agent",
    )

    graph.add_edge(
        "font_agent",
        "renderer",
    )

    graph.add_edge(
        "renderer",
        END,
    )

    return graph

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
            }
        },
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

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2)

    log_agent_success("pipeline", f"Timing log saved to: {log_path}")
    return log_data


def main():
    parser = argparse.ArgumentParser(description="PosterGen: Multi-agent Aesthetic-aware Paper-to-poster generation")
    parser.add_argument("--paper_path", type=str, required=True, help="Path to the PDF paper")
    default_text_model = (
        "local-text"
        if os.getenv("LOCAL_TEXT_BASE_URL")
        else "gpt-4o-2024-08-06"
    )
    default_vision_model = (
        "local-vision"
        if os.getenv("LOCAL_VISION_BASE_URL")
        else "gpt-4o-2024-08-06"
    )
    parser.add_argument("--text_model", type=str, default=default_text_model,
                        help="Text model for content processing")
    parser.add_argument("--vision_model", type=str, default=default_vision_model,
                        help="Vision model for image analysis")
    parser.add_argument("--poster_width", type=float, default=54, help="Poster width in inches")
    parser.add_argument("--poster_height", type=float, default=36, help="Poster height in inches")
    parser.add_argument("--url", type=str, help="URL for QR code on poster") # TODO
    parser.add_argument("--logo", type=str, default=None, help="Path to conference/journal logo (default: auto-detect logo.png next to paper.pdf)")
    parser.add_argument("--aff_logo", type=str, default=None, help="Path to affiliation logo (default: auto-detect aff.png next to paper.pdf)")
    
    args = parser.parse_args()

    # Auto-detect logo paths from the paper directory when not explicitly provided
    paper_dir = os.path.dirname(os.path.abspath(args.paper_path))

    if not args.logo:
        candidate_logo = os.path.join(paper_dir, "logo.png")
        if os.path.exists(candidate_logo):
            args.logo = candidate_logo

    if not args.aff_logo:
        candidate_aff = os.path.join(paper_dir, "aff.png")
        if os.path.exists(candidate_aff):
            args.aff_logo = candidate_aff
    
    # poster dimensions: fix width to 54", adjust height by ratio
    input_ratio = args.poster_width / args.poster_height
    # check poster ratio: lower bound 1.4 (ISO A paper size), upper bound 2 (human vision limit)
    if input_ratio > 2 or input_ratio < 1.4:
        print(f"❌ Poster ratio is out of range: {input_ratio}. Please use a ratio between 1.4 and 2.")
        return 1
    
    final_width = 54.0
    final_height = final_width / input_ratio
    
    # check api keys
    required_keys = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "google": "GOOGLE_API_KEY", "zhipu": "ZHIPU_API_KEY", "moonshot": "MOONSHOT_API_KEY", "Minimax": "MINIMAX_API_KEY", "Alibaba": "ALIBABA_API_KEY"}
    model_providers = {"claude-sonnet-4-20250514": "anthropic", "claude-opus-4.5": "anthropic", "claude-opus-4-5-20251101": "anthropic", "gemini": "google", "gemini-2.5-pro": "google",
                      "gpt-4o-2024-08-06": "openai", "gpt-4.1-2025-04-14": "openai", "gpt-4.1-mini-2025-04-14": "openai",
                      "glm-4.6": "zhipu", "glm-4.6v": "zhipu", "glm-4.5": "zhipu", "glm-4.5-air": "zhipu", "glm-4.5v": "zhipu", "glm-4": "zhipu", "glm-4v": "zhipu",
                      "kimi-k2-turbo-preview": "moonshot", "moonshot-v1-8k-vision-preview": "moonshot",
                      "qwen3-max": "Alibaba", "qwen3-vl-plus": "Alibaba", "Qwen3.8-27B": "Alibaba",
                      "MiniMax-M2":"Minimax",}
    
    needed_keys = set()
    if args.text_model in model_providers:
        needed_keys.add(required_keys[model_providers[args.text_model]])
    if args.vision_model in model_providers:
        needed_keys.add(required_keys[model_providers[args.vision_model]])
    
    missing = [k for k in needed_keys if not os.getenv(k)]
    if missing:
        print(f"❌ Missing API keys: {missing}")
        return 1
    
    # get pdf path
    pdf_path = args.paper_path
    if not pdf_path or not Path(pdf_path).exists():
        print("❌ PDF not found")
        return 1
    
    state = create_state(
        pdf_path, args.text_model, args.vision_model,
        final_width, final_height,
        args.url, args.logo, args.aff_logo,
    )
    run_log_path = Path(state["output_dir"]) / "run.log"

    with tee_console_output(run_log_path):
        if env_path.exists():
            print(f"✅ .env file found at: {env_path}")
        else:
            print("ℹ️ .env file not found; using shell environment variables")

        print(f"🚀 PosterGen Pipeline")
        print(f"📄 PDF: {pdf_path}")
        print(f"🤖 Models: {args.text_model}/{args.vision_model}")
        print(
            "🧠 Reasoning policy: per-agent "
            "(config/agent_policy.yaml)"
        )
        print(f"🔢 Text max tokens: {state['text_model'].max_tokens}")
        print(f"📏 Size: {final_width}\" × {final_height:.2f}\"")
        print(f"🏢 Conference Logo: {args.logo}")
        print(f"🏫 Affiliation Logo: {args.aff_logo}")
        print(f"📝 Run log: {run_log_path}")

        try:

            state["timing_metrics"].pipeline_start = time.time()

            log_agent_info("pipeline", "creating workflow graph")
            graph = create_workflow_graph()
            workflow = graph.compile()

            log_agent_info("pipeline", "executing workflow")
            final_state = workflow.invoke(state)

            final_state["timing_metrics"].pipeline_end = time.time()

            if final_state.get("errors"):
                log_agent_error("pipeline", f"Pipeline errors: {final_state['errors']}")
                return 1
            required_outputs = [
                "evidence_bank",
                "narrative_plan",
                "poster_claims",
                "verified_claims",
                "verification_report",
                "story_board",
                "design_layout",
                "color_scheme",
                "styled_layout",
            ]
            missing = [out for out in required_outputs if not final_state.get(out)]
            if missing:
                log_agent_error("pipeline", f"Missing outputs: {missing}")
                return 1

            log_agent_success("pipeline", "Pipeline completed successfully")
            log_agent_success("pipeline", "Full pipeline complete")

            timing_log = save_timing_log(final_state)
            total_time = timing_log["overall"]["total_runtime_seconds"]
            total_calls = timing_log["overall"]["total_api_calls"]

            log_agent_info("pipeline", f"Total runtime: {total_time}s ({total_time/60:.2f} minutes)")
            log_agent_info("pipeline", f"Total API calls: {total_calls}")
            log_agent_info("pipeline", f"Total tokens: {final_state['tokens'].input_text} → {final_state['tokens'].output_text}")

            output_path = Path(final_state["output_dir"]) / f"{final_state['poster_name']}.pptx"
            log_agent_info("pipeline", f"Final poster saved to: {output_path}")

            return 0

        except Exception as e:
            log_agent_error("pipeline", f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())
