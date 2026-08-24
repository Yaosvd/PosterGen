"""
spatial content planning and story board curation
"""

import json
from pathlib import Path
from typing import Dict, Any, List

from src.state.poster_state import PosterState
from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt
from utils.src.logging_utils import log_agent_info, log_agent_success, log_agent_error, log_agent_warning
from src.config.poster_config import load_config
from jinja2 import Template

class StoryBoardCurator:
    """creates spatial content plan and story board"""
    
    def __init__(self):
        self.name = "spatial_content_planner"
        self.spatial_planning_prompt = load_prompt("config/prompts/spatial_content_planner.txt")
        self.config = load_config()
        self.validation_config = self.config["validation"]
        self.utilization_config = self.config["utilization_thresholds"]

    def __call__(self, state: PosterState) -> PosterState:
        log_agent_info(self.name, "creating spatial content plan")
        
        try:
            structured_sections = state.get("structured_sections")
            narrative_content = state.get("narrative_content")
            classified_visuals = state.get("classified_visuals")

            if not structured_sections:
                log_agent_error(self.name, "missing structured_sections from parser")
                raise ValueError("missing structured_sections from parser")
            if not narrative_content:
                log_agent_error(self.name, "missing narrative_content from parser")
                raise ValueError("missing narrative_content from parser")
            if not classified_visuals:
                log_agent_error(self.name, "missing classified_visuals from parser")
                raise ValueError("missing classified_visuals from parser")
            
            # prepare visual height context for spatial planning
            visual_context = self._prepare_visual_context_for_curator(state)
            
            story_board, inp, out = self._create_story_board(
                structured_sections, narrative_content, classified_visuals,
                state.get("images", {}), state.get("tables", {}),
                visual_context, state["text_model"], state
            )
            state["tokens"].add_text(inp, out)
            
            # validate height distribution
            validation_result = self._validate_height_distribution(story_board, visual_context)
            if validation_result["warnings"]:
                log_agent_warning(self.name, f"height validation warnings: {validation_result['warnings']}")
            log_agent_info(self.name, f"column utilizations: {validation_result['column_utilizations']}")
            
            state["story_board"] = story_board
            state["current_agent"] = self.name
            
            self._save_story_board(state)
            
            # log story board summary
            sections = story_board.get("spatial_content_plan", {}).get("sections", [])
            total_visuals = sum(len(section.get("visual_assets", [])) for section in sections)
            
            log_agent_success(self.name, f"created story board with {len(sections)} sections")
            log_agent_success(self.name, f"selected {total_visuals} visual assets")

        except Exception as e:
            log_agent_error(self.name, f"failed: {e}")
            state["errors"].append(f"{self.name}: {e}")
            
        return state

    def _create_story_board(self, structured_sections, narrative_content, classified_visuals, images, tables, visual_context, config, state):
        log_agent_info(self.name, "generating spatial content plan")
        agent = LangGraphAgent("expert spatial poster designer", config, state, "curator")
        
        template_data = {
            "structured_sections": json.dumps(structured_sections, indent=2),
            "narrative_content": json.dumps(narrative_content, indent=2),
            "classified_visuals": json.dumps(classified_visuals, indent=2),
            "available_images": json.dumps({k: {"caption": v.get("caption", ""), "aspect": v.get("aspect", 1.0)} 
                                          for k, v in images.items()}, indent=2),
            "available_tables": json.dumps({k: {"caption": v.get("caption", ""), "aspect": v.get("aspect", 1.0)} 
                                          for k, v in tables.items()}, indent=2),
            "available_height_per_column": visual_context["available_height_per_column"],
            "visual_heights_info": json.dumps(visual_context["visual_assets_heights"], indent=2)
        }
        
        strict_constraint = """

CRITICAL INSTRUCTION: You MUST output a strictly valid JSON object. 
The outermost structure MUST be a dictionary containing the root key "spatial_content_plan".
DO NOT output a raw list. DO NOT add markdown code blocks (like ```json) or any conversational text. 
Your response must start with { and end with }.
Correct format strictly required: 
{
    "spatial_content_plan": {
        "sections": [
            {
                "section_id": "...",
                "section_title": "...",
                "column_assignment": "left",
                "vertical_priority": "top",
                "text_content": ["...", "..."],
                "visual_assets": [
                    {
                        "visual_id": "..."
                    }
                ]
            }
        ]
    }
}"""

        max_attempts = self.validation_config["max_llm_attempts"]
        last_raw_json = None
        last_inp, last_out = 0, 0

        for attempt in range(max_attempts):
            try:
                base_prompt = Template(self.spatial_planning_prompt).render(**template_data)
                prompt = base_prompt + strict_constraint
                
                agent.reset()
                response = agent.step(prompt)
                last_inp, last_out = getattr(response, 'input_tokens', 0), getattr(response, 'output_tokens', 0)
                
                story_board = extract_json(response.content)
                last_raw_json = story_board
                
                if self._validate_story_board(story_board, classified_visuals, visual_context):
                    log_agent_success(self.name, f"successfully created story board on attempt {attempt + 1}")
                    return story_board, last_inp, last_out
                else:
                    log_agent_warning(self.name, f"attempt {attempt + 1}: validation failed, retrying")
                    
            except Exception as e:
                log_agent_warning(self.name, f"story board attempt {attempt + 1} failed: {e}")

        # 当 3 次尝试均未完美通过验证时，启动智能修复/兜底接管，绝不抛出 Exception！
        log_agent_warning(self.name, "Validation failed after max attempts, executing repair & hard fallback...")
        repaired_board = self._repair_or_fallback_story_board(last_raw_json, state, classified_visuals)
        return repaired_board, last_inp, last_out
    
    def _repair_or_fallback_story_board(self, raw_board: Any, state: PosterState, classified_visuals: Dict) -> Dict:
        """智能修复大模型吐出的 JSON 结构，或直接使用 Parser 提取的内容硬接管兜底"""
        
        # 1. 尝试结构自动修复 (Auto-Repair)
        if raw_board:
            # 如果模型直接返回了 list，自动包一层
            if isinstance(raw_board, list):
                raw_board = {"spatial_content_plan": {"sections": raw_board}}
            
            # 如果模型返回了 dict 但缺失顶级键
            if isinstance(raw_board, dict):
                if "spatial_content_plan" not in raw_board:
                    if "sections" in raw_board:
                        raw_board = {"spatial_content_plan": {"sections": raw_board["sections"]}}
                    else:
                        raw_board = {"spatial_content_plan": {"sections": [raw_board]}}
                
                scp = raw_board.get("spatial_content_plan", {})
                if isinstance(scp, list):
                    raw_board["spatial_content_plan"] = {"sections": scp}
                    scp = raw_board["spatial_content_plan"]

                sections = scp.get("sections", [])
                if isinstance(sections, list) and len(sections) > 0:
                    repaired_sections = []
                    cols = ["left", "middle", "right"]
                    
                    for i, sec in enumerate(sections):
                        if not isinstance(sec, dict):
                            continue
                        
                        sec_id = sec.get("section_id", f"sec_{i+1}")
                        sec_title = sec.get("section_title", sec.get("title", f"Section {i+1}"))
                        
                        # 截断超长标题（防止超过 4 个词）
                        title_words = str(sec_title).split()
                        if len(title_words) > 4:
                            sec_title = " ".join(title_words[:4])
                            
                        col = sec.get("column_assignment", cols[i % 3])
                        if col not in cols:
                            col = cols[i % 3]
                            
                        prio = sec.get("vertical_priority", "middle")
                        if prio not in ["top", "middle", "bottom"]:
                            prio = "middle"
                            
                        text_content = sec.get("text_content", ["Key research findings."])
                        if not isinstance(text_content, list) or len(text_content) == 0:
                            text_content = ["Key research findings."]
                        
                        # 自动清理文本中的省略号
                        text_content = [str(t).replace("...", "") for t in text_content]
                        
                        repaired_sections.append({
                            "section_id": str(sec_id),
                            "section_title": str(sec_title),
                            "column_assignment": col,
                            "vertical_priority": prio,
                            "text_content": text_content,
                            "visual_assets": sec.get("visual_assets", [])
                        })
                    
                    # 强行确保包含 key_visual (如果有)
                    key_vis = (classified_visuals or {}).get("key_visual")
                    if key_vis and repaired_sections:
                        found = any(
                            v.get("visual_id") == key_vis
                            for s in repaired_sections
                            for v in s.get("visual_assets", [])
                        )
                        if not found:
                            # 强制挂载到 middle-top 段落
                            target_sec = next((s for s in repaired_sections if s["column_assignment"] == "middle" and s["vertical_priority"] == "top"), repaired_sections[0])
                            target_sec["column_assignment"] = "middle"
                            target_sec["vertical_priority"] = "top"
                            if "visual_assets" not in target_sec or not isinstance(target_sec["visual_assets"], list):
                                target_sec["visual_assets"] = []
                            target_sec["visual_assets"].append({"visual_id": key_vis})

                    if len(repaired_sections) >= 1:
                        log_agent_info(self.name, f"Successfully repaired story board with {len(repaired_sections)} sections")
                        return {"spatial_content_plan": {"sections": repaired_sections}}

        # 2. 硬核兜底 (Hard Fallback) - 当大模型彻底解析失败时执行
        log_agent_warning(self.name, "hard falling back to generated default story board from parser sections")
        structured_sections = state.get("structured_sections", {}).get("paper_sections", [])
        
        fallback_sections = []
        cols = ["left", "left", "middle", "middle", "right", "right"]
        prios = ["top", "bottom", "top", "bottom", "top", "bottom"]
        
        for i, sec in enumerate(structured_sections[:6]):
            sec_name = sec.get("section_name", f"Section {i+1}")
            clean_title = " ".join(sec_name.split()[:4])
            
            fallback_sections.append({
                "section_id": f"sec_{i+1}",
                "section_title": clean_title,
                "column_assignment": cols[i % len(cols)],
                "vertical_priority": prios[i % len(prios)],
                "text_content": [sec.get("content", "Key details.")],
                "visual_assets": []
            })
            
        if not fallback_sections:
            fallback_sections = [
                {"section_id": "sec_1", "section_title": "Introduction", "column_assignment": "left", "vertical_priority": "top", "text_content": ["Background context"], "visual_assets": []},
                {"section_id": "sec_2", "section_title": "Methodology", "column_assignment": "middle", "vertical_priority": "top", "text_content": ["System architecture"], "visual_assets": []},
                {"section_id": "sec_3", "section_title": "Experiments", "column_assignment": "middle", "vertical_priority": "bottom", "text_content": ["Experimental setup"], "visual_assets": []},
                {"section_id": "sec_4", "section_title": "Results", "column_assignment": "right", "vertical_priority": "top", "text_content": ["Main evaluation"], "visual_assets": []},
                {"section_id": "sec_5", "section_title": "Conclusion", "column_assignment": "right", "vertical_priority": "bottom", "text_content": ["Future work"], "visual_assets": []}
            ]
            
        key_vis = (classified_visuals or {}).get("key_visual")
        if key_vis and len(fallback_sections) > 1:
            fallback_sections[1]["column_assignment"] = "middle"
            fallback_sections[1]["vertical_priority"] = "top"
            fallback_sections[1]["visual_assets"] = [{"visual_id": key_vis}]

        return {"spatial_content_plan": {"sections": fallback_sections}}

    def _validate_story_board(self, story_board: Dict, classified_visuals: Dict = None, visual_context: Dict = None) -> bool:
        """validate story board structure and constraints"""
        if "spatial_content_plan" not in story_board:
            log_agent_warning(self.name, "validation error: missing 'spatial_content_plan'")
            return False
        
        scp = story_board["spatial_content_plan"]
        
        # check sections
        if "sections" not in scp or not isinstance(scp["sections"], list):
            log_agent_warning(self.name, "validation error: missing or invalid 'sections'")
            return False
        
        sections = scp["sections"]
        min_sections = self.validation_config["min_section_count"]
        max_sections = self.validation_config["max_section_count"] 
        if len(sections) < min_sections or len(sections) > max_sections:
            log_agent_warning(self.name, f"validation error: need 5-8 sections, got {len(sections)}")
            return False
        
        # validate each section
        for i, section in enumerate(sections):
            required_fields = ["section_id", "section_title", "column_assignment", "vertical_priority", "text_content"]
            for field in required_fields:
                if field not in section:
                    log_agent_warning(self.name, f"validation error: section {i} missing '{field}'")
                    return False
            
            # check column assignment is valid
            if section["column_assignment"] not in ["left", "middle", "right"]:
                log_agent_warning(self.name, f"validation error: section {i} invalid column_assignment")
                return False
                
            # check vertical priority is valid  
            if section["vertical_priority"] not in ["top", "middle", "bottom"]:
                log_agent_warning(self.name, f"validation error: section {i} invalid vertical_priority")
                return False
            
            # check section title length (4 words max)
            title = section.get("section_title", "")
            title_words = len(title.split())
            max_words = self.validation_config["max_title_words"]
            if title_words > max_words:
                log_agent_warning(self.name, f"validation error: section {i} title too long ({title_words} words): '{title}'")
                return False
            
            # check text content is list of bullet points
            min_items = self.validation_config["min_text_content_items"]
            if not isinstance(section["text_content"], list) or len(section["text_content"]) < min_items:
                log_agent_warning(self.name, f"validation error: section {i} invalid text_content")
                return False
            
            # check for ellipsis in text content
            for j, text in enumerate(section["text_content"]):
                if "..." in text:
                    log_agent_warning(self.name, f"validation error: section {i} bullet {j} contains ellipsis")
                    return False
        
        # validate key_visual placement if classified_visuals provided
        if classified_visuals:
            key_visual = classified_visuals.get("key_visual")
            if key_visual:
                key_visual_found = False
                key_visual_in_middle_top = False
                
                for section in sections:
                    visual_assets = section.get("visual_assets", [])
                    for visual in visual_assets:
                        if visual.get("visual_id") == key_visual:
                            key_visual_found = True
                            if (section.get("column_assignment") == "middle" and 
                                section.get("vertical_priority") == "top"):
                                key_visual_in_middle_top = True
                            break
                    if key_visual_found:
                        break
                
                if not key_visual_found:
                    log_agent_warning(self.name, f"validation error: key_visual '{key_visual}' not found in any section")
                    return False
                    
                if not key_visual_in_middle_top:
                    log_agent_warning(self.name, f"validation error: key_visual '{key_visual}' not placed in middle column, top priority")
                    return False
        
        # validate height exclusion compliance if visual_context provided
        if visual_context:
            visual_heights = visual_context.get("visual_assets_heights", {})
            oversized_visuals = []
            
            # check all visual assets in the story board
            for section in sections:
                visual_assets = section.get("visual_assets", [])
                for visual in visual_assets:
                    visual_id = visual.get("visual_id")
                    if visual_id in visual_heights:
                        height_info = visual_heights[visual_id]
                        # extract percentage value from string like "91%"
                        height_str = height_info.get("height_percentage", "0%")
                        height_percentage = float(height_str.rstrip('%'))
                        
                        if height_percentage > 50:
                            oversized_visuals.append(f"{visual_id} ({height_str})")
            
            if oversized_visuals:
                # check if only one oversized visual is selected
                if len(oversized_visuals) == 1:
                    # only one oversized visual selected, allow it as fallback
                    log_agent_info(self.name, f"fallback applied: allowing single oversized visual: {oversized_visuals[0]}")
                else:
                    # multiple oversized visuals selected, only allow the smallest
                    selected_oversized = []
                    for section in sections:
                        visual_assets = section.get("visual_assets", [])
                        for visual in visual_assets:
                            visual_id = visual.get("visual_id")
                            if visual_id in visual_heights:
                                height_info = visual_heights[visual_id]
                                height_str = height_info.get("height_percentage", "0%")
                                height_percentage = float(height_str.rstrip('%'))
                                if height_percentage > 50:
                                    selected_oversized.append((visual_id, height_percentage, height_str))
                    
                    smallest = min(selected_oversized, key=lambda x: x[1])
                    invalid_visuals = [f"{vid} ({h_str})" for vid, h, h_str in selected_oversized if vid != smallest[0]]
                    log_agent_warning(self.name, f"validation error: oversized visuals (>50% height) selected: {invalid_visuals} (fallback: only smallest allowed: {smallest[0]} ({smallest[2]}))")
                    return False
        
        return True

    def _prepare_visual_context_for_curator(self, state: PosterState) -> Dict[str, Any]:
        """prepare visual assets height information for curator's spatial planning"""
        config = load_config()
        
        # get poster dimensions
        poster_width = state["poster_width"] 
        poster_height = state["poster_height"]
        
        # calculate available height per column (18% of effective height for title region)
        poster_margins = 2 * config["layout"]["poster_margin"]
        effective_height = poster_height - poster_margins  # effective height after margins
        title_region_height = effective_height * config["layout"]["title_height_fraction"]  # 18% fixed region
        available_height = effective_height - title_region_height  # remaining height for sections
        
        # calculate effective column width for visual sizing
        column_margins = 2 * config["layout"]["poster_margin"]
        column_spacing = 2 * config["layout"]["column_spacing"]  # 2 gaps between 3 columns
        total_column_width = poster_width - column_margins - column_spacing
        column_width = total_column_width / 3
        
        # account for text padding within each column
        text_padding = 2 * config["layout"]["text_padding"]["left_right"]
        effective_width = column_width - text_padding
        
        log_agent_info(self.name, f"visual context: available_height={available_height:.1f}\", effective_width={effective_width:.1f}\"")
        
        # calculate height for each visual asset
        visual_heights = {}
        
        # process figures (images in state)
        figures = state.get("images", {})
        for fig_id, fig_data in figures.items():
            aspect_ratio = fig_data.get("aspect", 1.0)
            visual_height = effective_width / aspect_ratio
            height_percentage = (visual_height / available_height) * 100
            
            visual_heights[f"figure_{fig_id}"] = {
                "height_inches": round(visual_height, 1),
                "height_percentage": f"{height_percentage:.0f}%",
                "type": "figure",
                "aspect_ratio": aspect_ratio
            }
            log_agent_info(self.name, f"figure_{fig_id}: {visual_height:.1f}\" ({height_percentage:.0f}% of column)")
        
        # process tables
        tables = state.get("tables", {})
        for table_id, table_data in tables.items():
            aspect_ratio = table_data.get("aspect", 1.0)
            visual_height = effective_width / aspect_ratio
            height_percentage = (visual_height / available_height) * 100
            
            visual_heights[f"table_{table_id}"] = {
                "height_inches": round(visual_height, 1),
                "height_percentage": f"{height_percentage:.0f}%",
                "type": "table", 
                "aspect_ratio": aspect_ratio
            }
            log_agent_info(self.name, f"table_{table_id}: {visual_height:.1f}\" ({height_percentage:.0f}% of column)")
        
        return {
            "available_height_per_column": round(available_height, 1),
            "visual_assets_heights": visual_heights,
            "column_width": round(column_width, 1),
            "effective_width": round(effective_width, 1)
        }

    def _validate_height_distribution(self, story_board: Dict, visual_context: Dict) -> Dict[str, Any]:
        """validate spatial plan for height constraints and generate warnings"""
        config = load_config()
        available_height = visual_context["available_height_per_column"]
        visual_heights = visual_context["visual_assets_heights"]
        
        # extract sections from story board
        sections = story_board.get("spatial_content_plan", {}).get("sections", [])
        if not sections:
            return {"warnings": ["No sections found in story board"], "column_utilizations": {}}
        
        # organize sections by column
        columns = {"left": [], "middle": [], "right": []}
        for section in sections:
            column = section.get("column_assignment", "left")
            if column in columns:
                columns[column].append(section)
        
        # calculate estimated height for each section and column
        column_utilizations = {}
        warnings = []
        
        for column_name, column_sections in columns.items():
            total_height = 0
            total_visual_height = 0
            total_visuals = 0
            section_details = []
            
            for section in column_sections:
                section_height = self._estimate_section_height(section, visual_heights, config)
                total_height += section_height
                
                # calculate visual contribution for this section
                section_visual_height = 0
                visual_assets = section.get("visual_assets", [])
                for visual_asset in visual_assets:
                    visual_id = visual_asset.get("visual_id", "")
                    if visual_id in visual_heights:
                        section_visual_height += visual_heights[visual_id]["height_inches"]
                        total_visuals += 1
                
                total_visual_height += section_visual_height
                section_details.append({
                    "section_id": section.get("section_id", "unknown"),
                    "estimated_height": section_height,
                    "visual_count": len(visual_assets),
                    "visual_height": round(section_visual_height, 1)
                })
            
            utilization = total_height / available_height if available_height > 0 else 0
            visual_density = total_visual_height / available_height if available_height > 0 else 0
            
            column_utilizations[column_name] = {
                "total_height": round(total_height, 1),
                "utilization_percent": f"{utilization*100:.0f}%",
                "visual_density_percent": f"{visual_density*100:.0f}%",
                "section_count": len(column_sections),
                "total_visuals": total_visuals,
                "sections": section_details,
                "status": "OK" if utilization <= self.utilization_config["overflow_critical"] else "OVERFLOW"
            }
            
            if utilization > self.utilization_config["overflow_critical"]:
                warnings.append(f"{column_name} column serious overflow: {utilization*100:.0f}% (visual density: {visual_density*100:.0f}%)")
            elif utilization > self.utilization_config["overflow_warning"]:
                warnings.append(f"{column_name} column minor overflow: {utilization*100:.0f}% (visual density: {visual_density*100:.0f}%)")
            elif utilization < self.utilization_config["underutilized"]:
                warnings.append(f"{column_name} column underutilized: {utilization*100:.0f}% (visual density: {visual_density*100:.0f}%)")
            
            if total_visuals == 0:
                warnings.append(f"{column_name} column has no visuals - add visual assets")
        
        return {
            "column_utilizations": column_utilizations,
            "warnings": warnings,
            "overall_status": "PASS" if not warnings else "NEEDS_OPTIMIZATION"
        }

    def _estimate_section_height(self, section: Dict, visual_heights: Dict, config: Dict) -> float:
        """estimate total height for a section including visuals and text"""
        total_height = 0
        
        # section title height (from config)
        section_title_height = config["section_estimation"]["base_title_height"]
        total_height += section_title_height
        
        # visual assets height
        visual_assets = section.get("visual_assets", [])
        for visual_asset in visual_assets:
            visual_id = visual_asset.get("visual_id", "")
            if visual_id in visual_heights:
                visual_height = visual_heights[visual_id]["height_inches"]
                visual_spacing = config["layout"]["visual_spacing"]["below_visual"]
                total_height += visual_height + visual_spacing
        
        # text content height (rough estimation)
        text_content = section.get("text_content", [])
        text_lines = len(text_content)
        bullet_height = config["section_estimation"]["bullet_point_height"]
        text_height = text_lines * bullet_height
        total_height += text_height
        
        # spacing between title and content
        title_spacing = config["layout"]["title_to_content_spacing"]
        total_height += title_spacing
        
        # section bottom spacing
        section_spacing = config["layout"]["section_spacing"]
        total_height += section_spacing
        
        return total_height

    def _save_story_board(self, state: PosterState):
        """save story board to json file"""
        output_dir = Path(state["output_dir"]) / "content"
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "story_board.json", "w", encoding='utf-8') as f:
            json.dump(state.get("story_board", {}), f, indent=2)


def curator_node(state) -> Dict[str, Any]:
    result = StoryBoardCurator()(state)
    return {
        **result,
        "story_board": result.get("story_board", {}),
        "tokens": result.get("tokens"),
        "current_agent": result.get("current_agent", "spatial_content_planner"),
        "errors": result.get("errors", [])
    }