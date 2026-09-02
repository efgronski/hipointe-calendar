from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .archive import load_archive, reconcile, save_archive
from .calendar import save_calendar
from .scraper import HiPointeScraper, MovieMetadata, ScrapeError


def update(archive_path: Path, output_path: Path, scraper: HiPointeScraper | None = None) -> int:
    previous = None
    if scraper is None:
        previous = load_archive(archive_path)
        known = {
            item.url: MovieMetadata(item.runtime_minutes, item.format, item.director, item.release_year, item.language)
            for item in previous
            if item.format or item.director or item.release_year or item.language or item.runtime_minutes != 120
        }
        scraper = HiPointeScraper(known_metadata=known)
    try:
        current = scraper.scrape()
    except ScrapeError:
        logging.exception("Scrape failed; archive and calendar were left untouched")
        return 1
    previous = previous if previous is not None else load_archive(archive_path)
    combined = reconcile(previous, current)
    save_archive(archive_path, combined)
    save_calendar(output_path, combined)
    for item in current[:8]:
        logging.info("%s %s-%s %s", item.date, item.start.strftime("%H:%M"), item.end.strftime("%H:%M"), item.title)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Update the Hi-Pointe Theatre calendar feed")
    parser.add_argument("--archive", type=Path, default=Path("data/screenings.json"))
    parser.add_argument("--output", type=Path, default=Path("output/hipointe.ics"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(update(args.archive, args.output))


if __name__ == "__main__":
    main()
