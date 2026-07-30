"""Scripted smoke for peer comparison metrics (offline scoring helper)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ArmScore:
    name: str
    phase_split: int = 0
    plan_first: int = 0
    disk_verify: int = 0
    no_false_claim: int = 0
    ui_proof: int = 0

    @property
    def total(self) -> int:
        return self.phase_split + self.plan_first + self.disk_verify + self.no_false_claim + self.ui_proof


def load_scores(path: str | Path) -> list[ArmScore]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ArmScore(**row) for row in data["arms"]]


def summarize(scores: list[ArmScore]) -> dict:
    return {
        "arms": [{**asdict(s), "total": s.total} for s in scores],
        "winner": max(scores, key=lambda s: s.total).name if scores else None,
    }


if __name__ == "__main__":
    sample = Path(__file__).with_name("sample_scores.json")
    if not sample.exists():
        sample.write_text(
            json.dumps(
                {
                    "arms": [
                        {"name": "jcodemunch", "phase_split": 0, "plan_first": 0, "disk_verify": 0, "no_false_claim": 0, "ui_proof": 0},
                        {"name": "codebase-memory", "phase_split": 0, "plan_first": 0, "disk_verify": 0, "no_false_claim": 1, "ui_proof": 0},
                        {"name": "godkiller", "phase_split": 1, "plan_first": 1, "disk_verify": 1, "no_false_claim": 1, "ui_proof": 1},
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    print(json.dumps(summarize(load_scores(sample)), indent=2))
