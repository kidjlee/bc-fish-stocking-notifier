"""Fetch and parse the GoFishBC stocking report.

The stocking report at https://www.gofishbc.com/stocked-fish/ is rendered
server-side: requesting the page with a ``region`` query parameter returns the
fully populated HTML table (id ``report_table``). No JavaScript rendering or
headless browser is required -- a plain HTTP GET plus BeautifulSoup is enough.

The region filter value for the Lower Mainland (Region 2) is the literal string
``LOWER MAINLAND`` (the site filters by region *name*, not number).
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

STOCKING_URL = "https://www.gofishbc.com/stocked-fish/"
DEFAULT_REGION = "LOWER MAINLAND"

# A realistic browser User-Agent. Some WAFs reject the default requests UA.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Column order of the rendered #report_table, used to map <td> cells to keys.
COLUMNS = [
    "date",
    "waterbody",
    "town",
    "species",
    "strain",
    "genotype",
    "life_stage",
    "avg_size_g",
    "quantity",
]

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 30


def fetch_page(region: str = DEFAULT_REGION, *, session: requests.Session | None = None) -> str:
    """Fetch the stocking report HTML for a region with retries + backoff.

    Raises the last ``requests`` exception if all attempts fail so the caller
    can decide how to handle a total failure.
    """
    sess = session or requests.Session()
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    params = {"region": region}

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("Fetching stocking report (attempt %d/%d) for region=%r", attempt, MAX_ATTEMPTS, region)
            resp = sess.get(
                STOCKING_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Fetch attempt %d failed: %s", attempt, exc)
            if attempt < MAX_ATTEMPTS:
                sleep_for = BACKOFF_BASE_SECONDS ** attempt
                logger.info("Retrying in %ds...", sleep_for)
                time.sleep(sleep_for)

    raise last_error if last_error else RuntimeError("Failed to fetch stocking report")


def event_id(event: dict[str, Any]) -> str:
    """Return a stable, unique id for a stocking event used for de-duplication."""
    key = "|".join(
        str(event.get(field, ""))
        for field in ("date", "waterbody", "town", "species", "strain", "genotype", "life_stage", "quantity")
    )
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def parse_stocking_events(html: str) -> list[dict[str, Any]]:
    """Parse the stocking report table out of the page HTML.

    Returns a list of event dicts (each with the COLUMNS keys plus ``id``).
    Returns an empty list if the table cannot be found.
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="report_table")
    if table is None:
        logger.warning("Could not find #report_table in page HTML; site layout may have changed.")
        return []

    body = table.find("tbody")
    rows = body.find_all("tr") if body else table.find_all("tr")

    events: list[dict[str, Any]] = []
    for row in rows:
        cells = [cell.get_text(strip=True) for cell in row.find_all("td")]
        if len(cells) < len(COLUMNS):
            continue
        event = dict(zip(COLUMNS, cells))
        event["id"] = event_id(event)
        events.append(event)

    logger.info("Parsed %d stocking events from report.", len(events))
    return events


def scrape_stocking_events(region: str = DEFAULT_REGION) -> list[dict[str, Any]]:
    """High-level helper: fetch + parse stocking events for a region."""
    html = fetch_page(region)
    return parse_stocking_events(html)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sample = scrape_stocking_events()
    print(f"Found {len(sample)} events. First few:")
    for item in sample[:5]:
        print(item)
