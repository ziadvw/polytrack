from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests
from zoneinfo import ZoneInfo

from utils import clean_timestamp, get_yes_token_id, get_block_number

ET = ZoneInfo("America/New_York")
API_MARKETS = "https://gamma-api.polymarket.com/markets"
API_PRICES  = "https://clob.polymarket.com/prices-history"
API_OI_GQL  = (
    "https://api.goldsky.com/api/public/"
    "project_cl6mb8i9h0003e201j6li0diw/subgraphs/oi-subgraph/0.0.6/gn"
)


# ───────────────────────── scrape_markets ───────────────────────────────────
def scrape_markets(
    active: bool = True,
    output_path: Optional[str | os.PathLike[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Hit Polymarket REST and return a cleaned 'slim' list.
    """
    limit, offset = 500, 0
    markets: list[dict[str, Any]] = []
    sess = requests.Session()

    print("🔄 Fetching markets…")
    while True:
        params = {"limit": limit, "offset": offset, **({"closed": "false"} if active else {})}
        try:
            res = sess.get(API_MARKETS, params=params, timeout=20)
            res.raise_for_status()
        except Exception as exc:
            print("❌ Fetch error:", exc)
            break

        batch: list[dict[str, Any]] = res.json()
        if not batch:
            break
        markets.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    # --- post-process --------------------------------------------------------
    slim: list[dict[str, Any]] = []
    for m in markets:
        rec: dict[str, Any] = {
            "conditionId": m.get("conditionId"),
            "question":    m.get("question"),
        }

        # timestamps
        for fld in ("createdAt", "closedTime"):
            if cleaned := clean_timestamp(m.get(fld)):
                rec[fld] = cleaned

        # tokenId
        if tok := get_yes_token_id(m.get("clobTokenIds", "")):
            rec["tokenId"] = tok

        # events
        if ev := m.get("events"):
            rec["event_ids"] = [e["id"] for e in ev if e.get("id")]

        if any(rec.values()):
            slim.append(rec)

    if output_path:
        path = Path(output_path)
        if path.is_dir():
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            path = path / f"markets_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(slim, indent=2, ensure_ascii=False))
        print(f"✅ Saved {len(slim)} markets → {path}")

    return slim


# ─────────────────────── filter_markets_by_date ─────────────────────────────
def filter_markets_by_date(
    all_markets_data: List[Dict[str, Any]],
    start_date: datetime,
    end_date: datetime,
    output_path: Optional[str | os.PathLike[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Return markets active at any time within [start_date, end_date).
    """
    if not all_markets_data:
        print("❌ No markets data provided")
        return []

    filtered: list[dict[str, Any]] = []
    for m in all_markets_data:
        # createdAt
        try:
            created = datetime.fromisoformat(m["createdAt"])
        except Exception:
            continue
        if created > end_date:
            continue

        # closedTime (optional)
        closed_str = m.get("closedTime")
        if closed_str:
            try:
                closed = datetime.fromisoformat(closed_str)
                if closed < start_date:
                    continue
            except Exception:
                pass

        filtered.append(m)

    if output_path:
        path = Path(output_path)
        if path.is_dir():
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            path = path / f"filtered_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(filtered, indent=2, ensure_ascii=False))
        print(f"✅ Saved {len(filtered)} filtered markets → {path}")

    return filtered


# ─────────────────────────────── get_ois ────────────────────────────────────
def get_ois(
    markets: Optional[List[Dict[str, Any]]] = None,
    unix_timestamp: Optional[int] = None,
    top_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Return top-N markets by open interest (GraphQL call).
    """
    def fetch_batch(batch_size: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        variables: Dict[str, Any] = {}
        where_clause = ""
        block_clause = ""

        if markets is not None:
            variables["conditionIds"] = condition_ids
            where_clause = "where: {id_in: $conditionIds}"

        if unix_timestamp is not None:
            if (bn := get_block_number(unix_timestamp)) is None:
                return []
            variables["blockNumber"] = bn
            block_clause = "block: {number: $blockNumber},"

        query = f"""
        query GetOI($conditionIds: [String!], $blockNumber: Int) {{
            marketOpenInterests({block_clause}{where_clause}
                orderBy: amount
                orderDirection: desc
                first: {batch_size}
                skip: {skip}) {{
                    id amount
            }}
        }}
        """

        try:
            r = requests.post(API_OI_GQL, json={"query": query, "variables": variables}, timeout=20)
            r.raise_for_status()
            data = r.json()
            # Divide 'amount' by 1_000_000 for each market
            return [
                {"id": m["id"], "amount": float(m["amount"]) / 1_000_000}
                for m in data["data"]["marketOpenInterests"]
            ]
        except Exception as exc:
            print("❌ GraphQL error:", exc)
            return []

    def dedupe_shared_events(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if markets is None:
            return rows
        seen: Set[str] = set()
        out: list[dict[str, Any]] = []
        for r in rows:
            ev = markets_by_id.get(r["id"], {}).get("event_ids", [])
            if not ev or not any(e in seen for e in ev):
                out.append(r)
                seen.update(ev)
        return out

    condition_ids = [m["conditionId"] for m in markets or [] if m.get("conditionId")]
    markets_by_id = {m["conditionId"]: m for m in markets or [] if m.get("conditionId")}

    batch_size = max(top_n or 100, 100)
    result: list[dict[str, Any]] = []
    skip = 0

    while True:
        batch = fetch_batch(batch_size, skip)
        if not batch:
            break
        for r in dedupe_shared_events(batch):
            if all(r["id"] != x["id"] for x in result):
                result.append(r)
                if top_n and len(result) >= top_n:
                    return result[:top_n]
        if len(batch) < batch_size:
            break
        skip += batch_size

    return result[:top_n] if top_n else result


# ──────────────────────── get_day_price_change ──────────────────────────────
def get_day_price_change(
    token_id: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    fidelity: int = 60,
) -> float:
    """
    Return abs % price change for *token_id* over [start_ts, end_ts).
    """
    if start_ts is None:
        today_start = datetime.now(ET).replace(hour=0, minute=0, second=0, microsecond=0)
        start_ts = int(today_start.timestamp())

    params = {"market": token_id, "fidelity": fidelity, "startTs": start_ts}
    if end_ts is not None:
        params["endTs"] = end_ts

    for attempt in range(3):
        try:
            r = requests.get(API_PRICES, params=params, timeout=20)
            r.raise_for_status()
            hist = r.json().get("history", [])
            if len(hist) < 2:
                return 0.0
            start_price = hist[0]["p"]
            end_price   = hist[-2]["p"]          # second-to-last
            return end_price - start_price * 100
        except Exception as exc:
            if attempt < 2:
                time.sleep(1)
            else:
                print(f"❌ Price history failed: {exc}")
                return 0.0

    return 0.0
