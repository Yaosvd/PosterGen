"""Score-neutral source/module admission; unknown evidence cannot certify a pass."""
from copy import deepcopy

from src.critic.base import EvaluationResult, issue
from src.semantic.consistency import enabled, report_current, compiled_consistent, visible_board, build_paper_index


class ModuleConsistencyEvaluator:
    name = "module_consistency"

    def evaluate(self, context):
        state = context.state
        settings = context.config["evaluators"].get(self.name, {})
        if not enabled(state):
            return EvaluationResult(self.name, "1.0.0", False, True,
                                    metadata={"status": "not_applicable"})
        board = visible_board(state)
        build_paper_index(state)
        report = state.get("module_consistency_report") or {}
        current = report_current(state, report, board)
        compiled = compiled_consistent(state, board)
        passed = bool(current and compiled and report.get("status") == "passed")
        issues = []
        if not passed:
            for module in report.get("modules", []):
                for check in module.get("checks", []):
                    if check["status"] == "passed":
                        continue
                    issues.append(issue(f"MODULE-{module['section_id']}-{check['kind']}-{check['id']}",
                        severity="critical" if check["status"] == "failed" else "warning",
                        scope="scientific_integrity", location={"section_id": module["section_id"],
                            **({f"{check['kind']}_id": check["id"]} if check["kind"] in {"claim", "visual"} else {})},
                        observation=f"Module {check['kind']} relationship is {check['status']}: {check['reason_code']}",
                        required_outcome="Use a source-backed coherent title, claims and visuals",
                        evidence={"basis": check["basis"]},
                        allowed_operations=["move_claim", "move_visual", "retitle_module", "add_claim_from_evidence"],
                        forbidden_operations=["rewrite_claim", "delete_content_to_pass"]))
            if not issues:
                issues.append(issue("MODULE-SEMANTICS-UNVERIFIED", severity="warning", scope="scientific_integrity",
                    observation="Current rendered module relationships are not fully verified",
                    required_outcome="Complete source-backed checks for this exact renderer input"))
        return EvaluationResult(self.name, str(settings.get("version", "1.0.0")), True, passed,
            issues=issues, metadata={"status": report.get("status", "inconclusive"),
                                     "current": current, "compiled_consistent": compiled,
                                     "report": deepcopy(report)})
