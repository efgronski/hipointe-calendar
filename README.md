# Hi-Pointe Theatre Calendar

An unofficial, self-updating calendar feed for movie screenings at the [Hi-Pointe Theatre](https://hipointetheatre.org/) in St. Louis. Every advertised showtime becomes a timed event in the `America/Chicago` time zone, with its end time calculated from the movie runtime.

This personal project is not affiliated with Cinema St. Louis or the Hi-Pointe Theatre.

## Subscribe

After publishing this repository as described below, the feed URL is:

```text
https://YOUR-USERNAME.github.io/hipointe-calendar/hipointe.ics
```

- **Apple Calendar:** File → New Calendar Subscription, paste the URL, and choose a refresh interval.
- **Google Calendar:** Other calendars → From URL, then paste the URL.
- **Outlook on the web:** Add calendar → Subscribe from web, then paste the URL.

Calendar applications choose their own refresh schedule. Google Calendar in particular may take many hours to notice feed changes; the repository can update before a subscribed client displays the change.

## How it works

The scraper reads the server-rendered [Hi-Pointe calendar](https://hipointetheatre.org/calendar/). Each calendar day contains embedded movie cards whose showtimes have stable Filmbot performance IDs. Those IDs become deterministic iCalendar UIDs, avoiding duplicates even when a movie belongs to several series. Each unique movie detail page is fetched once to read its schema.org `Movie` data (runtime, director, year, and language) plus the displayed format.

Metadata already present in the archive is reused, and requests for new movie pages are deliberately spaced out. If a detail page is unavailable or rate-limited, the screening is still included with a conservative 120-minute fallback runtime and without invented metadata.

`data/screenings.json` is a persistent archive. Successful runs merge new data into it instead of deleting old screenings. Historical events stay forever. A future performance missing from two consecutive successful scrapes is marked `CANCELLED`; this is conservative because the site does not expose a separate cancellation feed. A rescheduled show normally receives a new performance ID, so clients see the old event cancelled and the new event added. Failed or empty scrapes leave both archive and calendar untouched.

## Run locally

Python 3.11 or newer is required.

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
python -m hipointe_calendar
```

The generated feed is `output/hipointe.ics`. Use `python -m hipointe_calendar --verbose` for request and parsing logs.

## Automatic updates

`.github/workflows/update-calendar.yml` runs at approximately 12:17 AM and 12:17 PM Central time (the exact local hour shifts with daylight saving time because GitHub cron uses UTC). It installs dependencies, runs tests, updates the archive/feed, and commits only when either generated file changed. Its path filter prevents the bot commit from recursively triggering the update workflow.

To run it manually, open **Actions → Update calendar → Run workflow** in GitHub.

## Publish with GitHub Pages

1. Create a public GitHub repository named `hipointe-calendar` and push this project to its `main` branch.
2. In the repository, open **Settings → Pages**.
3. Under **Build and deployment**, select **GitHub Actions** as the source.
4. Open **Actions → Publish calendar** and run it once (future feed changes deploy automatically).
5. Visit `https://YOUR-USERNAME.github.io/hipointe-calendar/hipointe.ics`, replacing `YOUR-USERNAME` with the repository owner's username.

The update workflow needs **Settings → Actions → General → Workflow permissions → Read and write permissions** so it can commit the generated files. The Pages workflow has only the permissions needed to read the repository and deploy Pages.

## Troubleshooting

- **The update action failed:** open its log. A temporary 403, 429, or network error is safe—the known-good feed is not overwritten. Retry later rather than repeatedly rerunning it.
- **Events have a two-hour duration:** the movie detail request failed and the fallback was used. A later newly discovered performance can supply richer metadata; existing archived metadata is retained.
- **The subscription URL returns 404:** confirm Pages uses **GitHub Actions**, then rerun **Publish calendar**.
- **Changes are on GitHub but not in the calendar app:** wait for the calendar client's next refresh, or remove and re-add the subscription while testing.
- **A future event disappeared:** inspect `data/screenings.json`; cancelled performances remain archived with `"status": "cancelled"` and are emitted with iCalendar `STATUS:CANCELLED`.

## Development

The important behavior is covered by fixtures and unit tests: multiple dates, multiple showtimes per date, annotated times, stable IDs, DST-aware duration calculations, duplicate removal, missing metadata, archive preservation/cancellation, and safe failure behavior.
