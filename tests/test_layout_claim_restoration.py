import unittest
from copy import deepcopy

from src.agents.layout_with_balancer import LayoutWithBalancerAgent


class LayoutClaimRestorationTests(unittest.TestCase):
    def setUp(self):
        self.agent = LayoutWithBalancerAgent()
        self.agent._measure_section_height = (
            lambda section, column_width, available_height, state:
            len(section.get("claim_ids", [])) * 2.0
        )
        self.state = {
            "poster_width": 54.0,
            "poster_height": 12.0,
        }

    @staticmethod
    def _section(section_id, claim_count):
        return {
            "section_id": section_id,
            "section_title": section_id,
            "column_assignment": "left",
            "vertical_priority": "top",
            "claim_ids": [
                f"{section_id}_c{index}"
                for index in range(1, claim_count + 1)
            ],
            "text_content": [
                f"original text {section_id} {index}"
                for index in range(1, claim_count + 1)
            ],
            "visual_assets": [],
        }

    def test_restores_only_original_claim_text_that_fits(self):
        original_sections = [
            self._section("s1", 4),
            self._section("s2", 4),
        ]
        optimized_sections = deepcopy(original_sections)
        for section in optimized_sections:
            section["claim_ids"] = section["claim_ids"][:1]
            section["text_content"] = section["text_content"][:1]

        restored, report = (
            self.agent._restore_grounded_claims_to_capacity(
                {
                    "spatial_content_plan": {
                        "sections": optimized_sections,
                    }
                },
                {
                    "spatial_content_plan": {
                        "sections": original_sections,
                    }
                },
                self.state,
            )
        )

        sections = restored["spatial_content_plan"]["sections"]
        self.assertEqual(3, sum(len(s["claim_ids"]) for s in sections))
        self.assertEqual(
            original_sections[0]["text_content"][:2],
            sections[0]["text_content"],
        )
        self.assertEqual(
            original_sections[1]["text_content"][:1],
            sections[1]["text_content"],
        )
        self.assertEqual(["s1_c2"], report["restored_claim_ids"])
        self.assertLessEqual(report["utilization_after"]["left"], 0.9)

    def test_skips_sections_without_one_to_one_claim_text_mapping(self):
        original = self._section("s1", 2)
        original["text_content"] = ["only one text"]
        optimized = deepcopy(original)

        restored, report = (
            self.agent._restore_grounded_claims_to_capacity(
                {
                    "spatial_content_plan": {
                        "sections": [optimized],
                    }
                },
                {
                    "spatial_content_plan": {
                        "sections": [original],
                    }
                },
                self.state,
            )
        )

        self.assertEqual(
            optimized,
            restored["spatial_content_plan"]["sections"][0],
        )
        self.assertEqual(["s1"], report["skipped_sections"])
        self.assertFalse(report["applied"])

    def test_column_height_tracks_renderer_reserve_separately(self):
        content_height = self.agent._column_height(
            ["s1", "s2"],
            {"s1": 2.0, "s2": 3.0},
        )
        physical_height = self.agent._column_height(
            ["s1", "s2"],
            {"s1": 2.0, "s2": 3.0},
            include_renderer_reserve=True,
        )

        self.assertAlmostEqual(
            5.0
            + self.agent.layout_agent.layout_constants[
                "section_padding"
            ],
            content_height,
        )
        self.assertAlmostEqual(
            content_height
            + self.agent.layout_agent.layout_constants[
                "body_render_reserve"
            ],
            physical_height,
        )

    def test_prunes_low_priority_claim_when_physical_layout_overflows(self):
        original_sections = [
            self._section("s1", 3),
            self._section("s2", 3),
        ]
        original_sections[1]["vertical_priority"] = "bottom"
        optimized_sections = deepcopy(original_sections)
        for section in optimized_sections:
            section["claim_ids"] = section["claim_ids"][:2]
            section["text_content"] = section["text_content"][:2]

        restored, report = (
            self.agent._restore_grounded_claims_to_capacity(
                {
                    "spatial_content_plan": {
                        "sections": optimized_sections,
                    }
                },
                {
                    "spatial_content_plan": {
                        "sections": original_sections,
                    }
                },
                self.state,
            )
        )

        sections = restored["spatial_content_plan"]["sections"]
        self.assertEqual(3, sum(len(s["claim_ids"]) for s in sections))
        self.assertEqual(["s2_c2"], [
            item["claim_id"]
            for item in report["pruned_due_physical_overflow"]
        ])
        self.assertEqual(4, report["llm_selected_claim_count"])
        self.assertEqual([], report["restored_claim_ids"])
        self.assertLessEqual(
            report["physical_utilization_after"]["left"],
            report["max_physical_utilization"],
        )
        self.assertEqual(
            [],
            report["unresolved_physical_overflow_columns"],
        )

    def test_removes_bottom_section_before_pruning_higher_priority_claim(self):
        original_sections = [
            self._section("s1", 2),
            self._section("s2", 1),
            self._section("s3", 1),
            self._section("s4", 3),
            self._section("s5", 3),
        ]
        original_sections[0]["vertical_priority"] = "top"
        original_sections[1]["vertical_priority"] = "middle"
        original_sections[2]["vertical_priority"] = "bottom"
        original_sections[3]["column_assignment"] = "middle"
        original_sections[3]["vertical_priority"] = "top"
        original_sections[4]["column_assignment"] = "right"
        original_sections[4]["vertical_priority"] = "top"
        optimized_sections = deepcopy(original_sections)

        restored, report = (
            self.agent._restore_grounded_claims_to_capacity(
                {
                    "spatial_content_plan": {
                        "sections": optimized_sections,
                    }
                },
                {
                    "spatial_content_plan": {
                        "sections": original_sections,
                    }
                },
                self.state,
            )
        )

        sections = restored["spatial_content_plan"]["sections"]
        self.assertEqual(["s1", "s2", "s4", "s5"], [
            section["section_id"]
            for section in sections
        ])
        self.assertEqual([], report["pruned_due_physical_overflow"])
        self.assertEqual(
            ["s3"],
            [
                item["section_id"]
                for item in report[
                    "removed_sections_due_physical_overflow"
                ]
            ],
        )
        self.assertEqual(
            ["s1_c1", "s1_c2"],
            sections[0]["claim_ids"],
        )
        self.assertLessEqual(
            report["physical_utilization_after"]["left"],
            report["max_physical_utilization"],
        )
        self.assertEqual(
            [],
            report["unresolved_physical_overflow_columns"],
        )

    def test_rebalances_bottom_sections_before_removing_result_section(self):
        original_sections = [
            self._section("s1", 1),
            self._section("s2", 1),
            self._section("s3", 1),
            self._section("s4", 1),
            self._section("s5", 2),
            self._section("s6", 1),
            self._section("s7", 1),
        ]
        assignments = {
            "s1": ("left", "top"),
            "s2": ("left", "middle"),
            "s3": ("middle", "top"),
            "s4": ("middle", "middle"),
            "s5": ("middle", "bottom"),
            "s6": ("right", "top"),
            "s7": ("right", "bottom"),
        }
        for section in original_sections:
            column, priority = assignments[section["section_id"]]
            section["column_assignment"] = column
            section["vertical_priority"] = priority

        heights = {
            "s1": 5.8,
            "s2": 12.8,
            "s3": 13.2,
            "s4": 7.4,
            "s6": 10.8,
            "s7": 5.1,
        }

        def measure(section, column_width, available_height, state):
            if section["section_id"] == "s5":
                return (
                    16.0
                    if len(section["claim_ids"]) == 2
                    else 14.2
                )
            return heights[section["section_id"]]

        self.agent._measure_section_height = measure
        self.state["poster_height"] = 36.0

        restored, report = (
            self.agent._restore_grounded_claims_to_capacity(
                {
                    "spatial_content_plan": {
                        "sections": deepcopy(original_sections),
                    }
                },
                {
                    "spatial_content_plan": {
                        "sections": original_sections,
                    }
                },
                self.state,
            )
        )

        sections = restored["spatial_content_plan"]["sections"]
        section_by_id = {
            section["section_id"]: section
            for section in sections
        }
        self.assertEqual(7, len(sections))
        self.assertEqual(
            [],
            report["removed_sections_due_physical_overflow"],
        )
        self.assertEqual(
            ["s5_c2"],
            [
                item["claim_id"]
                for item in report[
                    "pruned_due_physical_overflow"
                ]
            ],
        )
        self.assertEqual("right", section_by_id["s5"]["column_assignment"])
        self.assertEqual("left", section_by_id["s7"]["column_assignment"])
        self.assertEqual(
            {"s5", "s7"},
            {
                item["section_id"]
                for item in report[
                    "rebalanced_sections_due_physical_overflow"
                ]
            },
        )
        self.assertEqual(
            [],
            report["unresolved_physical_overflow_columns"],
        )


if __name__ == "__main__":
    unittest.main()
