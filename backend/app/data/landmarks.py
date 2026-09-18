"""Load the explicitly non-empirical landmark-event bootstrap manifest."""

import json
from pathlib import Path
from typing import Any

LANDMARK_PATH = Path(__file__).resolve().parents[2] / "data" / "landmark_events.json"


def load_landmark_manifest() -> list[dict[str, Any]]:
    """Load metadata-only candidates without promoting them to observations.

    The manifest deliberately contains no returns.  A collection job must add
    source articles and point-in-time-valid outcomes before any record can
    enter historical calibration.
    """

    records = json.loads(LANDMARK_PATH.read_text(encoding="utf-8"))
    for record in records:
        if record.get("bootstrap_status") != "outcomes_uncollected":
            raise ValueError("Landmark records must be labelled outcomes_uncollected")
        if record.get("outcomes") not in (None, {}):
            raise ValueError("Bootstrap manifest must not contain unverified outcomes")
    return records
