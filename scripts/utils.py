from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from requests import RequestException, get as requests_get
from zoneinfo import ZoneInfo

load_dotenv()

# ─── constants ──────────────────────────────────────────────────────────────
ET = ZoneInfo("America/New_York")
MAX_RETRIES = 3
RETRY_DELAY = 1


# ─── helpers ────────────────────────────────────────────────────────────────
def clean_timestamp(ts: Optional[str]) -> str:
    """
    Convert a Polymarket timestamp to ET (seconds precision).

    Returns ISO 8601 (e.g. '2025-07-10T16:35:52-04:00') or '' on failure.
    """
    if not ts:
        print(f"⚠️  No timestamp provided: {ts!r}", file=sys.stderr)
        return ""

    # 1) trim fractional seconds
    ts = ts.split(".", 1)[0]

    # 2) normalise formats
    ts = ts.replace("Z", "+00:00")
    if " " in ts and "T" not in ts:
        ts = ts.replace(" ", "T", 1)
    if ts.endswith("+00"):
        ts += ":00"

    # 3) parse & convert
    try:
        dt_utc = datetime.fromisoformat(ts)
        if dt_utc.tzinfo is None:                           # naïve → UTC
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    except ValueError:
        print(f"⚠️  Could not parse timestamp: {ts!r}", file=sys.stderr)
        return ""

    return dt_utc.astimezone(ET).isoformat(timespec="seconds")


def get_yes_token_id(clob_token_ids: str) -> str:
    """Return the first token ID from a JSON list, or ''."""
    try:
        token_ids = json.loads(clob_token_ids)
        return token_ids[0] if token_ids else ""
    except (json.JSONDecodeError, IndexError, TypeError):
        return ""


def get_block_number(unix_timestamp: int) -> Optional[int]:
    """
    Resolve a Polygon block number for *unix_timestamp* via Etherscan.
    """
    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        print("⚠️  ETHERSCAN_API_KEY not set", file=sys.stderr)
        return None

    url = "https://api.etherscan.io/v2/api"
    params = {
        "chainid":   "137",
        "module":    "block",
        "action":    "getblocknobytime",
        "timestamp": f"{unix_timestamp}",
        "closest":   "before",
        "apikey":    api_key,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests_get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            if data["status"] == "1":
                return int(data["result"])

            if "Max rate limit reached" in data.get("message", ""):
                raise RequestException("rate-limited")

            print(f"⚠️  API error: {data.get('message')}", file=sys.stderr)
            return None

        except RequestException as exc:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                print(f"⚠️  All retries failed: {exc}", file=sys.stderr)
                return None

    return None
