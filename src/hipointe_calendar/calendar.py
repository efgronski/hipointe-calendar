from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from icalendar import Calendar, Event

from .models import Screening

LOCATION = "Hi-Pointe Theatre\n1005 McCausland Ave\nSt. Louis, MO 63117"


def _description(item: Screening) -> str:
    fields = [
        ("Runtime", f"{item.runtime_minutes} minutes"), ("Format", item.format),
        ("Director", item.director), ("Release Year", item.release_year),
        ("Language", item.language), ("Screening note", item.screening_note),
    ]
    lines = [f"{label}: {value}" for label, value in fields if value not in (None, "")]
    lines.extend(["", item.url])
    return "\n".join(lines)


def build_calendar(screenings: list[Screening]) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Hi-Pointe Theatre Calendar//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "Hi-Pointe Theatre")
    cal.add("x-wr-timezone", "America/Chicago")
    stamp = datetime.now(timezone.utc)
    for item in screenings:
        event = Event()
        event.add("uid", item.uid)
        event.add("summary", f"🎬 {item.title}")
        event.add("dtstart", item.start)
        event.add("dtend", item.end)
        event.add("dtstamp", stamp)
        event.add("location", LOCATION)
        event.add("description", _description(item))
        event.add("url", item.url)
        event.add("status", "CANCELLED" if item.status == "cancelled" else "CONFIRMED")
        event.add("sequence", item.missing_count if item.status == "cancelled" else 0)
        cal.add_component(event)
    return cal.to_ical()


def save_calendar(path: Path, screenings: list[Screening]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_calendar(screenings))
