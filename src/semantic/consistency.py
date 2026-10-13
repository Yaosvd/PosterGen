"""Evidence-backed, bounded module checks. No scientific prose is edited here.

Geometry is deliberately absent from check identities. Only positive, complete
checks are reusable; missing evidence and model outages never become a pass.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import base64
import json
from pathlib import Path
import re
from typing import Any

from utils.evidence_utils import normalize_space, extract_numbers
from utils.grounded_content import all_publishable_claims, merge_evidence_banks

POLICY = "module_consistency_v1"
DEFAULTS = {
    "enabled": True, "max_model_calls": 32, "max_repairs": 2,
    "max_payload_bytes": 98304, "max_modules": 16, "cache_entries": 128,
    "max_image_bytes": 8388608,
}
_REF = re.compile(r"\b(Fig(?:ure)?s?\.?|Tables?)\s*(\d+[A-Za-z]?)\b", re.I)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def settings(state: dict) -> dict:
    return {**DEFAULTS, **((state.get("critic_config") or {}).get("module_consistency") or {})}


def enabled(state: dict) -> bool:
    return state.get("generation_route") == "optimization_family" and settings(state)["enabled"]


def sections(board: Any) -> list[dict]:
    return (board or {}).get("spatial_content_plan", {}).get("sections", [])


def visible_board(state: dict) -> dict:
    return state.get("optimized_story_board") or state.get("story_board") or {}


def _asset_digest(asset: dict) -> str | None:
    path = Path(str(asset.get("path") or ""))
    if not path.is_file():
        return None
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def _ref_identity(text: str) -> tuple[str, str] | None:
    match = _REF.match(text.strip())
    if not match:
        return None
    return ("table" if match[1].lower().startswith("table") else "figure", match[2].lower())


def build_paper_index(state: dict) -> dict:
    """Derive associations, never equating extraction sequence with paper number."""
    chunks = state.get("section_chunks") or (state.get("structured_sections") or {}).get("sections", [])
    if isinstance(chunks, dict):
        chunks = chunks.get("sections", [])
    raw = str(state.get("raw_text") or "")
    source_texts = [raw] + [str(c.get("content") or "") for c in chunks if isinstance(c, dict)]
    normalized_sources = [normalize_space(text) for text in source_texts if text]
    sources: dict[str, dict] = {}
    evidence = {}
    for item in merge_evidence_banks(state).get("items", []):
        eid = str(item.get("evidence_id") or "")
        excerpt = normalize_space(item.get("source_excerpt") or "")
        if not eid or not excerpt:
            continue
        verified = any(excerpt in text for text in normalized_sources)
        evidence[eid] = {"source_id": f"evidence:{eid}", "verified": verified,
                         "source": deepcopy(item.get("source") or {})}
        sources[f"evidence:{eid}"] = {"text": excerpt, "verified": verified, "kind": "evidence"}
    assets = {}
    for kind, collection in (("figure", state.get("images") or {}), ("table", state.get("tables") or {})):
        for key, asset in collection.items():
            vid = f"{kind}_{key}"
            caption = normalize_space(asset.get("caption") or "")
            identity = _ref_identity(caption)
            generic = not caption or bool(re.fullmatch(r"(?:Figure|Fig\.?|Table)\s*\d+", caption, re.I))
            provenance = asset.get("caption_provenance") or "legacy"
            verified = (not generic and provenance != "ambiguous"
                        and any(caption in text for text in normalized_sources))
            sid = f"caption:{vid}"
            sources[sid] = {"text": caption, "verified": verified, "kind": "caption"}
            references = []
            if identity and not generic:
                # Exact paper reference tokens, not substring Figure 1 / Figure 10.
                for chunk_index, chunk in enumerate(chunks):
                    if not isinstance(chunk, dict):
                        continue
                    for paragraph_index, paragraph in enumerate(re.split(r"\n\s*\n", str(chunk.get("content") or ""))):
                        if not any(_ref_identity(m.group(0)) == identity for m in _REF.finditer(paragraph)):
                            continue
                        ref_id = f"reference:{vid}:{chunk_index}:{paragraph_index}"
                        sources[ref_id] = {"text": normalize_space(paragraph), "verified": True,
                                           "kind": "reference", "section_id": chunk.get("section_id")}
                        references.append(ref_id)
            assets[vid] = {"caption_source_id": sid, "paper_reference": identity,
                           "reference_source_ids": references, "caption_provenance": provenance,
                           "association_status": "supported" if verified else "inconclusive",
                           "page": asset.get("page"), "block_id": asset.get("block_id"),
                           "asset_sha256": _asset_digest(asset)}
    # Ambiguous duplicate paper labels cannot identify a unique extracted asset.
    counts = Counter(tuple(a["paper_reference"]) for a in assets.values() if a["paper_reference"])
    for asset in assets.values():
        identity = asset["paper_reference"]
        if identity and counts[tuple(identity)] > 1:
            asset["association_status"] = "inconclusive"
            sources[asset["caption_source_id"]]["verified"] = False
            asset["caption_provenance"] = "duplicate_paper_label"
    index = {"schema_version": 1, "policy": POLICY, "sources": sources,
             "evidence": evidence, "visuals": assets, "paper_sha256": digest(source_texts)}
    index["digest"] = digest(index)
    state["paper_semantic_index"] = index
    return index


def _payload(state: dict, section: dict, index: dict) -> tuple[dict, list[str]]:
    claims = all_publishable_claims(state)
    selected = []
    source_ids = set()
    problems = []
    ids = [str(cid) for cid in section.get("claim_ids") or []]
    texts = section.get("text_content") or []
    if len(ids) != len(texts) or len(ids) != len(set(ids)) or not ids:
        problems.append("invalid_claim_ownership")
    for position, cid in enumerate(ids):
        claim = claims.get(cid)
        if not claim or position >= len(texts) or texts[position] != claim.get("text"):
            problems.append("unverified_visible_text")
            continue
        eids = [str(eid) for eid in claim.get("evidence_ids") or []]
        if not eids or any(not (index["evidence"].get(eid) or {}).get("verified") for eid in eids):
            problems.append("missing_exact_source_evidence")
        source_ids.update(f"evidence:{eid}" for eid in eids)
        selected.append({"claim_id": cid, "text": claim["text"], "evidence_ids": eids,
                         "origin_narrative_section_id": claim.get("section_id")})
    visuals = []
    for item in section.get("visual_assets") or []:
        vid = str(item.get("visual_id") or "")
        asset = index["visuals"].get(vid)
        if not asset or not asset.get("asset_sha256"):
            problems.append("missing_source_visual")
            continue
        if asset["association_status"] != "supported":
            problems.append("unresolved_caption_association")
        source_ids.add(asset["caption_source_id"])
        source_ids.update(asset["reference_source_ids"])
        visuals.append({"visual_id": vid, **asset})
    sources = {sid: index["sources"][sid] for sid in sorted(source_ids) if sid in index["sources"]}
    payload = {"section_id": str(section.get("section_id") or ""),
               "title": str(section.get("section_title") or ""), "claims": selected,
               "visuals": visuals, "sources": sources}
    return payload, sorted(set(problems))


def _model_identity(state: dict, key: str = "text_model") -> dict:
    config = state.get(key)
    # Never serialize credentials/endpoints from model configuration.
    from utils.agent_policy import apply_agent_policy
    if config is not None:
        config = apply_agent_policy(config, "module_consistency")
    return {key: getattr(config, key, None) for key in ("model_name", "provider", "temperature", "max_tokens", "enable_thinking", "json_mode")}


def _call(state: dict, prompt_path: str, payload: dict) -> dict:
    from utils.agent_policy import apply_agent_policy
    from utils.langgraph_utils import LangGraphAgent, extract_json, load_prompt
    runtime = state.setdefault("module_semantic_runtime", {"model_calls": 0})
    limits = settings(state)
    encoded = json.dumps(payload, ensure_ascii=False)
    if len(encoded.encode()) > limits["max_payload_bytes"]:
        return {"unavailable_reason": "payload_budget"}
    if runtime["model_calls"] >= limits["max_model_calls"]:
        return {"unavailable_reason": "call_budget"}
    visual_input = bool(payload.get("visuals"))
    # User explicitly authorized source-image checks through the same configured
    # vision_model already used by ColorAgent and VisualCritic (2026-10-13).
    model_key = "vision_model" if visual_input else "text_model"
    if state.get(model_key) is None:
        return {"unavailable_reason": "model_unavailable"}
    images = []
    image_bytes = 0
    for visual in payload.get("visuals") or []:
        kind, key = visual["visual_id"].split("_", 1)
        asset = (state.get("tables" if kind == "table" else "images") or {}).get(key) or {}
        path = Path(str(asset.get("path") or ""))
        if not path.is_file() or path.stat().st_size + image_bytes > limits["max_image_bytes"]:
            return {"unavailable_reason": "image_payload_unavailable_or_over_budget"}
        with path.open("rb") as stream:
            image = stream.read(limits["max_image_bytes"] - image_bytes + 1)
        if image_bytes + len(image) > limits["max_image_bytes"]:
            return {"unavailable_reason": "image_payload_unavailable_or_over_budget"}
        if hashlib.sha256(image).hexdigest() != visual.get("asset_sha256"):
            return {"unavailable_reason": "source_image_changed"}
        image_bytes += len(image)
        images.extend([{"type": "text", "text": "Source visual ID: " + visual["visual_id"]},
                       {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode("ascii")}}])
    runtime["model_calls"] += 1
    agent = LangGraphAgent("Check scientific module relationships using supplied sources only.",
                           apply_agent_policy(state[model_key], "module_consistency"),
                           state, "module_consistency", single_attempt=True)
    prompt = load_prompt(prompt_path) + "\n\nINPUT DATA:\n" + encoded
    try:
        response = agent.step(json.dumps([{"type": "text", "text": prompt}, *images]) if visual_input else prompt)
    except Exception as exc:
        # An API/programming failure follows ordinary generation-failure
        # accounting, never a scored rejection or a template-transfer failure.
        raise RuntimeError(f"Module consistency {model_key} call failed ({type(exc).__name__})") from exc
    account = state["tokens"].add_vision if visual_input else state["tokens"].add_text
    account(int(response.input_tokens), int(response.output_tokens))
    try:
        result = extract_json(response.content)
    except (ValueError, TypeError):
        return {"unavailable_reason": "invalid_model_response"}
    return result if isinstance(result, dict) else {"unavailable_reason": "invalid_model_response"}


def dependency_safe(section: dict, state: dict) -> bool:
    """Cheap selection guard; final semantic checks still verify changed wording."""
    if not enabled(state):
        return True
    contract = (state.get("module_semantic_contracts") or {}).get(str(section.get("section_id"))) or {}
    if not contract.get("dependencies"):
        return True
    claims = all_publishable_claims(state)
    def root(cid):
        item = claims.get(str(cid)) or {}
        return str(item.get("root_claim_id") or cid)
    roots = {root(cid) for cid in section.get("claim_ids", [])}
    visuals = {v.get("visual_id") for v in section.get("visual_assets", [])}
    return all(dep["visual_id"] not in visuals or {root(cid) for cid in dep["required_claim_ids"]}.issubset(roots)
               for dep in contract.get("dependencies") or [])


def compiled_consistent(state: dict, board: dict) -> bool:
    """Bind source review to the actual renderer input, including literal titles."""
    from src.agents.font_agent import FontAgent
    from utils.text_formatting import tokenize_styling
    layout = state.get("styled_layout") or []
    if not layout:
        return False
    font = FontAgent()
    by_id = {str(s.get("section_id")): s for s in sections(board)}
    if {str(e.get("section_id")) for e in layout if e.get("type") == "section_container"} != set(by_id):
        return False
    for sid, section in by_id.items():
        titles = [e for e in layout if e.get("type") == "section_title" and str(e.get("section_id")) == sid]
        if len(titles) != 1 or str(titles[0].get("section_title") or "") != str(section.get("section_title") or ""):
            return False
        expected = font._escape_formatting_literals(font._format_bullet_points("\n".join(section.get("text_content") or [])))
        actual = "\n".join(str(e.get("content") or "") for e in layout if e.get("type") == "text" and str(e.get("section_id")) == sid)
        def plain(text):
            return normalize_space("\n".join("".join(t["text"] for t in tokenize_styling(line)) for line in text.split("\n")))
        if plain(expected) != plain(actual):
            return False
    expected_visuals = Counter((sid, str(v.get("visual_id"))) for sid, s in by_id.items() for v in s.get("visual_assets") or [])
    actual_visuals = Counter((str(e.get("section_id")), str(e.get("visual_id"))) for e in layout if e.get("type") == "visual")
    return expected_visuals == actual_visuals


def _normalize(raw: dict, payload: dict, identity: str) -> dict:
    expected = {("title", payload["section_id"]), ("module", payload["section_id"])}
    expected.update(("claim", c["claim_id"]) for c in payload["claims"])
    expected.update(("visual", v["visual_id"]) for v in payload["visuals"])
    checks = {}
    malformed = False
    raw_checks = raw.get("checks") or []
    if not isinstance(raw_checks, list):
        raw_checks = []
        malformed = True
    for item in raw_checks:
        if not isinstance(item, dict):
            malformed = True
            continue
        key = (str(item.get("kind")), str(item.get("id")))
        if key not in expected or key in checks:
            malformed = True
            continue
        status = item.get("status")
        citations = []
        basis = item.get("basis") or []
        for citation in basis if isinstance(basis, list) else []:
            if not isinstance(citation, dict):
                continue
            sid = str(citation.get("source_id") or "")
            quote = normalize_space(citation.get("quote") or "")
            source = payload["sources"].get(sid) or {}
            if source.get("verified") and quote and quote in source.get("text", "") and len(quote) >= min(12, len(source["text"])):
                citations.append({"source_id": sid, "quote_sha256": digest(quote)})
        if status not in {"passed", "failed", "inconclusive"} or not citations:
            status = "inconclusive"
        if key[0] == "title" and status == "passed":
            evidence_numbers = {number for source in payload["sources"].values() if source["kind"] == "evidence"
                                for number in extract_numbers(source["text"])}
            if not set(extract_numbers(payload["title"])).issubset(evidence_numbers):
                status = "failed"
                item = {**item, "reason_code": "unsupported_title_number"}
        if key[0] == "claim" and status != "inconclusive":
            own = next(c for c in payload["claims"] if c["claim_id"] == key[1])
            if not any(c["source_id"] in {f"evidence:{eid}" for eid in own["evidence_ids"]} for c in citations):
                status = "inconclusive"
        if key[0] == "visual" and status != "inconclusive":
            visual = next(v for v in payload["visuals"] if v["visual_id"] == key[1])
            kinds = {payload["sources"][c["source_id"]]["kind"] for c in citations}
            if item.get("image_examined") is not True or visual["caption_source_id"] not in {c["source_id"] for c in citations} or "evidence" not in kinds:
                status = "inconclusive"
        checks[key] = {"kind": key[0], "id": key[1], "status": status,
                       "reason_code": str(item.get("reason_code") or "unspecified")[:80], "basis": citations,
                       **({"image_examined": item.get("image_examined") is True} if key[0] == "visual" else {})}
    for kind, oid in sorted(expected - set(checks)):
        checks[(kind, oid)] = {"kind": kind, "id": oid, "status": "inconclusive", "reason_code": "missing_check", "basis": []}
    statuses = [item["status"] for item in checks.values()]
    status = "failed" if "failed" in statuses else "inconclusive" if malformed or "inconclusive" in statuses else "passed"
    theme_values = raw.get("theme_evidence_ids") or []
    theme_eids = sorted({str(eid) for eid in (theme_values if isinstance(theme_values, list) else [])
                         if f"evidence:{eid}" in payload["sources"] and payload["sources"][f"evidence:{eid}"]["verified"]})
    if not theme_eids and status == "passed":
        status = "inconclusive"
    dependencies = []
    raw_dependencies = raw.get("dependencies") or []
    for dep in raw_dependencies if isinstance(raw_dependencies, list) else []:
        if not isinstance(dep, dict):
            continue
        required_ids = dep.get("required_claim_ids") or []
        required = set(map(str, required_ids)) if isinstance(required_ids, list) else set()
        if dep.get("visual_id") in {v["visual_id"] for v in payload["visuals"]} and required and required.issubset({c["claim_id"] for c in payload["claims"]}):
            dependencies.append({"visual_id": dep["visual_id"], "required_claim_ids": sorted(required)})
    return {"section_id": payload["section_id"], "identity": identity, "status": status,
            "checks": list(checks.values()), "theme": str(raw.get("theme") or "")[:240],
            "theme_evidence_ids": theme_eids, "dependencies": dependencies,
            "repair_proposals": deepcopy([p for p in raw.get("repair_proposals", []) if isinstance(p, dict)][:4]) if isinstance(raw.get("repair_proposals", []), list) else [],
            "reason": raw.get("unavailable_reason")}


def audit_board(state: dict, board: dict, *, refresh_index: bool = False) -> dict:
    if not enabled(state):
        return {"schema_version": 1, "policy": POLICY, "status": "not_applicable", "modules": []}
    index = build_paper_index(state) if refresh_index or not state.get("paper_semantic_index") else state["paper_semantic_index"]
    limits = settings(state)
    modules = []
    cache = state.setdefault("module_semantic_cache", {})
    board_sections = sections(board)
    unique_ids = [str(s.get("section_id") or "") for s in board_sections]
    if not board_sections or len(board_sections) > limits["max_modules"] or not all(unique_ids) or len(unique_ids) != len(set(unique_ids)):
        return {"schema_version": 1, "policy": POLICY, "status": "inconclusive", "modules": [], "reason": "invalid_module_set"}
    for section in board_sections:
        payload, problems = _payload(state, section, index)
        identity = digest({"policy": POLICY, "payload": payload, "paper": index["digest"],
                           "model": [_model_identity(state), _model_identity(state, "vision_model")], "settings": limits,
                           "prompts": [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (
                               "config/prompts/module_consistency.txt", "config/prompts/module_consistency_confirm.txt")]})
        payload["repair_targets"] = [{"section_id": str(s.get("section_id")), "title": str(s.get("section_title") or "")}
                                     for s in board_sections if s is not section]
        if identity in cache:
            result = deepcopy(cache[identity])
        elif problems:
            result = {"section_id": payload["section_id"], "identity": identity,
                      "status": "inconclusive", "checks": [], "reason": ",".join(problems), "repair_proposals": []}
        else:
            result = _normalize(_call(state, "config/prompts/module_consistency.txt", payload), payload, identity)
            if result["status"] == "failed":
                # Independently confirm object-specific failures. Disagreement is unknown.
                confirmation = _normalize(_call(state, "config/prompts/module_consistency_confirm.txt", payload), payload, identity)
                confirmed = {(c["kind"], c["id"]) for c in confirmation["checks"] if c["status"] == "failed"}
                for check in result["checks"]:
                    if check["status"] == "failed" and (check["kind"], check["id"]) not in confirmed:
                        check["status"] = "inconclusive"
                result["status"] = ("failed" if any(c["status"] == "failed" for c in result["checks"]) else "inconclusive")
            if result["status"] == "passed":
                cache[identity] = deepcopy(result)
                while len(cache) > limits["cache_entries"]:
                    del cache[next(iter(cache))]
        modules.append(result)
    statuses = [m["status"] for m in modules]
    return {"schema_version": 1, "policy": POLICY, "status": "failed" if "failed" in statuses else "inconclusive" if "inconclusive" in statuses else "passed",
            "board_identity": digest(board_content_identity(board)), "paper_index_digest": index["digest"],
            "modules": modules, "coverage": {name: statuses.count(name) for name in ("passed", "failed", "inconclusive")},
            "model_calls": state.get("module_semantic_runtime", {}).get("model_calls", 0)}


def board_content_identity(board: dict) -> list[dict]:
    return [{"section_id": s.get("section_id"), "title": s.get("section_title"),
             "claim_ids": s.get("claim_ids") or [], "text": s.get("text_content") or [],
             "visual_ids": [v.get("visual_id") for v in s.get("visual_assets") or []]}
            for s in sections(board)]


def report_current(state: dict, report: dict, board: dict) -> bool:
    return (report.get("policy") == POLICY and report.get("board_identity") == digest(board_content_identity(board))
            and report.get("paper_index_digest") == (state.get("paper_semantic_index") or {}).get("digest"))


def preserve_content(before: dict, after: dict) -> bool:
    def inventory(board):
        return (Counter((str(cid), str(text)) for s in sections(board) for cid, text in zip(s.get("claim_ids") or [], s.get("text_content") or [])),
                Counter(str(v.get("visual_id")) for s in sections(board) for v in s.get("visual_assets") or []))
    return inventory(before) == inventory(after) and all(s.get("claim_ids") for s in sections(after))


def changed_modules_safe(state: dict, before: dict, after: dict) -> bool:
    """Membership edits are staged; an unknown target cannot authorize a move."""
    if not enabled(state) or board_content_identity(before) == board_content_identity(after):
        return True
    old = {str(s.get("section_id")): s for s in sections(before)}
    changed = [s for s in sections(after) if board_content_identity({"spatial_content_plan": {"sections": [s]}})
               != board_content_identity({"spatial_content_plan": {"sections": [old.get(str(s.get("section_id")), {})]}})]
    if set(old) != {str(s.get("section_id")) for s in sections(after)}:
        return False
    return audit_board(state, {"spatial_content_plan": {"sections": changed}}, refresh_index=True)["status"] == "passed"


def save_reports(state: dict) -> None:
    if not state.get("output_dir"):
        return
    target = Path(state["output_dir"]) / "content"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("paper_semantic_index", "module_consistency_report", "module_semantic_repair_report"):
        if state.get(name):
            (target / f"{name}.json").write_text(json.dumps(state[name], ensure_ascii=False, indent=2), encoding="utf-8")
