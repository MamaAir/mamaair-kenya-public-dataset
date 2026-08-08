from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def daily(week: int, day: int, cumulative: int, marker: Any) -> dict[str, Any]:
    return {
        "gestation_week": week,
        "day_of_week": day,
        "cumulative_pregnancy_day": cumulative,
        "preservation_probe": marker,
    }


def trajectory(track_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "track_id": track_id,
        "static_profile": {"profile_probe": track_id, "nullable": None},
        "pregnancy_summary": {
            "trajectory_overview": {
                "starting_gestation_week": records[0]["gestation_week"],
                "weeks_tracked": 1,
                "trajectory_arc": "test-only-context",
            }
        },
        "weekly_summaries": [],
        "daily_records": records,
    }


def dataset() -> dict[str, Any]:
    return {
        "dataset_metadata": {"dataset_id": "mamaair-ssa-climate-maternal-wq1"},
        "trajectories": [
            trajectory(
                "WQ1-002",
                [daily(8, 1, 1, {"nested": [2, None]}), daily(8, 2, 2, 2.25)],
            ),
            trajectory(
                "WQ1-001",
                [daily(1, 1, 1, {"nested": [1, False]}), daily(1, 2, 2, 1.25)],
            ),
        ],
    }


def write_dataset(path: Path) -> None:
    path.write_text(json.dumps(dataset()), encoding="utf-8")
