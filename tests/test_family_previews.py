from pptx import Presentation
from src.layout.families import LayoutFamilyRegistry
from src.layout.family_previews import generate_family_previews


def test_all_registered_families_have_editable_png_pptx_skeletons(tmp_path):
    paths = generate_family_previews(tmp_path)
    assert len(paths) == 2 * len(LayoutFamilyRegistry().ids())
    for family_id in LayoutFamilyRegistry().ids():
        assert (tmp_path / f'{family_id}.png').is_file()
        deck = Presentation(tmp_path / f'{family_id}.pptx')
        assert len(deck.slides[0].shapes) >= 2
        assert all(shape.has_text_frame for shape in deck.slides[0].shapes)
