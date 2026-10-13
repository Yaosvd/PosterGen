"""Bounded content-aware shared-boundary refinement; no model coordinates."""

from copy import deepcopy
from typing import Any, Dict

from src.layout.measurement_context import current_context, measured_phase
from src.layout.whitespace import no_displaced_whitespace


def boundary_options(candidate, body_height, *, maximum=4, preferred_gutter_inches=0.30):
    """Release measured upper-zone slack to an aligned lower zone.

    Keep zone IDs, roles, assignments, reading order, horizontal geometry and
    the pair's outside edges. Never manufacture density by shrinking the body.
    """
    spec = candidate["layout_spec"]
    choices = []
    # A shared row boundary may join a spanning upper module to several lower
    # cards (or several upper rails to a lower band). Move the whole row group
    # together; never independently create overlapping partial boundaries.
    zones = spec["zones"]
    for lower_y in sorted({float(zone["y"]) for zone in zones if float(zone["y"]) > 0}):
        lowers = [zone for zone in zones if abs(float(zone["y"]) - lower_y) < 1e-6]
        ends = sorted({float(zone["y"]) + float(zone["height"]) for zone in zones
                       if 0 <= lower_y - float(zone["y"]) - float(zone["height"]) <= 0.08})
        for end in ends:
            uppers = [zone for zone in zones if abs(float(zone["y"]) + float(zone["height"]) - end) < 1e-6
                      and any(min(float(zone["x"]) + float(zone["width"]), float(lower["x"]) + float(lower["width"]))
                              > max(float(zone["x"]), float(lower["x"])) + 1e-6 for lower in lowers)]
            if len(uppers) + len(lowers) <= 2 or not uppers:
                continue
            slack = min(max(0.0, float((candidate.get("exact_bottom_gaps") or {}).get(str(zone["zone_id"]), 0)) - 0.10)
                        for zone in uppers) / body_height
            slack = min(slack, 0.065, *(max(0.0, float(zone["height"]) - 0.10) for zone in uppers))
            gutter_release = max(0.0, lower_y - end - preferred_gutter_inches / body_height)
            gutter_release = min(gutter_release, 0.03)
            if (slack + gutter_release) * body_height < 0.20:
                continue
            for fraction in (1.0, 0.5):
                changed = deepcopy(zones)
                delta = round(slack * fraction, 6)
                released = round(gutter_release * fraction, 6)
                for zone in changed:
                    if zone["zone_id"] in {item["zone_id"] for item in uppers}:
                        zone["height"] = round(float(zone["height"]) - delta, 6)
                    elif zone["zone_id"] in {item["zone_id"] for item in lowers}:
                        zone["y"] = round(float(zone["y"]) - delta - released, 6)
                        zone["height"] = round(float(zone["height"]) + delta + released, 6)
                choices.append(((slack + gutter_release) * body_height * len(uppers), changed,
                                ",".join(str(zone["zone_id"]) for zone in uppers),
                                ",".join(str(zone["zone_id"]) for zone in lowers)))
    for upper in spec["zones"]:
        upper_bottom = float(upper["y"]) + float(upper["height"])
        for lower in spec["zones"]:
            if upper is lower or abs(float(upper["x"]) - float(lower["x"])) > 1e-6 or abs(float(upper["width"]) - float(lower["width"])) > 1e-6:
                continue
            gutter = float(lower["y"]) - upper_bottom
            if not 0 <= gutter <= 0.08:
                continue
            unused = float((candidate.get("exact_bottom_gaps") or {}).get(str(upper["zone_id"]), 0.0))
            slack = max(0.0, unused - 0.10) / body_height
            slack = min(slack, 0.065, max(0.0, float(upper["height"]) - 0.10))
            gutter_release = min(0.03, max(0.0, gutter - preferred_gutter_inches / body_height))
            if (slack + gutter_release) * body_height < 0.20:
                continue
            for fraction in (1.0, 0.5):
                zones = deepcopy(spec["zones"])
                first = next(zone for zone in zones if zone["zone_id"] == upper["zone_id"])
                second = next(zone for zone in zones if zone["zone_id"] == lower["zone_id"])
                delta = round(slack * fraction, 6)
                released = round(gutter_release * fraction, 6)
                first["height"] = round(float(first["height"]) - delta, 6)
                second["y"] = round(float(second["y"]) - delta - released, 6)
                second["height"] = round(float(second["height"]) + delta + released, 6)
                choices.append((unused + gutter_release * body_height, zones, str(upper["zone_id"]), str(lower["zone_id"])))
    return sorted(choices, key=lambda value: -value[0])[:maximum]


