from __future__ import annotations

import html
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import Screening

LOG = logging.getLogger(__name__)
BASE_URL = "https://hipointetheatre.org"
CALENDAR_URL = f"{BASE_URL}/calendar/"
TIME_RE = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<meridiem>[ap])\.?m\.?(?P<note>.*)", re.I)


class ScrapeError(RuntimeError):
    pass


@dataclass(slots=True)
class MovieMetadata:
    runtime_minutes: int | None = None
    format: str | None = None
    director: str | None = None
    release_year: int | None = None
    language: str | None = None


def parse_showtime(value: str) -> tuple[str, str | None]:
    match = TIME_RE.search(" ".join(value.split()))
    if not match:
        raise ValueError(f"Unrecognized showtime: {value!r}")
    hour = int(match["hour"]) % 12 + (12 if match["meridiem"].lower() == "p" else 0)
    minute = int(match["minute"])
    if minute > 59:
        raise ValueError(f"Invalid showtime: {value!r}")
    note = match["note"].strip(" -–—,()") or None
    return f"{hour:02d}:{minute:02d}", note


def _duration_minutes(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", value)
    if not match:
        return None
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)


def parse_movie_metadata(page: str) -> MovieMetadata:
    soup = BeautifulSoup(page, "html.parser")
    movie: dict = {}
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        objects = data.get("@graph", [data]) if isinstance(data, dict) else data
        movie = next((item for item in objects if isinstance(item, dict) and item.get("@type") == "Movie"), movie)
    director = movie.get("director")
    if isinstance(director, list):
        director = ", ".join(x.get("name", "") for x in director if isinstance(x, dict)).strip(", ")
    elif isinstance(director, dict):
        director = director.get("name")
    year = None
    if movie.get("dateCreated"):
        match = re.search(r"\b(18|19|20)\d{2}\b", str(movie["dateCreated"]))
        year = int(match.group()) if match else None
    text = " ".join(soup.get_text(" ", strip=True).split())
    fmt = re.search(r"Format:\s*([^|]+?)(?=\s+Release Year:|\s+Language:|$)", text, re.I)
    return MovieMetadata(
        runtime_minutes=_duration_minutes(movie.get("duration")),
        format=fmt.group(1).strip() if fmt else None,
        director=director or None,
        release_year=year,
        language=movie.get("inLanguage") or None,
    )


def _movie_id(url: str) -> str:
    return urlparse(url).path.rstrip("/").split("/")[-1]


def parse_calendar_page(page: str, metadata: dict[str, MovieMetadata] | None = None) -> tuple[list[Screening], str | None, set[str]]:
    soup = BeautifulSoup(page, "html.parser")
    screenings: list[Screening] = []
    movie_urls: set[str] = set()
    metadata = metadata or {}
    for day in soup.select(".calendar-day[data-date]"):
        day_value = day.get("data-date", "")
        try:
            datetime.strptime(day_value, "%Y-%m-%d")
        except ValueError:
            LOG.warning("Skipping invalid calendar date %r", day_value)
            continue
        for card in day.select(".calendar-show-item[data-show-card]"):
            fragment = BeautifulSoup(html.unescape(card.get("data-show-card", "")), "html.parser")
            title_node = fragment.select_one("h2")
            detail_link = fragment.select_one('a[href*="/movies/"]')
            if not title_node or not detail_link:
                continue
            title = title_node.get_text(" ", strip=True)
            url = urljoin(BASE_URL, detail_link.get("href", ""))
            movie_urls.add(url)
            movie_id = _movie_id(url)
            meta = metadata.get(url, MovieMetadata())
            runtime = meta.runtime_minutes or 120
            for showtime in fragment.select(".showtime[data-showtime_id]"):
                performance_id = str(showtime.get("data-showtime_id", "")).strip()
                if not performance_id:
                    continue
                try:
                    parsed_time, note = parse_showtime(showtime.get_text(" ", strip=True))
                except ValueError as exc:
                    LOG.warning("%s", exc)
                    continue
                screenings.append(Screening(
                    performance_id=performance_id, movie_id=movie_id, title=title,
                    date=day_value, showtime=parsed_time, runtime_minutes=runtime, url=url,
                    format=meta.format, director=meta.director, release_year=meta.release_year,
                    language=meta.language, screening_note=note,
                ))
    next_link = soup.select_one('a[rel="next"], a[aria-label="Next Month"], a.next-month')
    next_url = urljoin(BASE_URL, next_link.get("href")) if next_link and next_link.get("href") else None
    unique = {item.performance_id: item for item in screenings}
    return list(unique.values()), next_url, movie_urls


class HiPointeScraper:
    def __init__(self, session: requests.Session | None = None, timeout: int = 30, max_months: int = 4,
                 known_metadata: dict[str, MovieMetadata] | None = None, detail_delay: float = 0.75):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_months = max_months
        self.known_metadata = known_metadata or {}
        self.detail_delay = detail_delay
        self.session.headers.update({"User-Agent": "HiPointeCalendar/0.1 (personal calendar feed; respectful twice-daily fetch)"})

    def _get(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def scrape(self) -> list[Screening]:
        try:
            pages: list[str] = []
            url: str | None = CALENDAR_URL
            seen_urls: set[str] = set()
            all_movie_urls: set[str] = set()
            for _ in range(self.max_months):
                if not url or url in seen_urls:
                    break
                seen_urls.add(url)
                page = self._get(url)
                pages.append(page)
                _, url, movie_urls = parse_calendar_page(page)
                all_movie_urls.update(movie_urls)
            details: dict[str, MovieMetadata] = dict(self.known_metadata)
            for movie_url in sorted(all_movie_urls):
                if movie_url in details:
                    continue
                try:
                    if self.detail_delay:
                        time.sleep(self.detail_delay)
                    details[movie_url] = parse_movie_metadata(self._get(movie_url))
                except requests.RequestException as exc:
                    LOG.warning("Could not fetch metadata for %s: %s", movie_url, exc)
            screenings: list[Screening] = []
            for page in pages:
                parsed, _, _ = parse_calendar_page(page, details)
                screenings.extend(parsed)
            unique = {item.performance_id: item for item in screenings}
            if not unique:
                raise ScrapeError("No screenings found; refusing to replace the known-good feed")
            LOG.info("Parsed %d unique screenings from %d month page(s)", len(unique), len(pages))
            return sorted(unique.values(), key=lambda x: (x.date, x.showtime, x.title))
        except requests.RequestException as exc:
            raise ScrapeError(f"Hi-Pointe request failed: {exc}") from exc
