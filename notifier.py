"""Send stocking notifications via the Telegram Bot API.

Only the standard library + ``requests`` are needed. The bot token and chat id
are read from environment variables by the caller and passed in -- nothing is
hardcoded here.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"
REPORT_URL = "https://www.gofishbc.com/stocked-fish/"

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 30


def _pretty_date(raw: str) -> str:
    """Convert an ISO date like ``2026-06-14`` to ``June 14, 2026``.

    Falls back to the original string if it cannot be parsed.
    """
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%B %-d, %Y")
    except ValueError:
        return raw


def _pretty_waterbody(name: str) -> str:
    """Turn an ALL-CAPS waterbody name into Title Case (e.g. STUMP -> Stump)."""
    return name.title() if name.isupper() else name


def _format_quantity(raw: str) -> str:
    """Format a quantity string with thousands separators when numeric."""
    try:
        return f"{int(float(raw)):,}"
    except (ValueError, TypeError):
        return raw


def format_message(events: list[dict[str, Any]]) -> str:
    """Build the Telegram message body for a list of new stocking events."""
    lines = ["\U0001F3A3 New fish stocked in the Lower Mainland!", ""]

    for event in events:
        waterbody = _pretty_waterbody(event.get("waterbody", "Unknown"))
        species = event.get("species", "Unknown")
        strain = event.get("strain", "").strip()
        genotype = event.get("genotype", "").strip()

        species_detail = species
        descriptor = " ".join(part for part in (strain.title() if strain.isupper() else strain, genotype) if part)
        if descriptor:
            species_detail = f"{species} ({descriptor})"

        lines.append(f"\U0001F4CD {waterbody}")
        lines.append(f"   Species: {species_detail}")
        lines.append(f"   Count: {_format_quantity(event.get('quantity', '?'))} fish")
        lines.append(f"   Date: {_pretty_date(event.get('date', ''))}")
        lines.append("")

    lines.append(f"Check details: {REPORT_URL}")
    return "\n".join(lines)


def send_telegram_message(token: str, chat_id: str, text: str) -> bool:
    """Send a message via Telegram with retries + exponential backoff.

    Returns ``True`` on success, ``False`` on failure. Never raises -- a failed
    notification should not crash the workflow.
    """
    if not token or not chat_id:
        logger.error("Telegram token or chat id missing; cannot send notification.")
        return False

    url = TELEGRAM_API_TEMPLATE.format(token=token)
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("Sending Telegram message (attempt %d/%d)...", attempt, MAX_ATTEMPTS)
            resp = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            logger.info("Telegram message sent successfully.")
            return True
        except requests.RequestException as exc:
            logger.warning("Telegram send attempt %d failed: %s", attempt, exc)
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_BASE_SECONDS ** attempt)

    logger.error("Failed to send Telegram message after %d attempts.", MAX_ATTEMPTS)
    return False
