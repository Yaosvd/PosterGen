"""poster state management"""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, TypedDict


@dataclass
class ModelConfig:
    model_name: str
    provider: str
    temperature: float = 0.2
    max_tokens: int = 8192

    # None = use provider/environment default.
    # True/False = override thinking mode for this agent.
    enable_thinking: Optional[bool] = None

    # Whether ChatOpenAI-compatible models should be forced
    # to return a JSON object.
    json_mode: bool = True


@dataclass
class TokenUsage:
    input_text: int = 0
    output_text: int = 0
    input_vision: int = 0
    output_vision: int = 0

    def add_text(self, inp: int, out: int):
        self.input_text += inp
        self.output_text += out

    def add_vision(self, inp: int, out: int):
        self.input_vision += inp
        self.output_vision += out


@dataclass
class APICall:
    agent: str
    call_type: str
    input_tokens: int
    output_tokens: int
    timestamp: float


@dataclass
class TimingMetrics:
    pipeline_start: float = 0.0
    pipeline_end: float = 0.0
    parser_time: float = 0.0
    evidence_builder_time: float = 0.0
    visual_interpreter_time: float = 0.0
    narrative_planner_time: float = 0.0
    claim_writer_time: float = 0.0
    claim_verifier_time: float = 0.0
    curator_time: float = 0.0
    layout_optimizer_time: float = 0.0
    color_agent_time: float = 0.0
    font_agent_time: float = 0.0
    title_designer_time: float = 0.0
    renderer_time: float = 0.0
    api_calls: List[APICall] = field(default_factory=list)

    def add_api_call(self, agent: str, call_type: str, input_tokens: int, output_tokens: int):
        self.api_calls.append(APICall(
            agent=agent,
            call_type=call_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            timestamp=time.time()
        ))

    def get_total_time(self) -> float:
        if self.pipeline_start == 0.0 or self.pipeline_end == 0.0:
            return 0.0
        return round(self.pipeline_end - self.pipeline_start, 2)

    def get_api_call_count(self) -> int:
        return len(self.api_calls)

    def get_component_percentage(self, component_time: float) -> float:
        total = self.get_total_time()
        if total == 0:
            return 0.0
        return round((component_time / total) * 100, 2)


class PosterState(TypedDict):
    # core paths
    pdf_path: str
    output_dir: str
    poster_name: str

    # model configs
    text_model: ModelConfig
    vision_model: ModelConfig

    # processing results
    images: Optional[Dict[str, Any]]
    tables: Optional[Dict[str, Any]]
    narrative: Optional[Dict[str, str]]
    poster_plan: Optional[List[Dict[str, Any]]]
    poster_width: int
    poster_height: int
    wireframe_layout: Optional[List[Dict[str, Any]]]
    content_filled_layout: Optional[List[Dict[str, Any]]]
    final_layout: Optional[List[Dict[str, Any]]]

    # source/evidence layer
    raw_text: Optional[str]
    page_records: Optional[List[Dict[str, Any]]]
    section_chunks: Optional[List[Dict[str, Any]]]
    evidence_bank: Optional[Dict[str, Any]]
    academic_entities: Optional[Dict[str, Any]]

    # semantic planning layer
    visual_analysis: Optional[Dict[str, Any]]
    narrative_plan: Optional[Dict[str, Any]]
    poster_claims: Optional[Dict[str, Any]]
    verified_claims: Optional[Dict[str, Any]]
    verification_report: Optional[Dict[str, Any]]

    # compatibility with original PosterGen
    narrative_content: Optional[Dict[str, Any]]
    classified_visuals: Optional[Dict[str, Any]]
    structured_sections: Optional[Dict[str, Any]]
    story_board: Optional[Dict[str, Any]]
    curated_content: Optional[Dict[str, Any]]
    design_layout: Optional[List[Dict[str, Any]]]
    section_title_design: Optional[Dict[str, Any]]
    color_scheme: Optional[Dict[str, str]]
    keywords: Optional[Dict[str, Any]]
    styled_layout: Optional[List[Dict[str, Any]]]

    # poster assets
    url: str
    logo_path: str
    aff_logo_path: Optional[str]

    # metadata
    tokens: TokenUsage
    timing_metrics: TimingMetrics
    current_agent: str
    errors: List[str]

    # grounded academic generation
    strict_academic: bool
    reasoning_mode: str
    debug_evidence: bool
    verification_passed: bool
    claim_repair_count: int


