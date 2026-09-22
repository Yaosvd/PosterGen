"""Legacy L1 records must not invent cross-paper profile evidence."""

import json

from src.config.critic_config import load_critic_config
from src.templates.library import TemplateLibrary


def _legacy_library(tmp_path, with_outcome):
    library = TemplateLibrary(tmp_path, load_critic_config())
    library.index_path.parent.mkdir(parents=True)
    library.index_path.write_text(json.dumps({
        "schema_version": 5,
        "templates": [{
            "template_id": "legacy-l1", "template_level": 1,
            "status": "paper_specific", "family": "classic_three_column",
            "fingerprint": "legacy-l1", "signature_vector": [0.1, 0.2],
            "source_paper_id": "source", "source_profile": "balanced:medium",
            "applicability": {"preferred_visual_count": [0, 10]},
            "validation": {
                "successful_papers": ["source", "other"],
                "successful_profiles": ["balanced:medium", "visual_heavy:high"],
            },
        }],
    }))
    if with_outcome:
        library.outcomes_path.write_text(json.dumps({
            "template_id": "legacy-l1", "paper_id": "other",
            "profile_key": "visual_heavy:high", "validation_run": True,
            "accepted": True, "transfer_verified": True,
        }) + "\n")
    return library


def _ids(library, profile):
    return [item["template_id"] for item in library.retrieve(
        strategy="adapt", campaign_id="new-campaign", paper_id="third",
        paper_profile={"profile_key": profile, "visual_count": 2},
        iteration=1, recent_template_ids=[], random_seed=1,
    )]


def test_v5_l1_replays_only_strictly_verified_cross_paper_profile(tmp_path):
    library = _legacy_library(tmp_path, with_outcome=True)
    assert _ids(library, "visual_heavy:high") == ["legacy-l1"]
    assert _ids(library, "balanced:medium") == []


def test_v5_l1_without_outcome_journal_fails_closed_for_foreign_paper(tmp_path):
    library = _legacy_library(tmp_path, with_outcome=False)
    assert _ids(library, "visual_heavy:high") == []
    selected = library.retrieve(
        strategy="validate", campaign_id="new-campaign", paper_id="third",
        paper_profile={"profile_key": "visual_heavy:high", "visual_count": 2},
        iteration=1, recent_template_ids=[], random_seed=1,
    )
    assert [item["template_id"] for item in selected] == ["legacy-l1"]
