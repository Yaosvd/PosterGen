import json

from src.config.critic_config import load_critic_config
from src.templates.library import TemplateLibrary


def _template():
    return {
        "template_id": "template",
        "status": "paper_specific",
        "family": "classic_three_column",
        "fingerprint": "unique-template",
        "source_paper_id": "paper-a",
        "source_profile": "balanced:medium",
        "overall_score": 91,
        "signature_vector": [0.2, 0.4],
        "applicability": {"preferred_visual_count": [0, 10]},
        "layout_principles": ["clear hierarchy"],
        "normalized_blueprint": [],
        "usage": {
            "times_retrieved": 0,
            "successful_papers": ["paper-a"],
            "successful_profiles": ["balanced:medium"],
        },
    }


def test_every_registered_template_enters_validation_queue(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    queue = json.loads(library.validation_queue_path.read_text())
    assert queue["pending"][0]["template_id"] == "template"
    assert queue["pending"][0]["validation_status"] == "pending"


def test_failed_validation_keeps_template_and_learns_scope(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    for iteration, paper_id in enumerate(("paper-b", "paper-c"), start=1):
        library.record_usage(
            template_ids=["template"],
            campaign_id=f"campaign-{iteration}",
            paper_id=paper_id,
            profile_key="visual_heavy:high",
            iteration=iteration,
            accepted=False,
            score=58,
            event_id=f"failure:{iteration}",
            validation_run=True,
        )

    stored = json.loads(library.index_path.read_text())["templates"][0]
    assert stored["status"] == "paper_specific"
    assert stored["template_level"] == 0
    assert stored["validation"]["failed_events"] == 2
    assert "visual_heavy:high" in stored["applicability"][
        "observed_inapplicable_profiles"
    ]
    assert stored["overall_score"] == 91
