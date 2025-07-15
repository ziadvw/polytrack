from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo

from scraper import (
    filter_markets_by_date,
    get_day_price_change,
    get_ois,
    scrape_markets,
)

ET = ZoneInfo("America/New_York")

# Current formula is average % daily change for top 10 markets by OI
# ───────────────────────────── helpers ──────────────────────────────────────
def process_single_day(date_et: datetime, all_markets: List[Dict[str, Any]]
                       ) -> Tuple[str, float]:
    """Return (YYYY-MM-DD, avg % change) for one day."""
    day_str = f"{date_et:%Y-%m-%d}"
    day_start = date_et.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end   = day_start + timedelta(days=1)
    ts_start  = int(day_start.timestamp())
    ts_end    = int(day_end.timestamp())

    day_markets = filter_markets_by_date(all_markets, day_start, day_end)
    id_map = {m["conditionId"]: m["tokenId"] for m in day_markets if m.get("tokenId")}

    top = get_ois(day_markets, unix_timestamp=ts_start, top_n=10)
    if not top:
        return day_str, 0.0

    changes = [
        get_day_price_change(id_map[cid["id"]], ts_start, ts_end)
        for cid in top
        if cid["id"] in id_map
    ]
    avg = sum(changes) / len(changes) if changes else 0.0
    return day_str, round(avg, 3)


def write_scores(series: List[Dict[str, Any]], out_file: Path) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(series, indent=2))
    print(f"✅  Saved → {out_file}")


# ─────────────────────────────── main ───────────────────────────────────────
def backfill_scores(
    start_date: datetime,
    end_date: datetime,
    markets_file: Optional[str] = None,
) -> None:
    """Run daily calc over [start_date, end_date] inclusive."""
    # markets
    if markets_file:
        with open(markets_file, encoding="utf-8") as fp:
            markets = json.load(fp)
    else:
        markets = scrape_markets(active=False)

    # dates list
    dates = []
    cur = start_date
    while cur <= end_date:
        dates.append(cur)
        cur += timedelta(days=1)

    n_proc = max(1, cpu_count() - 1)
    with Pool(n_proc) as pool:
        results = pool.starmap(process_single_day, [(d, markets) for d in dates])

    series = [{"time": d, "value": v} for d, v in sorted(results, key=lambda t: t[0])]

    # write
    suffix = f"{start_date:%Y-%m-%d}" if start_date == end_date \
        else f"{start_date:%Y-%m-%d}-{end_date:%Y-%m-%d}"
    out_path = Path("data/backfills/scores") / f"scores_{suffix}.json"
    write_scores(series, out_path)


# ───────────────────────── CLI entrypoint ───────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill daily scores")
    ap.add_argument("start_date", help="YYYY-MM-DD")
    ap.add_argument("end_date", nargs="?", help="YYYY-MM-DD (optional)")
    ap.add_argument("-m", "--markets-file", dest="markets_file",
                    help="Existing markets JSON (else scrape fresh)")
    ns = ap.parse_args()

    try:
        start_dt = datetime.strptime(ns.start_date, "%Y-%m-%d").replace(tzinfo=ET)
        end_dt   = datetime.strptime(ns.end_date, "%Y-%m-%d").replace(tzinfo=ET) \
                   if ns.end_date else start_dt
    except ValueError as e:
        raise SystemExit(f"❌  Invalid date: {e}")

    backfill_scores(start_dt, end_dt, ns.markets_file)
