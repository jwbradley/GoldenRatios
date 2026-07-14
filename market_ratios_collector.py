#!/usr/bin/env python3
"""
Market Ratios Data Collector

Pulls daily gold, silver, Dow, and S&P 500 prices (Yahoo Finance / yfinance)
and calculates GSR, Dow/Gold, and S&P/Gold ratios.

First run:  python3 market_ratios_collector.py --backfill
Daily:      python3 market_ratios_collector.py
Briefing:   python3 market_ratios_collector.py --briefing

Environment:
  MARKET_RATIOS_DIR or GSR_DATA_DIR  — output directory (default: script dir)

Crontab example (after US equity close, weekdays):
  30 17 * * 1-5 /path/to/.venv/bin/python /path/to/market_ratios_collector.py

Educational / informational use only — see DISCLAIMER.md.

Includes holiday-safe handling when some symbols have no row for a session
(e.g. prior day was a scheduled market holiday).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    import pandas as pd
    import yfinance as yf
except ImportError:
    print("ERROR: Required packages not installed.", file=sys.stderr)
    print("Run: pip install yfinance pandas", file=sys.stderr)
    sys.exit(1)

SYMBOLS = {
    "gold": "GC=F",
    "silver": "SI=F",
    "dow": "^DJI",
    "sp500": "^GSPC",
}

DEFAULT_START = "2000-01-01"
MAX_RETRIES = 3
RETRY_SLEEP_SEC = 2.0

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(
    os.environ.get(
        "MARKET_RATIOS_DIR",
        os.environ.get("GSR_DATA_DIR", str(SCRIPT_DIR)),
    )
)
HISTORY_FILE = DATA_DIR / "market_ratios_history.json"
LATEST_FILE = DATA_DIR / "market_ratios_latest.json"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "market_ratios.log"


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, data: Any) -> None:
    ensure_data_dir()
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_history() -> list[dict]:
    if HISTORY_FILE.is_file():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(data: list[dict]) -> None:
    atomic_write_json(HISTORY_FILE, data)
    log(f"Saved {len(data)} records to {HISTORY_FILE}")


def save_latest(record: dict) -> None:
    atomic_write_json(LATEST_FILE, record)


def _download_close(symbol: str, start_date: str, end: str) -> pd.Series:
    """Download close with simple retries; empty Series on failure."""
    last_err: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            hist = yf.Ticker(symbol).history(start=start_date, end=end, auto_adjust=True)
            if hist is None or hist.empty or "Close" not in hist.columns:
                raise ValueError(f"empty history for {symbol}")
            s = hist["Close"].copy()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            s.name = symbol
            return s
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_SLEEP_SEC * attempt)
    log(f"  WARNING: No data for {symbol} after {MAX_RETRIES} tries ({last_err})")
    return pd.Series(dtype=float)


def fetch_data(start_date: str, end_date: Optional[str] = None) -> list[dict]:
    """Fetch all market data and compute ratios for the date range."""
    log(f"Fetching data from {start_date} to {end_date or 'today'}...")
    end = end_date or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    frames: dict[str, pd.Series] = {}
    for name, symbol in SYMBOLS.items():
        log(f"  Downloading {name} ({symbol})...")
        series = _download_close(symbol, start_date, end)
        if not series.empty:
            frames[name] = series.rename(name)

    if "gold" not in frames:
        log("ERROR: No gold data — cannot compute ratios.")
        return []

    df = pd.DataFrame(frames)
    df = df.dropna(subset=["gold"])

    # Holiday / partial-session safe: only drop rows where every non-gold field is NaN,
    # and only among columns that actually exist (avoids KeyError when a symbol is missing).
    other_cols = [c for c in ("silver", "dow", "sp500") if c in df.columns]
    if other_cols:
        df = df.dropna(how="all", subset=other_cols)

    if df.empty:
        log("No overlapping data available for the requested range.")
        return []

    records: list[dict] = []
    for date, row in df.iterrows():
        gold = float(row["gold"])
        silver = (
            float(row["silver"])
            if "silver" in row.index and pd.notna(row.get("silver"))
            else None
        )
        dow = float(row["dow"]) if "dow" in row.index and pd.notna(row.get("dow")) else None
        sp500 = (
            float(row["sp500"])
            if "sp500" in row.index and pd.notna(row.get("sp500"))
            else None
        )

        records.append(
            {
                "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                "gold": round(gold, 2),
                "silver": round(silver, 4) if silver is not None else None,
                "dow": round(dow, 2) if dow is not None else None,
                "sp500": round(sp500, 2) if sp500 is not None else None,
                "gsr": round(gold / silver, 4) if silver and silver > 0 else None,
                "dow_gold": round(dow / gold, 4) if dow and gold > 0 else None,
                "sp500_gold": round(sp500 / gold, 4) if sp500 and gold > 0 else None,
            }
        )

    partial = sum(1 for r in records if r.get("dow") is None or r.get("sp500") is None)
    if partial:
        log(
            f"WARNING: {partial}/{len(records)} rows missing Dow and/or S&P "
            "(ratios null where missing)."
        )

    log(f"Fetched {len(records)} data points.")
    return records


def backfill(start_date: str = DEFAULT_START) -> list[dict]:
    log(f"BACKFILL: Pulling full history from {start_date}...")
    records = fetch_data(start_date)
    if records:
        save_history(records)
        save_latest(records[-1])
        log(f"Backfill complete: {len(records)} records")
        log(f"  First: {records[0]['date']}")
        log(f"  Last:  {records[-1]['date']}")
        print_record(records[-1])
    else:
        log("ERROR: No data returned.")
    return records


def daily_update() -> None:
    history = load_history()
    if not history:
        log("No existing history found. Run with --backfill first.")
        sys.exit(1)

    last_date = history[-1]["date"]
    latest = history[-1]
    incomplete = any(
        latest.get(k) is None
        for k in ("silver", "dow", "sp500", "gsr", "dow_gold", "sp500_gold")
    )

    # Always re-fetch a trailing window so late index prints and nulls can be filled,
    # even when the latest date is already "today".
    overlap_start = (datetime.strptime(last_date, "%Y-%m-%d") - timedelta(days=10)).strftime(
        "%Y-%m-%d"
    )
    reason = "incomplete latest row" if incomplete else "overlap refresh"
    log(f"DAILY UPDATE: Fetching from {overlap_start} (last record: {last_date}, {reason})...")
    new_records = fetch_data(overlap_start)

    if not new_records:
        log("No new data available yet.")
        return

    by_date = {r["date"]: r for r in history}
    added = 0
    updated = 0
    for r in new_records:
        prev = by_date.get(r["date"])
        if prev is None:
            by_date[r["date"]] = r
            added += 1
        else:
            # Prefer non-null fields when refreshing an existing day
            merged = dict(prev)
            for k, v in r.items():
                if v is not None:
                    merged[k] = v
            g, s, d, sp = (
                merged.get("gold"),
                merged.get("silver"),
                merged.get("dow"),
                merged.get("sp500"),
            )
            if g and s and s > 0:
                merged["gsr"] = round(g / s, 4)
            if g and d and g > 0:
                merged["dow_gold"] = round(d / g, 4)
            if g and sp and g > 0:
                merged["sp500_gold"] = round(sp / g, 4)
            if merged != prev:
                by_date[r["date"]] = merged
                updated += 1

    if added or updated:
        history = sorted(by_date.values(), key=lambda x: x["date"])
        save_history(history)
        save_latest(history[-1])
        log(f"Added {added}, updated {updated} (total: {len(history)})")
        if history:
            print_record(history[-1])
    else:
        log("No new unique records to add.")


def print_record(r: dict) -> None:
    parts = [f"  {r['date']}:"]
    if r.get("gold") is not None:
        parts.append(f"Gold=${r['gold']:,.2f}")
    if r.get("silver") is not None:
        parts.append(f"Silver=${r['silver']:.2f}")
    if r.get("dow") is not None:
        parts.append(f"Dow={r['dow']:,.2f}")
    if r.get("sp500") is not None:
        parts.append(f"S&P={r['sp500']:,.2f}")
    if r.get("gsr") is not None:
        parts.append(f"GSR={r['gsr']:.1f}")
    if r.get("dow_gold") is not None:
        parts.append(f"Dow/Gold={r['dow_gold']:.2f}")
    if r.get("sp500_gold") is not None:
        parts.append(f"S&P/Gold={r['sp500_gold']:.2f}")
    log(" | ".join(parts))


def export_csv(output_path: Optional[str] = None) -> None:
    history = load_history()
    if not history:
        print("No history file found. Run with --backfill first.")
        return

    path = Path(output_path) if output_path else DATA_DIR / "market_ratios_history.csv"
    ensure_data_dir()
    fieldnames = ["date", "gold", "silver", "dow", "sp500", "gsr", "dow_gold", "sp500_gold"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(history)
    log(f"Exported {len(history)} records to {path}")


def show_status() -> None:
    history = load_history()
    if not history:
        print("No history file found. Run with --backfill to initialize.")
        return

    latest = history[-1]
    print(f"History file: {HISTORY_FILE}")
    print(f"Total records: {len(history)}")
    print(f"Date range: {history[0]['date']} to {latest['date']}")
    print(f"\nLatest record ({latest['date']}):")
    print(f"  Gold:       ${latest['gold']:,.2f}" if latest.get("gold") is not None else "  Gold:       N/A")
    print(f"  Silver:     ${latest['silver']:.2f}" if latest.get("silver") is not None else "  Silver:     N/A")
    print(f"  Dow:        {latest['dow']:,.2f}" if latest.get("dow") is not None else "  Dow:        N/A")
    print(f"  S&P 500:    {latest['sp500']:,.2f}" if latest.get("sp500") is not None else "  S&P 500:    N/A")
    print(f"  GSR:        {latest['gsr']:.2f}" if latest.get("gsr") is not None else "  GSR:        N/A")
    print(f"  Dow/Gold:   {latest['dow_gold']:.2f}" if latest.get("dow_gold") is not None else "  Dow/Gold:   N/A")
    print(f"  S&P/Gold:   {latest['sp500_gold']:.4f}" if latest.get("sp500_gold") is not None else "  S&P/Gold:   N/A")

    if HISTORY_FILE.is_file():
        print(f"\nFile size: {HISTORY_FILE.stat().st_size / 1024 / 1024:.1f} MB")

    if len(history) >= 5:
        print("\nLast 5 trading days:")
        print(f"  {'Date':<12} {'Gold':>10} {'Dow/Gold':>10} {'S&P/Gold':>10} {'GSR':>8}")
        print(f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8}")
        for r in history[-5:]:
            gold_str = f"${r['gold']:,.0f}" if r.get("gold") is not None else "N/A"
            dg_str = f"{r['dow_gold']:.2f}" if r.get("dow_gold") is not None else "N/A"
            sg_str = f"{r['sp500_gold']:.4f}" if r.get("sp500_gold") is not None else "N/A"
            gsr_str = f"{r['gsr']:.1f}" if r.get("gsr") is not None else "N/A"
            print(f"  {r['date']:<12} {gold_str:>10} {dg_str:>10} {sg_str:>10} {gsr_str:>8}")


def show_briefing() -> None:
    history = load_history()
    if not history or len(history) < 2:
        print("Insufficient data for briefing. Run --backfill first.")
        return

    latest = history[-1]
    prev = history[-2]

    print(f"## Market Ratios ({latest['date']})")
    print()

    if latest.get("gsr") is not None and prev.get("gsr") is not None:
        gsr_chg = latest["gsr"] - prev["gsr"]
        direction = "+" if gsr_chg >= 0 else ""
        print(f"- **Gold/Silver Ratio:** {latest['gsr']:.1f} ({direction}{gsr_chg:.2f})")
        if latest.get("gold") is not None and latest.get("silver") is not None:
            print(f"  - Gold: ${latest['gold']:,.2f} | Silver: ${latest['silver']:.2f}")

    if latest.get("dow_gold") is not None and prev.get("dow_gold") is not None:
        dg_chg = latest["dow_gold"] - prev["dow_gold"]
        direction = "+" if dg_chg >= 0 else ""
        print(f"- **Dow/Gold Ratio:** {latest['dow_gold']:.2f} ({direction}{dg_chg:.3f})")
        if latest.get("dow") is not None and latest.get("gold") is not None:
            print(f"  - Dow: {latest['dow']:,.2f} | Gold: ${latest['gold']:,.2f}")
    elif latest.get("dow_gold") is None:
        print("- **Dow/Gold Ratio:** N/A (index data missing for this date)")

    if latest.get("sp500_gold") is not None and prev.get("sp500_gold") is not None:
        sg_chg = latest["sp500_gold"] - prev["sp500_gold"]
        direction = "+" if sg_chg >= 0 else ""
        print(f"- **S&P 500/Gold Ratio:** {latest['sp500_gold']:.4f} ({direction}{sg_chg:.4f})")
        if latest.get("sp500") is not None and latest.get("gold") is not None:
            print(f"  - S&P 500: {latest['sp500']:,.2f} | Gold: ${latest['gold']:,.2f}")
    elif latest.get("sp500_gold") is None:
        print("- **S&P 500/Gold Ratio:** N/A (index data missing for this date)")

    print()
    if len(history) >= 252:
        year_ago = history[-252]
        if year_ago.get("dow_gold") and latest.get("dow_gold"):
            ytd_chg = ((latest["dow_gold"] / year_ago["dow_gold"]) - 1) * 100
            print(f"- Dow/Gold 1-year change: {ytd_chg:+.1f}% (from {year_ago['dow_gold']:.2f})")
        if year_ago.get("gsr") and latest.get("gsr"):
            gsr_ytd = ((latest["gsr"] / year_ago["gsr"]) - 1) * 100
            print(f"- GSR 1-year change: {gsr_ytd:+.1f}% (from {year_ago['gsr']:.1f})")

    print()
    print("_Educational context only — not investment advice. See DISCLAIMER.md._")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Market Ratios Data Collector - Gold, Silver, Dow, S&P 500 with ratio calculations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Initial backfill:      python3 market_ratios_collector.py --backfill
  From specific year:    python3 market_ratios_collector.py --backfill --start 2010-01-01
  Daily cron update:     python3 market_ratios_collector.py
  Check status:          python3 market_ratios_collector.py --status
  Briefing output:       python3 market_ratios_collector.py --briefing
  Export to CSV:         python3 market_ratios_collector.py --csv
  Export to path:        python3 market_ratios_collector.py --csv /path/to/output.csv
        """,
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Pull full historical data (run once to initialize)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=DEFAULT_START,
        help=f"Start date for backfill (default: {DEFAULT_START})",
    )
    parser.add_argument("--status", action="store_true", help="Show current data status and exit")
    parser.add_argument(
        "--briefing",
        action="store_true",
        help="Output market briefing summary (for inclusion in reports)",
    )
    parser.add_argument(
        "--csv",
        nargs="?",
        const="",
        default=None,
        help="Export history to CSV (optional: specify output path)",
    )

    args = parser.parse_args()

    if args.status:
        show_status()
        return
    if args.briefing:
        show_briefing()
        return
    if args.csv is not None:
        export_csv(args.csv if args.csv else None)
        return
    if args.backfill:
        backfill(args.start)
    else:
        daily_update()


if __name__ == "__main__":
    main()
