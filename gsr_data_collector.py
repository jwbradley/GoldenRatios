#!/usr/bin/env python3
"""
Gold/Silver Ratio (GSR) Data Collector — hybrid source.

Primary path (no API key required):
  Gold  → yfinance GC=F (CME gold futures)
  Silver → yfinance SI=F (CME silver futures)

Optional upgrade when FRED_API_KEY is set:
  Gold  → FRED series GOLDAMGBD228NLBM (LBMA AM fix, USD/oz)
  Silver → still SI=F (FRED silver series availability varies)

Modes:
  --backfill   Full history from --start (default 2000-01-01)
  (default)    Daily append since last history date
  --status     Summary of stored history
  --csv        Export gsr_history.csv
  --briefing   Short markdown snippet for reports

Environment:
  GSR_DATA_DIR   Output directory (default: script directory)
  FRED_API_KEY   Optional FRED key (or ~/.fred_api_key)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    import pandas as pd
    import yfinance as yf
except ImportError:
    print("ERROR: Missing packages.", file=sys.stderr)
    print("Run: pip install pandas yfinance", file=sys.stderr)
    print("Optional: pip install fredapi  (for FRED gold fix)", file=sys.stderr)
    sys.exit(1)

# Optional FRED
try:
    from fredapi import Fred
except ImportError:
    Fred = None  # type: ignore

GOLD_FRED_SERIES = "GOLDAMGBD228NLBM"
GOLD_YF_TICKER = "GC=F"
SILVER_YF_TICKER = "SI=F"
DEFAULT_START = "2000-01-01"

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("GSR_DATA_DIR", str(SCRIPT_DIR)))
HISTORY_FILE = DATA_DIR / "gsr_history.json"
LATEST_FILE = DATA_DIR / "gsr_latest.json"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "gsr_collector.log"


def log(msg: str) -> None:
    """Print timestamped message and append to log file when possible."""
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
    """Write JSON via temp file + rename to avoid truncated files on crash."""
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


def get_fred_client() -> Optional[Any]:
    """Return Fred client if fredapi + key available, else None."""
    if Fred is None:
        return None
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        for candidate in (
            Path.home() / ".fred_api_key",
            SCRIPT_DIR / ".fred_api_key",
        ):
            if candidate.is_file():
                api_key = candidate.read_text(encoding="utf-8").strip()
                break
    if not api_key:
        return None
    try:
        return Fred(api_key=api_key)
    except Exception as e:
        log(f"WARNING: FRED client init failed: {e}")
        return None


def _yf_close(ticker: str, start_date: str, end_date: Optional[str]) -> pd.Series:
    """Download adjusted close series; empty Series on failure."""
    end = end_date or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        hist = yf.Ticker(ticker).history(start=start_date, end=end, auto_adjust=True)
        if hist is None or hist.empty or "Close" not in hist.columns:
            return pd.Series(dtype=float)
        s = hist["Close"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        s.name = ticker
        return s
    except Exception as e:
        log(f"WARNING: yfinance {ticker} failed: {e}")
        return pd.Series(dtype=float)


def fetch_gold_fred(fred: Any, start_date: str, end_date: Optional[str] = None) -> Optional[pd.Series]:
    """LBMA gold AM fix from FRED, or None."""
    try:
        kwargs: dict[str, Any] = {"observation_start": start_date}
        if end_date:
            kwargs["observation_end"] = end_date
        series = fred.get_series(GOLD_FRED_SERIES, **kwargs)
        if series is None or len(series) == 0:
            return None
        s = series.dropna()
        s.index = pd.to_datetime(s.index)
        s.name = "gold"
        return s
    except Exception as e:
        log(f"WARNING: FRED gold fetch failed: {e}")
        return None


def fetch_data(start_date: str, end_date: Optional[str] = None) -> list[dict]:
    """
    Fetch gold + silver and compute GSR for overlapping dates.

    Prefers FRED gold when configured; always uses yfinance for silver.
    Falls back to yfinance gold if FRED is unavailable or empty.
    """
    log(f"Fetching GSR data from {start_date} to {end_date or 'today'}...")

    gold_source = "yfinance"
    gold = None

    fred = get_fred_client()
    if fred is not None:
        gold = fetch_gold_fred(fred, start_date, end_date)
        if gold is not None and len(gold) > 0:
            gold_source = "FRED"
            log(f"  Gold: FRED {GOLD_FRED_SERIES} ({len(gold)} pts)")
        else:
            log("  Gold: FRED empty/unavailable — falling back to yfinance")

    if gold is None or len(gold) == 0:
        gold = _yf_close(GOLD_YF_TICKER, start_date, end_date)
        gold_source = "yfinance"
        log(f"  Gold: yfinance {GOLD_YF_TICKER} ({len(gold)} pts)")

    silver = _yf_close(SILVER_YF_TICKER, start_date, end_date)
    log(f"  Silver: yfinance {SILVER_YF_TICKER} ({len(silver)} pts)")

    if gold.empty or silver.empty:
        log("ERROR: No data downloaded for gold and/or silver.")
        return []

    df = pd.concat([gold.rename("gold"), silver.rename("silver")], axis=1, join="inner")
    df = df.dropna(how="any")

    if df.empty:
        log("ERROR: No overlapping gold/silver dates.")
        return []

    records: list[dict] = []
    for date, row in df.iterrows():
        g = float(row["gold"])
        s = float(row["silver"])
        gsr = round(g / s, 4) if s > 0 else None
        records.append(
            {
                "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                "gold": round(g, 2),
                "silver": round(s, 4),
                "gsr": gsr,
            }
        )

    log(f"Fetched {len(records)} data points (gold source: {gold_source}).")
    return records


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


def backfill(start_date: str = DEFAULT_START) -> list[dict]:
    log(f"BACKFILL: Pulling full history from {start_date}...")
    records = fetch_data(start_date)
    if records:
        save_history(records)
        save_latest(records[-1])
        log(f"Backfill complete: {len(records)} records")
        log(f"  First: {records[0]['date']}  Last: {records[-1]['date']}")
        log(
            f"  Latest GSR: {records[-1].get('gsr')} "
            f"(Gold ${records[-1].get('gold')}, Silver ${records[-1].get('silver')})"
        )
    else:
        log("ERROR: Backfill returned no data.")
    return records


def daily_update() -> None:
    history = load_history()
    if not history:
        log("No history found. Run with --backfill first.")
        sys.exit(1)

    last_date = history[-1]["date"]
    # Always re-fetch a short trailing window so same-day / late prints get corrected
    overlap_start = (datetime.strptime(last_date, "%Y-%m-%d") - timedelta(days=7)).strftime(
        "%Y-%m-%d"
    )
    log(f"DAILY UPDATE: Fetching from {overlap_start} (last record: {last_date}, overlap refresh)...")
    new_records = fetch_data(overlap_start)
    if not new_records:
        log("No new data available yet.")
        return

    by_date = {r["date"]: r for r in history}
    added = 0
    updated = 0
    for r in new_records:
        if r["date"] in by_date:
            if by_date[r["date"]] != r:
                by_date[r["date"]] = r
                updated += 1
        else:
            by_date[r["date"]] = r
            added += 1

    if added or updated:
        history = sorted(by_date.values(), key=lambda x: x["date"])
        save_history(history)
        save_latest(history[-1])
        log(f"Added {added}, updated {updated} (total: {len(history)})")
    else:
        log("No new unique records to add.")


def export_csv(output_path: Optional[str] = None) -> None:
    history = load_history()
    if not history:
        print("No history file found. Run --backfill first.")
        return
    path = Path(output_path) if output_path else DATA_DIR / "gsr_history.csv"
    ensure_data_dir()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "gold", "silver", "gsr"])
        writer.writeheader()
        writer.writerows(history)
    log(f"Exported {len(history)} records to {path}")


def show_status() -> None:
    history = load_history()
    if not history:
        print("No history file found. Run --backfill first.")
        return
    latest = history[-1]
    print(f"History file: {HISTORY_FILE}")
    print(f"Total records: {len(history)}")
    print(f"Date range: {history[0]['date']} to {latest['date']}")
    print(f"Latest: {latest}")
    if HISTORY_FILE.is_file():
        print(f"File size: {HISTORY_FILE.stat().st_size / 1024:.1f} KB")


def show_briefing() -> None:
    history = load_history()
    if not history or len(history) < 2:
        print("Insufficient data for briefing. Run --backfill first.")
        return
    latest, prev = history[-1], history[-2]
    print(f"## Gold/Silver Ratio ({latest['date']})")
    print()
    if latest.get("gsr") is not None and prev.get("gsr") is not None:
        chg = latest["gsr"] - prev["gsr"]
        sign = "+" if chg >= 0 else ""
        print(f"- **GSR:** {latest['gsr']:.1f} ({sign}{chg:.2f})")
        print(f"  - Gold: ${latest['gold']:,.2f} | Silver: ${latest['silver']:.2f}")
    if len(history) >= 252 and history[-252].get("gsr") and latest.get("gsr"):
        yoy = ((latest["gsr"] / history[-252]["gsr"]) - 1) * 100
        print(f"- GSR 1-year change: {yoy:+.1f}% (from {history[-252]['gsr']:.1f})")
    print()
    print("_Educational context only — not investment advice. See DISCLAIMER.md._")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gold/Silver Ratio collector (yfinance + optional FRED gold)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 gsr_data_collector.py --backfill
  python3 gsr_data_collector.py --backfill --start 2016-01-01
  python3 gsr_data_collector.py
  python3 gsr_data_collector.py --status
  python3 gsr_data_collector.py --briefing
  python3 gsr_data_collector.py --csv
        """,
    )
    parser.add_argument("--backfill", action="store_true", help="Full historical backfill")
    parser.add_argument("--start", type=str, default=DEFAULT_START, help="Start date for backfill")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--briefing", action="store_true", help="Markdown briefing snippet")
    parser.add_argument("--csv", nargs="?", const="", default=None, help="Export to CSV")

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
