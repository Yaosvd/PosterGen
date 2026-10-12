"""Explicit, model-free accounting/journal repair for one offline Campaign."""

import argparse
import json
import re
from pathlib import Path

from src.config.critic_config import load_critic_config
from src.templates.library import LoopStorage
from src.workflow.campaign import CampaignHandle, CampaignManager


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--store-root", default="storage/critic_loop")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.campaign_id) or args.campaign_id in {".", ".."}:
        parser.error("Invalid Campaign ID")
    root = Path(args.store_root).resolve()
    path = root / "campaigns" / args.campaign_id
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    handle = CampaignHandle(args.campaign_id, path, manifest, True, 0)
    config = load_critic_config()
    manager = CampaignManager(root, config)
    storage = LoopStorage(root, config)
    with manager.lease(handle):
        before = manager.load_campaign_state(handle)
        if not manager.reconcile_committed_summaries(handle):
            raise ValueError("Incomplete commit history; no accounting correction applied")
        corrections = storage.invalidate_uncommitted_rejections(path)
        after = manager.load_campaign_state(handle)
    print(json.dumps({
        "campaign_id": args.campaign_id, "status": after.get("status"),
        "last_completed_iteration": after.get("last_completed_iteration", 0),
        "before": {key: before.get(key, 0) for key in ("accepted_count", "rejected_count", "template_count")},
        "after": {key: after.get(key, 0) for key in ("accepted_count", "rejected_count", "template_count")},
        "legacy_rejection_invalidations_added": corrections,
        "batch_started": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
