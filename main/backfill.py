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
                       ) -> Tuple[str, float, List[Dict[str, Any]]]:
    """Return (YYYY-MM-DD, avg % change, top10 with price changes) for one day."""
    day_str = f"{date_et:%Y-%m-%d}"
    day_start = date_et.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end   = day_start + timedelta(days=1)
    ts_start  = int(day_start.timestamp())
    ts_end    = int(day_end.timestamp())

    day_markets = filter_markets_by_date(all_markets, day_start, day_end)
    id_map = {m["conditionId"]: m for m in day_markets if m.get("tokenId")}

    top = get_ois(day_markets, unix_timestamp=ts_start, top_n=10)
    if not top:
        return day_str, 0.0, []

    top10_with_changes = []
    total_abs = 0.0
    for cid in top:
        cond_id = cid["id"]
        m = id_map.get(cond_id)
        if not m:
            continue
        token_id = m["tokenId"]
        change = get_day_price_change(token_id, ts_start, ts_end)
        top10_with_changes.append({
            "conditionId": cond_id,
            "tokenId": token_id,
            "question": m.get("question"),
            "priceChange": round(change, 3)
        })
        total_abs += abs(change)
    avg = sum(abs(m["priceChange"]) for m in top10_with_changes) / len(top10_with_changes) if top10_with_changes else 0.0
    return day_str, round(avg, 3), top10_with_changes


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

    series = []
    for d, v, top10 in sorted(results, key=lambda t: t[0]):
        entry = {"time": d, "value": v}
        events = []
        if v > 8:
            # get top 10 markets with abs(priceChange) > 10%, ranked by abs(priceChange)
            top10_high_movers = sorted(
                [m for m in top10 if abs(m.get("priceChange", 0)) > 10],
                key=lambda m: abs(m["priceChange"]),
                reverse=True
            )
            for m in top10_high_movers:
                events.append({
                    "title": m.get("question", "Unknown"),
                    "value": m["priceChange"]  # keep signed value
                })
        if events:
            entry["events"] = events
        series.append(entry)

    # write
    suffix = f"{start_date:%Y-%m-%d}" if start_date == end_date \
        else f"{start_date:%Y-%m-%d}-{end_date:%Y-%m-%d}"
    out_path = Path("data/backfills/scores") / f"scores_{suffix}.json"
    write_scores(series, out_path)


# ───────────────────────── CLI entrypoint ───────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill daily scores")
    ap.add_argument("dates", nargs="+", help="YYYY-MM-DD[,YYYY-MM-DD,...] or start end")
    ap.add_argument("-m", "--markets-file", dest="markets_file",
                    help="Existing markets JSON (else scrape fresh)")
    ns = ap.parse_args()

    # Support for comma-separated list or range
    date_args = ns.dates
    dates_list = []
    try:
        if len(date_args) == 1 and "," in date_args[0]:
            # Comma-separated list
            dates_list = [datetime.strptime(d.strip(), "%Y-%m-%d").replace(tzinfo=ET) for d in date_args[0].split(",")]
        elif len(date_args) == 2:
            # Range
            start_dt = datetime.strptime(date_args[0], "%Y-%m-%d").replace(tzinfo=ET)
            end_dt   = datetime.strptime(date_args[1], "%Y-%m-%d").replace(tzinfo=ET)
            cur = start_dt
            while cur <= end_dt:
                dates_list.append(cur)
                cur += timedelta(days=1)
        elif len(date_args) == 1:
            # Single date
            dates_list = [datetime.strptime(date_args[0], "%Y-%m-%d").replace(tzinfo=ET)]
        else:
            raise ValueError("Invalid date arguments")
    except ValueError as e:
        raise SystemExit(f"❌  Invalid date: {e}")

    def custom_backfill(dates, markets_file=None):
        if markets_file:
            with open(markets_file, encoding="utf-8") as fp:
                markets = json.load(fp)
        else:
            markets = scrape_markets(active=False)
        n_proc = max(1, cpu_count() - 1)
        with Pool(n_proc) as pool:
            results = pool.starmap(process_single_day, [(d, markets) for d in dates])
        series = []
        for d, v, top10 in sorted(results, key=lambda t: t[0]):
            entry = {"time": d, "value": v}
            events = []
            if v > 8:
                top10_high_movers = sorted(
                    [m for m in top10 if abs(m.get("priceChange", 0)) > 10],
                    key=lambda m: abs(m["priceChange"]),
                    reverse=True
                )
                for m in top10_high_movers:
                    events.append({
                        "title": m.get("question", "Unknown"),
                        "value": m["priceChange"]
                    })
            if events:
                entry["events"] = events
            series.append(entry)
        if len(dates) == 1:
            suffix = f"{dates[0]:%Y-%m-%d}"
        else:
            suffix = f"{dates[0]:%Y-%m-%d}-{dates[-1]:%Y-%m-%d}"
        out_path = Path("data/backfills/scores") / f"scores_{suffix}.json"
        write_scores(series, out_path)

    custom_backfill(dates_list, ns.markets_file)
