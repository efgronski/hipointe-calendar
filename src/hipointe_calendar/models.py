from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Chicago")


@dataclass(slots=True)
class Screening:
    performance_id: str
    movie_id: str
    title: str
    date: str
    showtime: str
    runtime_minutes: int
    url: str
    format: str | None = None
    director: str | None = None
    release_year: int | None = None
    language: str | None = None
    screening_note: str | None = None
    status: str = "confirmed"
    first_seen: str | None = None
    last_seen: str | None = None
    missing_count: int = 0

    def __post_init__(self) -> None:
        date.fromisoformat(self.date)
        time.fromisoformat(self.showtime)
        if not 1 <= int(self.runtime_minutes) <= 1440:
            raise ValueError(f"Invalid runtime: {self.runtime_minutes}")
        if self.status not in {"confirmed", "cancelled"}:
            raise ValueError(f"Invalid status: {self.status}")

    @property
    def start(self) -> datetime:
        return datetime.combine(date.fromisoformat(self.date), time.fromisoformat(self.showtime), TIMEZONE)

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.runtime_minutes)

    @property
    def uid(self) -> str:
        return f"hipointe-performance-{self.performance_id}@hipointe-calendar"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Screening":
        return cls(**value)
