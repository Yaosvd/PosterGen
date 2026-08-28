import unittest

from src.agents.renderer import Renderer
from src.agents.font_agent import FontAgent
from src.agents.layout_agent import LayoutAgent


class BodyTextGeometryTests(unittest.TestCase):
    def test_section_title_reserves_bold_renderer_wrap(self):
        agent = LayoutAgent()
        state = {
            "styling_interfaces": {
                "font_sizes": {
                    "section_title": 64,
                },
            },
        }
        column_width = 16.6667

        short_title = agent._measure_section_title(
            "DP/RDP Analysis",
            column_width,
            state,
        )
        already_wrapped_title = agent._measure_section_title(
            "ViT & Distributed Learning Constraints",
            column_width,
            state,
        )

        self.assertEqual(1, short_title["renderer_safe_lines"])
        self.assertEqual(0.0, short_title["renderer_wrap_reserve"])
        self.assertEqual(2, already_wrapped_title["measured_lines"])
        self.assertEqual(
            0.0,
            already_wrapped_title["renderer_wrap_reserve"],
        )

        for title in (
            "ViT Privacy Risks & Regularization",
            "Reconstruction Attack Robustness",
        ):
            with self.subTest(title=title):
                wrapped_title = agent._measure_section_title(
                    title,
                    column_width,
                    state,
                )
                self.assertEqual(
                    2,
                    wrapped_title["renderer_safe_lines"],
                )
                self.assertAlmostEqual(
                    64 / 72,
                    wrapped_title["renderer_wrap_reserve"],
                )
                self.assertGreater(
                    wrapped_title["height"],
                    short_title["height"] + 0.8,
                )

    def test_renderer_preserves_layout_textbox_geometry(self):
        renderer = Renderer()
        captured = {}

        def capture(slide, text, left, top, width, height, element):
            captured.update(
                {
                    "text": text,
                    "left": left.inches,
                    "top": top.inches,
                    "width": width.inches,
                    "height": height.inches,
                }
            )

        renderer._add_enhanced_text = capture
        renderer._render_text(
            None,
            {
                "id": "poster_sec_1_text",
                "type": "text",
                "x": 1.3,
                "y": 2.4,
                "width": 16.067,
                "height": 5.25,
                "content": "Verified claim text.",
            },
            {},
        )

        self.assertEqual("Verified claim text.", captured["text"])
        self.assertAlmostEqual(1.3, captured["left"], delta=1e-6)
        self.assertAlmostEqual(2.4, captured["top"], delta=1e-6)
        self.assertAlmostEqual(16.067, captured["width"], delta=1e-6)
        self.assertAlmostEqual(5.25, captured["height"], delta=1e-6)

    def test_font_agent_does_not_insert_bullet_characters(self):
        content = (
            "The source claim starts with an article.\n"
            "A second verified claim."
        )

        self.assertEqual(
            content,
            FontAgent()._format_bullet_points(content),
        )


if __name__ == "__main__":
    unittest.main()
