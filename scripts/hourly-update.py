"""
Hourly task:
• read today's top-10 snapshot
• recompute their average abs price change since 00:00 ET (fidelity 60 min)
• write / overwrite today's value in data/daily_scores.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from scraper import scrape_markets, get_ois, get_day_price_change

ET = ZoneInfo("America/New_York")
TOP10_DIR   = Path("data/top10")
SCORES_FILE = Path("data/daily_scores.json")

def main() -> None:
    now_et   = datetime.now(ET)
    day_str  = now_et.strftime("%Y-%m-%d")
    day_start= now_et.replace(hour=0, minute=0, second=0, microsecond=0)
    today_ts = int(day_start.timestamp())
    now_ts   = int(datetime.now(timezone.utc).timestamp())

    snapshot_file = TOP10_DIR / f"{day_str}.json"
    if not snapshot_file.exists():
        print(f"⚠️  No top-10 snapshot yet for {day_str}, creating it now...")
        # --- replicate daily_top10.py logic ---
        markets = scrape_markets(active=True)
        top_oi  = get_ois(markets, unix_timestamp=today_ts, top_n=10)
        markets_by_id = {m["conditionId"]: m for m in markets}
        snapshot = []
        for m in top_oi:
            cond = m["id"]
            src  = markets_by_id.get(cond, {})
            snapshot.append({
                "conditionId": cond,
                "tokenId":    src.get("tokenId"),
                "question":   src.get("question"),
                "openInterest": m["amount"],
            })
        TOP10_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_file.write_text(json.dumps(snapshot, indent=2))
        print(f"✅ Created top-10 → {snapshot_file}")

    top10 = json.loads(snapshot_file.read_text())
    if not top10:
        print(f"⚠️  Snapshot empty for {day_str}")
        return

    total_abs = 0.0
    updated_top10 = []
    for i, m in enumerate(top10, 1):
        token = m.get("tokenId")
        if not token:
            print(f"  • #{i} missing tokenId")
            updated_top10.append(m)
            continue
        change = get_day_price_change(token, today_ts, now_ts, fidelity=60)
        print(f"    today_ts={today_ts}, now_ts={now_ts}")
        print(f"  • #{i} {token}: {change:.2f}%")
        m["priceChange"] = round(change, 3)  # signed value
        updated_top10.append(m)

        total_abs += abs(change)

    # Write updated top10 with priceChange back to the snapshot file
    snapshot_file.write_text(json.dumps(updated_top10, indent=2))

    avg = round(total_abs / len(updated_top10), 3)
    print(f"💹 Avg change so far: {avg}%")

    events = []
    if avg > 8:
        # get top 10 markets with abs(priceChange) > 10%, ranked by abs(priceChange)
        top10_high_movers = sorted(
            [m for m in updated_top10[:10] if abs(m.get("priceChange", 0)) > 10],
            key=lambda m: abs(m["priceChange"]),
            reverse=True
        )
        for m in top10_high_movers:
            events.append({
                "title": m.get("question", "Unknown"),
                "value": m["priceChange"]  # keep signed value
            })
        if events:
            print(f"🚀 Highlight events:")
            for e in events:
                print(f"   → {e['title']} ({e['value']}%)")

    series = []
    if SCORES_FILE.exists():
        series = json.loads(SCORES_FILE.read_text())

    # edit today’s row in place, or append if missing
    today_entry = {"time": day_str, "value": avg}
    if events:
        today_entry["events"] = events

    if series and series[-1]["time"] == day_str:
        series[-1] = today_entry
    else:
        series.append(today_entry)

    SCORES_FILE.write_text(json.dumps(series, indent=2))
    print(f"✅ Wrote {avg}% to {SCORES_FILE}")

if __name__ == "__main__":
    main()
