import json
import pytest

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
        "zone_topology": {
            "family_id": "classic_three_column",
            "primary_anchor_zone": "main",
            "zones": [{
                "zone_id": "main", "role": "main", "capacity": 8,
                "x": 0, "y": 0, "width": 1, "height": 1,
            }],
        },
        "usage": {
            "times_retrieved": 0,
            "successful_papers": ["paper-a"],
            "successful_profiles": ["balanced:medium"],
        },
    }


def _failure(library, paper_id, attempt, *, profile="visual_heavy:high"):
    library.record_usage(
        template_ids=["template"],
        campaign_id=f"campaign-{paper_id}-{attempt}",
        paper_id=paper_id,
        profile_key=profile,
        iteration=attempt,
        accepted=False,
        score=58,
        event_id=f"failure:{paper_id}:{attempt}",
        validation_run=True,
    )


def test_every_registered_template_enters_validation_queue(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    queue = json.loads(library.validation_queue_path.read_text())
    assert queue["schema_version"] == 2
    assert queue["pending"][0]["template_id"] == "template"
    assert queue["pending"][0]["validation_status"] == "pending"
    assert queue["pending"][0]["blocked_reason"] is None


def test_cross_paper_failure_remains_retryable_until_third_attempt(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    profile = {"profile_key": "visual_heavy:high", "visual_count": 2}

    for attempt in (1, 2):
        _failure(library, "paper-b", attempt)
        stored = library._load()["templates"][0]
        trial = stored["validation"]["paper_trials"]["paper-b"]
        assert trial["attempts_completed"] == attempt
        assert trial["status"] == "retry_pending"
        assert "paper-b" not in stored["validation"]["distinct_validation_papers"]
        assert library.has_validation_candidate(
            paper_id="paper-b", paper_profile=profile
        )

    _failure(library, "paper-b", 3)
    stored = library._load()["templates"][0]
    trial = stored["validation"]["paper_trials"]["paper-b"]
    assert trial["status"] == "failed_final"
    assert stored["validation"]["distinct_validation_papers"] == ["paper-b"]
    assert stored["validation"]["failed_papers"] == ["paper-b"]
    assert not library.has_validation_candidate(
        paper_id="paper-b", paper_profile=profile
    )


def test_two_final_paper_failures_learn_profile_scope(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    for paper_id in ("paper-b", "paper-c"):
        for attempt in (1, 2, 3):
            _failure(library, paper_id, attempt)

    stored = library._load()["templates"][0]
    assert stored["status"] == "paper_specific"
    assert stored["template_level"] == 0
    assert stored["validation"]["failed_events"] == 6
    assert set(stored["validation"]["failed_papers"]) == {"paper-b", "paper-c"}
    assert "visual_heavy:high" in stored["applicability"][
        "observed_inapplicable_profiles"
    ]
    assert stored["overall_score"] == 91


def test_success_after_two_failures_promotes_and_restores_profile(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    _failure(library, "paper-b", 1)
    _failure(library, "paper-b", 2)
    library.record_usage(
        template_ids=["template"], campaign_id="campaign-success",
        paper_id="paper-b", profile_key="visual_heavy:high",
        iteration=3, accepted=True, score=89,
        event_id="success:paper-b:3", validation_run=True,
        transfer_verified=True,
    )
    stored = library._load()["templates"][0]
    trial = stored["validation"]["paper_trials"]["paper-b"]
    assert trial["attempts_completed"] == 3
    assert trial["status"] == "passed"
    assert stored["template_level"] == 1
    assert "visual_heavy:high" not in stored["applicability"][
        "observed_inapplicable_profiles"
    ]
    selected = library.retrieve(
        strategy="adapt", campaign_id="campaign-next", paper_id="paper-c",
        paper_profile={"profile_key": "visual_heavy:high", "visual_count": 2},
        iteration=1, recent_template_ids=[], random_seed=1,
    )
    assert [item["template_id"] for item in selected] == ["template"]


def test_duplicate_committed_failure_is_idempotent(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    _failure(library, "paper-b", 1)
    _failure(library, "paper-b", 1)
    stored = library._load()["templates"][0]
    trial = stored["validation"]["paper_trials"]["paper-b"]
    assert trial["attempts_completed"] == 1
    assert stored["validation"]["failed_events"] == 1


def test_validation_snapshot_excludes_templates_saved_mid_batch(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    first = _template()
    first["template_id"] = "first"
    first["fingerprint"] = "first"
    assert library.register(first)["registered"]
    profile = {"profile_key": "visual_heavy:high", "visual_count": 2}
    snapshot = library.validation_candidate_ids(
        paper_id="paper-b", paper_profile=profile
    )
    assert snapshot == ["first"]

    second = _template()
    second["template_id"] = "second"
    second["fingerprint"] = "second"
    assert library.register(second)["registered"]
    chosen = library.retrieve(
        strategy="validate", campaign_id="campaign-b", paper_id="paper-b",
        paper_profile=profile, iteration=1, recent_template_ids=[],
        random_seed=1, validation_template_ids=snapshot,
    )
    assert [item["template_id"] for item in chosen] == ["first"]


def test_schema_v6_failure_migrates_to_one_retryable_attempt(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    template = _template()
    library.index_path.parent.mkdir(parents=True)
    library.index_path.write_text(json.dumps({
        "schema_version": 6,
        "templates": [template],
    }))
    library.outcomes_path.write_text(json.dumps({
        "template_id": "template", "campaign_id": "legacy-campaign",
        "paper_id": "paper-b", "profile_key": "visual_heavy:high",
        "iteration": 7, "accepted": False, "score": 58,
        "event_id": "legacy-campaign:7", "validation_run": True,
        "transfer_verified": False,
    }) + "\n")
    stored = library._load()["templates"][0]
    trial = stored["validation"]["paper_trials"]["paper-b"]
    assert trial["attempts_completed"] == 1
    assert trial["status"] == "retry_pending"
    assert "paper-b" not in stored["validation"]["distinct_validation_papers"]


def test_missing_topology_is_blocked_without_consuming_attempts(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    template = _template()
    template.pop("zone_topology")
    assert library.register(template)["registered"]
    profile = {"profile_key": "balanced:medium", "visual_count": 2}
    assert not library.has_validation_candidate(
        paper_id="paper-b", paper_profile=profile
    )
    stored = library._load()["templates"][0]
    assert stored["validation"]["blocked_reason"] == "missing_strict_topology"
    assert stored["validation"]["events"] == 0
    assert library.validation_blocked_candidates(paper_profile=profile) == [{
        "template_id": "template", "reason": "missing_strict_topology",
    }]


def test_success_restores_profile_after_two_distinct_final_failures(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    for paper_id in ("paper-b", "paper-c"):
        for attempt in (1, 2, 3):
            _failure(library, paper_id, attempt)
    blocked = library._load()["templates"][0]
    assert "visual_heavy:high" in blocked["applicability"][
        "observed_inapplicable_profiles"
    ]

    library.record_usage(
        template_ids=["template"], campaign_id="campaign-paper-d",
        paper_id="paper-d", profile_key="visual_heavy:high", iteration=1,
        accepted=True, score=92, event_id="success:paper-d:1",
        validation_run=True, transfer_verified=True,
    )
    restored = library._load()["templates"][0]
    assert restored["validation"]["paper_trials"]["paper-d"]["status"] == "passed"
    assert "visual_heavy:high" not in restored["applicability"][
        "observed_inapplicable_profiles"
    ]


def test_strict_validation_changes_only_validation_metadata_and_level(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    before = library._load()["templates"][0]
    identity = library.validation_identity("template")
    immutable = {
        key: before.get(key)
        for key in (
            "fingerprint",
            "family",
            "normalized_blueprint",
            "zone_topology",
            "template_design_score",
            "template_evaluation",
        )
    }
    usage_before = dict(before["usage"])
    evidence = {
        "artifact_kind": "validation_evidence",
        "saved": True,
        "candidate_id": "candidate-validation",
        "relative_dir": "validation_evidence/template/paper-b/candidate-validation",
    }

    library.record_usage(
        template_ids=["template"],
        campaign_id="validation-campaign",
        paper_id="paper-b",
        profile_key="visual_heavy:high",
        iteration=4,
        accepted=True,
        score=94,
        event_id="validation-campaign:4",
        validation_run=True,
        transfer_verified=True,
        candidate_id="candidate-validation",
        validation_evidence=evidence,
        expected_template_fingerprint=identity["fingerprint"],
        expected_topology_sha256=identity["topology_sha256"],
    )

    templates = library._load()["templates"]
    assert len(templates) == 1
    stored = templates[0]
    assert stored["usage"] == usage_before
    assert {key: stored.get(key) for key in immutable} == immutable
    assert stored["template_level"] == 1
    trial = stored["validation"]["paper_trials"]["paper-b"]
    assert trial["status"] == "passed"
    assert trial["attempts"][0]["candidate_id"] == "candidate-validation"
    assert trial["attempts"][0]["poster_artifact_saved"] is True
    assert trial["attempts"][0]["evidence"] == evidence


def test_validation_rejects_changed_source_template_identity(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]
    identity = library.validation_identity("template")
    with pytest.raises(ValueError, match="template_changed_during_validation"):
        library.record_usage(
            template_ids=["template"],
            campaign_id="validation-campaign",
            paper_id="paper-b",
            profile_key="visual_heavy:high",
            iteration=1,
            accepted=True,
            score=94,
            event_id="validation-campaign:1",
            validation_run=True,
            transfer_verified=True,
            expected_template_fingerprint=identity["fingerprint"],
            expected_topology_sha256="changed",
        )
    stored = library._load()["templates"][0]
    assert stored["validation"]["events"] == 0
    assert stored["usage"]["times_retrieved"] == 0


def test_unscored_preflight_failures_use_three_attempt_validation_semantics(tmp_path):
    library = TemplateLibrary(tmp_path, load_critic_config())
    assert library.register(_template())["registered"]

    for attempt in (1, 2, 3):
        library.record_usage(
            template_ids=["template"],
            campaign_id=f"preflight-{attempt}",
            paper_id="paper-preflight",
            profile_key="visual_heavy:high",
            iteration=attempt,
            accepted=False,
            score=None,
            event_id=f"preflight:{attempt}",
            validation_run=True,
            transfer_verified=False,
            transfer_reasons=["layout_preflight_failed"],
            poster_evaluated=False,
            validation_failure_reason="layout_preflight_failed",
        )
        trial = library._load()["templates"][0]["validation"][
            "paper_trials"
        ]["paper-preflight"]
        assert trial["attempts_completed"] == attempt
        assert trial["status"] == (
            "failed_final" if attempt == 3 else "retry_pending"
        )
        record = trial["attempts"][-1]
        assert record["poster_score"] is None
        assert record["poster_evaluated"] is False
        assert record["result"] == "layout_preflight_failed"

    stored = library._load()["templates"][0]
    assert stored["validation"]["distinct_validation_papers"] == [
        "paper-preflight"
    ]
    assert stored["validation"]["profile_outcomes"][
        "visual_heavy:high"
    ]["scores"] == []
