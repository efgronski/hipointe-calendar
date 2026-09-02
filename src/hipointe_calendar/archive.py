from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from .models import Screening


def load_archive(path: Path) -> list[Screening]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Screening.from_dict(item) for item in data.get("screenings", [])]


def reconcile(previous: list[Screening], current: list[Screening], *, today: date | None = None) -> list[Screening]:
    today = today or date.today()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    old = {x.performance_id: x for x in previous}
    fresh = {x.performance_id: x for x in current}
    result: dict[str, Screening] = {}
    for performance_id, item in fresh.items():
        item.first_seen = old.get(performance_id, item).first_seen or now
        item.last_seen = now
        item.missing_count = 0
        item.status = "confirmed"
        result[performance_id] = item
    for performance_id, item in old.items():
        if performance_id in fresh:
            continue
        if date.fromisoformat(item.date) >= today and item.status == "confirmed":
            item.missing_count += 1
            if item.missing_count >= 2:
                item.status = "cancelled"
        result[performance_id] = item
    return sorted(result.values(), key=lambda x: (x.date, x.showtime, x.title))


def save_archive(path: Path, screenings: list[Screening]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "screenings": [x.to_dict() for x in screenings]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
