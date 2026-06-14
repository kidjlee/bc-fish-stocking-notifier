"""Entry point: scrape GoFishBC, detect new stockings, notify via Telegram.

Run by GitHub Actions on a daily schedule. Designed to fail *soft*: any scrape
or network error is logged and the process exits 0 so the workflow stays green
and the persisted state file is never corrupted.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

import notifier
import scraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fish-notifier")

DATA_FILE = Path(__file__).parent / "data" / "seen_events.json"
REGION = scraper.DEFAULT_REGION


def load_seen_ids() -> tuple[set[str], bool]:
    """Load previously seen event ids.

    Returns ``(seen_ids, is_first_run)``. ``is_first_run`` is True when the
    state file is missing or empty, which suppresses the initial notification
    flood (the historical table contains hundreds of past events).
    """
    if not DATA_FILE.exists():
        logger.info("No state file at %s -- treating this as the first run.", DATA_FILE)
        return set(), True

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        seen = set(data.get("seen_event_ids", []))
        is_first_run = len(seen) == 0
        logger.info("Loaded %d previously seen event ids.", len(seen))
        return seen, is_first_run
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read state file (%s); treating as first run.", exc)
        return set(), True


def save_seen_ids(seen_ids: set[str]) -> None:
    """Persist the set of seen event ids back to the JSON state file."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"seen_event_ids": sorted(seen_ids)}
    DATA_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Saved %d seen event ids to %s.", len(seen_ids), DATA_FILE)


def main() -> int:
    load_dotenv()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    try:
        events: list[dict[str, Any]] = scraper.scrape_stocking_events(REGION)
    except Exception as exc:  # noqa: BLE001 - never crash the workflow on scrape failure
        logger.warning("Scrape failed, exiting without changes: %s", exc)
        return 0

    if not events:
        logger.warning("No events parsed (possible site change or empty report); nothing to do.")
        return 0

    seen_ids, is_first_run = load_seen_ids()
    current_ids = {event["id"] for event in events}

    if is_first_run:
        logger.info("First run: seeding state with %d events, no notification sent.", len(current_ids))
        save_seen_ids(current_ids)
        return 0

    new_events = [event for event in events if event["id"] not in seen_ids]

    if not new_events:
        logger.info("No new stocking events. Silent run.")
        return 0

    logger.info("Found %d new stocking event(s).", len(new_events))
    message = notifier.format_message(new_events)
    print(message)

    sent = notifier.send_telegram_message(token, chat_id, message)

    if sent:
        save_seen_ids(seen_ids | current_ids)
    else:
        # Don't mark events as seen if the notification failed, so we retry next run.
        logger.warning("Notification not sent; leaving state unchanged to retry next run.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
