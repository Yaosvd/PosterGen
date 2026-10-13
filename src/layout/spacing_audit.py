"""Read-only CPU audit of a saved poster's title spacing and composition."""

import argparse
import json
from pathlib import Path

from pptx import Presentation

from src.layout.render_fit import audit_rendered_text


def audit_saved_poster(candidate_dir: Path, layout_spec_path: Path | None = None):
    content = candidate_dir / "content"
    if not content.is_dir():
        content = candidate_dir  # accepted/rejected bundles use a flat layout
    files = sorted(path for path in candidate_dir.glob("*.pptx") if path.stem != "template")
    if len(files) != 1:
        raise ValueError("Expected exactly one poster PPTX (excluding template.pptx)")
    pptx = files[0]
    spec_path = layout_spec_path or content / "layout_spec.json"
    if not spec_path.is_file():
        raise ValueError("LayoutSpec missing; supply --layout-spec for a flat historical bundle")
    presentation = Presentation(pptx)
    state = {
        "poster_width": presentation.slide_width.inches,
        "poster_height": presentation.slide_height.inches,
        "styled_layout": json.loads((content / "styled_layout.json").read_text()),
        "layout_spec": json.loads(spec_path.read_text()),
        "current_candidate": {"pptx_path": str(pptx.resolve())},
    }
    return audit_rendered_text(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--layout-spec", type=Path, help="Explicit LayoutSpec for historical flat bundles")
    args = parser.parse_args()
    print(json.dumps(audit_saved_poster(args.candidate_dir, args.layout_spec), indent=2))


if __name__ == "__main__":
    main()
