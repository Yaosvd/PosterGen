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

    def test_renderer_reserve_uses_capacity_headroom(self):
        height = self.agent._column_height(
            ["s1", "s2"],
            {"s1": 2.0, "s2": 3.0},
        )

        self.assertAlmostEqual(
            5.0
            + self.agent.layout_agent.layout_constants[
                "section_padding"
            ],
            height,
        )
        self.assertAlmostEqual(
            self.agent.layout_agent.layout_constants["section_padding"]
            + self.agent.layout_agent.layout_constants[
                "body_render_reserve"
            ],
            self.agent.layout_agent._inter_section_spacing(),
        )


if __name__ == "__main__":
    unittest.main()