@measured_phase("composition_refinement")
def refine_composition(agent, candidate, source_board, state, config, exact_refine, fingerprint):
    """At most two rounds of four exact candidates, after a feasible fit."""
    settings = config.get("composition_refinement") or {}
    audit: Dict[str, Any] = {"schema_version": 1, "policy_version": "composition_v2", "status": "not_needed", "trials": []}
    if not settings.get("enabled", True) or state.get("template_validation_topology") or state.get("improve_safe_fallback") or (state.get("iteration_context") or {}).get("portfolio_mode") == "validate":
        audit["status"] = "locked_or_disabled"
        return candidate, audit
    if not candidate.get("layout_spec", {}).get("zones"):
        audit["status"] = "geometry_unavailable"
        return candidate, audit
    from src.layout.families import LayoutFamilyRegistry, valid_family_topology
    family = LayoutFamilyRegistry().get(candidate["layout_spec"]["family_id"])
    body_height = (float(state["poster_height"]) - 2 * agent.poster_margin) * (1 - agent.title_height_fraction)
    best = candidate
    seen = set()
    rounds = min(2, max(0, int(settings.get("max_rounds", 2))))
    maximum = min(4, max(0, int(settings.get("candidates_per_round", 4))))
    for round_index in range(rounds):
        improved = None
        body_font = float((getattr(agent, "config", {}).get("typography") or {}).get("sizes", {}).get("body_text", 44))
        gutter = body_font / 72 * float(settings.get("preferred_zone_gutter_body_lines", 0.5))
        for _, zones, upper, lower in boundary_options(best, body_height, maximum=maximum, preferred_gutter_inches=gutter):
            identity = fingerprint([{key: zone.get(key) for key in ("zone_id", "x", "y", "width", "height", "role", "capacity")} for zone in zones])
            if identity in seen or not valid_family_topology(family, zones):
                continue
            seen.add(identity)
            trace = {"round": round_index + 1, "upper_zone_id": upper, "lower_zone_id": lower,
                     "geometry_fingerprint": identity}
            audit["trials"].append(trace)
            context = current_context()
            if context:
                context.emit("composition candidate", round=round_index + 1, candidate=len(audit["trials"]), limit=rounds * maximum)
            trial = deepcopy(best)
            trial["layout_spec"]["zones"] = zones
            for payload in (trial["layout_spec"], trial["variant"]):
                payload["geometry_fingerprint"] = identity
                payload["variant_id"] = f"{family.family_id}_{identity}"
                payload["mutation_trace"] = list(payload.get("mutation_trace") or []) + ["content_aware_shared_boundary", upper, lower]
            trial["variant"]["zones"] = deepcopy(zones)
            result = exact_refine(agent, trial, source_board, state, config.get("explore_layout") or {}, allow_changes=True)
            if result is None:
                trace["status"] = "infeasible"
                continue
            before_ids = set(best["candidate_content_selection"]["visible_claim_ids"])
            before_visuals = set(best["candidate_content_selection"]["visible_visual_ids"])
            safe = (before_ids.issubset(result["candidate_content_selection"]["visible_claim_ids"])
                    and before_visuals.issubset(result["candidate_content_selection"]["visible_visual_ids"])
                    and no_displaced_whitespace(best["composition_whitespace"], result["composition_whitespace"]))
            if state.get("revision_contract"):
                from src.agents.revision_contract import check_contract, deletion_guard
                safe = safe and check_contract(state, result["board"])["passed"] and deletion_guard(state, {
                    "composition_whitespace": result["composition_whitespace"],
                    "zone_utilization": result["exact_utilization"],
                    "exact_bottom_gaps": result["exact_bottom_gaps"],
                })["passed"]
            trace.update({"score_before": best["exact_score"], "score_after": result["exact_score"],
                          "whitespace_before": best["composition_whitespace"], "whitespace_after": result["composition_whitespace"]})
            if safe and result["exact_score"] > best["exact_score"] + 1e-6:
                trace["status"] = "improved"
                if improved is None or result["exact_score"] > improved["exact_score"]:
                    improved = result
            else:
                trace["status"] = "no_safe_gain"
        if improved is None:
            break
        best = improved
        audit["status"] = "improved"
    audit["exact_candidates_checked"] = len(audit["trials"])
    audit["limits"] = {"rounds": rounds, "candidates_per_round": maximum}
    if audit["trials"] and audit["status"] != "improved":
        audit["status"] = "no_safe_gain"
    return best, audit
