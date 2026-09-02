from datetime import date
from pathlib import Path

from icalendar import Calendar

from hipointe_calendar.archive import reconcile
from hipointe_calendar.calendar import build_calendar
from hipointe_calendar.cli import update
from hipointe_calendar.models import Screening
from hipointe_calendar.scraper import MovieMetadata, ScrapeError, parse_calendar_page, parse_movie_metadata, parse_showtime


def screening(pid="100", day="2026-09-05", at="16:00", **kwargs):
    values = dict(performance_id=pid, movie_id="example", title="Example Movie", date=day,
                  showtime=at, runtime_minutes=120, url="https://hipointetheatre.org/movies/example/")
    values.update(kwargs)
    return Screening(**values)


def calendar_fixture(days):
    cells = []
    for day, showtimes in days:
        times = "".join(f'<li><a class="showtime" data-showtime_id="{pid}">{text}</a></li>' for pid, text in showtimes)
        card = (f'<div class="show"><a href="https://hipointetheatre.org/movies/example/"><h2>Example Movie</h2></a>'
                f'<ol class="showtimes">{times}</ol></div>').replace('"', '&quot;')
        cells.append(f'<div class="calendar-day" data-date="{day}"><li class="calendar-show-item" data-show-card="{card}"></li></div>')
    return "<html><body>" + "".join(cells) + "</body></html>"


def test_one_date_one_showtime():
    items, _, _ = parse_calendar_page(calendar_fixture([("2026-09-05", [("1", "4:00 pm")])]))
    assert [(x.date, x.showtime) for x in items] == [("2026-09-05", "16:00")]


def test_multiple_dates_and_multiple_times_same_date():
    items, _, _ = parse_calendar_page(calendar_fixture([
        ("2026-09-05", [("1", "12:30 pm"), ("2", "3:00 pm")]),
        ("2026-09-06", [("3", "2:15 pm")]),
    ]))
    assert {(x.performance_id, x.date, x.showtime) for x in items} == {
        ("1", "2026-09-05", "12:30"), ("2", "2026-09-05", "15:00"), ("3", "2026-09-06", "14:15")}


def test_runtime_end_and_stable_uid():
    item = screening(runtime_minutes=124)
    assert item.end.isoformat() == "2026-09-05T18:04:00-05:00"
    assert item.uid == screening().uid == "hipointe-performance-100@hipointe-calendar"


def test_duplicate_performance_is_removed():
    page = calendar_fixture([("2026-09-05", [("1", "4:00 pm"), ("1", "4:00 pm")])])
    assert len(parse_calendar_page(page)[0]) == 1


def test_missing_optional_metadata_is_clean():
    item = screening()
    event = next(c for c in Calendar.from_ical(build_calendar([item])).walk() if c.name == "VEVENT")
    description = str(event["description"])
    assert "None" not in description and "Director:" not in description


def test_annotated_showtime():
    assert parse_showtime("3:00 pm w/ FOX") == ("15:00", "w/ FOX")


def test_json_ld_metadata():
    page = '<script type="application/ld+json">{"@graph":[{"@type":"Movie","duration":"PT1H58M","dateCreated":"1977-12-16","director":[{"name":"John Doe"}],"inLanguage":"English"}]}</script><p>Format: 35mm Film Release Year: 1977</p>'
    meta = parse_movie_metadata(page)
    assert meta == MovieMetadata(118, "35mm Film", "John Doe", 1977, "English")


def test_archive_preserves_history_and_cancels_future_after_two_misses():
    past = screening("past", "2026-01-01")
    future = screening("future", "2026-12-01")
    first = reconcile([past, future], [], today=date(2026, 9, 2))
    assert {x.performance_id for x in first} == {"past", "future"}
    assert next(x for x in first if x.performance_id == "future").status == "confirmed"
    second = reconcile(first, [], today=date(2026, 9, 2))
    assert next(x for x in second if x.performance_id == "future").status == "cancelled"


def test_failed_scrape_does_not_touch_files(tmp_path: Path):
    archive = tmp_path / "screenings.json"
    output = tmp_path / "hipointe.ics"
    archive.write_text("known-good", encoding="utf-8")
    output.write_text("known-good-calendar", encoding="utf-8")

    class Broken:
        def scrape(self):
            raise ScrapeError("boom")

    assert update(archive, output, Broken()) == 1
    assert archive.read_text() == "known-good"
    assert output.read_text() == "known-good-calendar"