def create_state(
    pdf_path: str,
    text_model: str = "gpt-4.1-2025-04-14",
    vision_model: str = "gpt-4.1-2025-04-14",
    width: int = 84,
    height: int = 42,
    url: str = "",
    logo_path: str = "",
    aff_logo_path: str = "",
    poster_name: Optional[str] = None,
    strict_academic: bool = True,
    reasoning_mode: str = "balanced",
    debug_evidence: bool = False,
) -> PosterState:
    """create initial poster state"""
    poster_name = poster_name or Path(pdf_path).parent.name or "test_poster"
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_dir = str(Path("output") / poster_name / run_timestamp)

    return PosterState(
        pdf_path=pdf_path,
        output_dir=output_dir,
        poster_name=poster_name,
        text_model=_get_model_config(text_model),
        vision_model=_get_model_config(vision_model),
        images=None,
        tables=None,
        narrative=None,
        poster_plan=None,
        poster_width=width,
        poster_height=height,
        wireframe_layout=None,
        content_filled_layout=None,
        final_layout=None,
        raw_text=None,
        page_records=None,
        section_chunks=None,
        evidence_bank=None,
        academic_entities=None,
        visual_analysis=None,
        narrative_plan=None,
        poster_claims=None,
        verified_claims=None,
        verification_report=None,

        narrative_content=None,
        classified_visuals=None,
        structured_sections=None,
        story_board=None,
        curated_content=None,
        design_layout=None,
        section_title_design=None,
        color_scheme=None,
        keywords=None,
        styled_layout=None,
        url=url,
        logo_path=logo_path,
        aff_logo_path=aff_logo_path,
        tokens=TokenUsage(),
        timing_metrics=TimingMetrics(),
        current_agent="init",
        errors=[],
        strict_academic=strict_academic,
        reasoning_mode=reasoning_mode,
        debug_evidence=debug_evidence,
        verification_passed=False,
        claim_repair_count=0
    )


def _get_model_config(model_id: str) -> ModelConfig:
    """get model configuration"""
    local_text_model = os.getenv("LOCAL_TEXT_MODEL", "qwen3.8-27b")
    local_vision_model = os.getenv("LOCAL_VISION_MODEL", "qwen3-vl-30b-a3b")

    try:
        local_max_tokens = int(os.getenv("LOCAL_MAX_TOKENS", "32768"))
    except ValueError as exc:
        raise ValueError("LOCAL_MAX_TOKENS must be an integer") from exc
    if local_max_tokens <= 0:
        raise ValueError("LOCAL_MAX_TOKENS must be greater than zero")

    local_text_aliases = {
        "local-text",
        "Qwen3.8-27B",
        "qwen3.8-27b",
        local_text_model,
    }
    if model_id in local_text_aliases:
        return ModelConfig(local_text_model, "local_text", max_tokens=local_max_tokens)
    if model_id in {"local-vision", "qwen3-vl-30b-a3b", local_vision_model}:
        return ModelConfig(local_vision_model, "local_vision", max_tokens=local_max_tokens)

    configs = {
        "claude": ModelConfig("claude-sonnet-4-20250514", "anthropic"),
        "claude-sonnet-4-20250514": ModelConfig("claude-sonnet-4-20250514", "anthropic"),
        "claude-opus-4.5": ModelConfig("claude-opus-4-5-20251101", "anthropic"),
        "claude-opus-4-5-20251101": ModelConfig("claude-opus-4-5-20251101", "anthropic"),
        "gemini": ModelConfig("gemini-2.5-pro", "google"),
        "gemini-2.5-pro": ModelConfig("gemini-2.5-pro", "google"),
        "gpt-4o-2024-08-06": ModelConfig("gpt-4o-2024-08-06", "openai"),
        "gpt-4.1-2025-04-14": ModelConfig("gpt-4.1-2025-04-14", "openai"),
        "gpt-4.1-mini-2025-04-14": ModelConfig("gpt-4.1-mini-2025-04-14", "openai"),
        "glm-4.6": ModelConfig("glm-4.6", "zhipu"),
        "glm-4.6v": ModelConfig("glm-4.6v", "zhipu"),
        "glm-4.5": ModelConfig("glm-4.5", "zhipu"),
        "glm-4.5-air": ModelConfig("glm-4.5-air", "zhipu"),
        "glm-4.5v": ModelConfig("glm-4.5v", "zhipu"),
        "glm-4": ModelConfig("glm-4", "zhipu"),
        "glm-4v": ModelConfig("glm-4v", "zhipu"),
        "kimi-k2-turbo-preview": ModelConfig("kimi-k2-turbo-preview", "moonshot"),
        "moonshot-v1-8k-vision-preview": ModelConfig("moonshot-v1-8k-vision-preview", "moonshot"),
        "MiniMax-M2": ModelConfig("MiniMax-M2", "Minimax"),
        "qwen3-max": ModelConfig("qwen3-max", "Alibaba"),
        "qwen3-vl-plus": ModelConfig("qwen3-vl-plus", "Alibaba"),
    }
    return configs.get(model_id, configs["gpt-4.1-2025-04-14"])
