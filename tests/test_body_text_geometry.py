import unittest

from src.agents.renderer import Renderer
from src.agents.font_agent import FontAgent


class BodyTextGeometryTests(unittest.TestCase):
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
