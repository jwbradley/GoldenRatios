#!/usr/bin/env python3
"""
Market Ratios Data Collector
Pulls daily gold, silver, Dow, and S&P 500 prices from Yahoo Finance
and calculates GSR, Dow/Gold, and S&P/Gold ratios.

First run: Downloads full history back to 2000 (or specified start date)
Subsequent runs: Appends only new data points since last collection

Setup:
  1. pip install yfinance pandas
  2. Run once to pull historical data: python3 market_ratios_collector.py --backfill
  3. Add to crontab for daily updates: python3 market_ratios_collector.py

Crontab example (run at 5:30 PM CT Monday-Friday, after markets close):
  30 17 * * 1-5 /usr/bin/python3 /home/pi/scripts/market_ratios_collector.py >> /home/pi/logs/market_ratios.log 2>&1

Output:
  - market_ratios_history.json: Full price history with all ratios
  - market_ratios_latest.json: Most recent data point only
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Run: pip install yfinance pandas")
    sys.exit(1)

# Symbols
SYMBOLS = {
    'gold': 'GC=F',       # Gold Futures (CME)
    'silver': 'SI=F',     # Silver Futures (CME)
    'dow': '^DJI',        # Dow Jones Industrial Average
    'sp500': '^GSPC',     # S&P 500 Index
}

DEFAULT_START = '2000-01-01'

# File paths
DATA_DIR = os.environ.get('MARKET_RATIOS_DIR',
           os.environ.get('GSR_DATA_DIR',
           os.path.dirname(os.path.abspath(__file__))))
HISTORY_FILE = os.path.join(DATA_DIR, 'market_ratios_history.json')
LATEST_FILE = os.path.join(DATA_DIR, 'market_ratios_latest.json')
LOG_PREFIX = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def load_history():
    """Load existing history from JSON file."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []


def save_history(data):
    """Save history to JSON file."""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[{LOG_PREFIX}] Saved {len(data)} records to {HISTORY_FILE}")


def save_latest(record):
    """Save the most recent data point for quick access."""
    with open(LATEST_FILE, 'w') as f:
        json.dump(record, f, indent=2)


def fetch_data(start_date, end_date=None):
    """Fetch all market data from Yahoo Finance for the given date range."""
    print(f"[{LOG_PREFIX}] Fetching data from {start_date} to {end_date or 'today'}...")

    end = end_date or (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    # Download all symbols
    frames = {}
    for name, symbol in SYMBOLS.items():
        print(f"[{LOG_PREFIX}]   Downloading {name} ({symbol})...")
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_date, end=end)
        if hist.empty:
            print(f"[{LOG_PREFIX}]   WARNING: No data for {symbol}")
            continue
        frames[name] = hist['Close'].rename(name)

    if not frames:
        print(f"[{LOG_PREFIX}] ERROR: No data returned from any source.")
        return []

    # Combine into single DataFrame aligned on date
    df = pd.DataFrame(frames)

    # Drop rows where gold is missing (needed for all ratios)
    df = df.dropna(subset=['gold'])

    # Drop rows where ALL other columns are NaN
    df = df.dropna(how='all', subset=['silver', 'dow', 'sp500'])

    if df.empty:
        print(f"[{LOG_PREFIX}] No overlapping data available for the requested range.")
        return []

    # Calculate ratios
    records = []
    for date, row in df.iterrows():
        gold = float(row['gold'])
        silver = float(row['silver']) if pd.notna(row['silver']) else None
        dow = float(row['dow']) if pd.notna(row['dow']) else None
        sp500 = float(row['sp500']) if pd.notna(row['sp500']) else None

        record = {
            'date': date.strftime('%Y-%m-%d'),
            'gold': round(gold, 2),
            'silver': round(silver, 4) if silver else None,
            'dow': round(dow, 2) if dow else None,
            'sp500': round(sp500, 2) if sp500 else None,
            'gsr': round(gold / silver, 4) if silver and silver > 0 else None,
            'dow_gold': round(dow / gold, 4) if dow and gold > 0 else None,
            'sp500_gold': round(sp500 / gold, 4) if sp500 and gold > 0 else None,
        }
        records.append(record)

    print(f"[{LOG_PREFIX}] Fetched {len(records)} data points.")
    return records


def backfill(start_date=DEFAULT_START):
    """Pull full historical data from start_date to today."""
    print(f"[{LOG_PREFIX}] BACKFILL: Pulling full history from {start_date}...")
    records = fetch_data(start_date)

    if records:
        save_history(records)
        save_latest(records[-1])
        print(f"[{LOG_PREFIX}] Backfill complete: {len(records)} records")
        print(f"[{LOG_PREFIX}]   First: {records[0]['date']}")
        print(f"[{LOG_PREFIX}]   Last:  {records[-1]['date']}")
        print_record(records[-1])
    else:
        print(f"[{LOG_PREFIX}] ERROR: No data returned.")

    return records


def daily_update():
    """Append new data points since last collection."""
    history = load_history()

    if not history:
        print(f"[{LOG_PREFIX}] No existing history found. Run with --backfill first.")
        sys.exit(1)

    last_date = history[-1]['date']
    start = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    if start > datetime.now().strftime('%Y-%m-%d'):
        print(f"[{LOG_PREFIX}] Already up to date (last record: {last_date}). Nothing to fetch.")
        return

    print(f"[{LOG_PREFIX}] DAILY UPDATE: Fetching from {start} (last record: {last_date})...")
    new_records = fetch_data(start)

    if new_records:
        existing_dates = {r['date'] for r in history}
        new_unique = [r for r in new_records if r['date'] not in existing_dates]

        if new_unique:
            history.extend(new_unique)
            history.sort(key=lambda x: x['date'])
            save_history(history)
            save_latest(history[-1])
            print(f"[{LOG_PREFIX}] Added {len(new_unique)} new records (total: {len(history)})")
            for r in new_unique:
                print_record(r)
        else:
            print(f"[{LOG_PREFIX}] No new unique records to add.")
    else:
        print(f"[{LOG_PREFIX}] No new data available yet.")


def print_record(r):
    """Print a single record in readable format."""
    parts = [f"  {r['date']}:"]
    if r.get('gold'):
        parts.append(f"Gold=${r['gold']:,.2f}")
    if r.get('silver'):
        parts.append(f"Silver=${r['silver']:.2f}")
    if r.get('dow'):
        parts.append(f"Dow={r['dow']:,.2f}")
    if r.get('sp500'):
        parts.append(f"S&P={r['sp500']:,.2f}")
    if r.get('gsr'):
        parts.append(f"GSR={r['gsr']:.1f}")
    if r.get('dow_gold'):
        parts.append(f"Dow/Gold={r['dow_gold']:.2f}")
    if r.get('sp500_gold'):
        parts.append(f"S&P/Gold={r['sp500_gold']:.2f}")
    print(f"[{LOG_PREFIX}] {' | '.join(parts)}")


def export_csv(output_path=None):
    """Export history to CSV file for spreadsheet use."""
    import csv

    history = load_history()
    if not history:
        print("No history file found. Run with --backfill first.")
        return

    if not output_path:
        output_path = os.path.join(DATA_DIR, 'market_ratios_history.csv')

    fieldnames = ['date', 'gold', 'silver', 'dow', 'sp500', 'gsr', 'dow_gold', 'sp500_gold']

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(history)

    print(f"[{LOG_PREFIX}] Exported {len(history)} records to {output_path}")


def show_status():
    """Display current data status."""
    history = load_history()
    if not history:
        print("No history file found. Run with --backfill to initialize.")
        return

    latest = history[-1]
    print(f"History file: {HISTORY_FILE}")
    print(f"Total records: {len(history)}")
    print(f"Date range: {history[0]['date']} to {latest['date']}")
    print(f"\nLatest record ({latest['date']}):")
    print(f"  Gold:       ${latest['gold']:,.2f}" if latest.get('gold') else "  Gold:       N/A")
    print(f"  Silver:     ${latest['silver']:.2f}" if latest.get('silver') else "  Silver:     N/A")
    print(f"  Dow:        {latest['dow']:,.2f}" if latest.get('dow') else "  Dow:        N/A")
    print(f"  S&P 500:    {latest['sp500']:,.2f}" if latest.get('sp500') else "  S&P 500:    N/A")
    print(f"  GSR:        {latest['gsr']:.2f}" if latest.get('gsr') else "  GSR:        N/A")
    print(f"  Dow/Gold:   {latest['dow_gold']:.2f}" if latest.get('dow_gold') else "  Dow/Gold:   N/A")
    print(f"  S&P/Gold:   {latest['sp500_gold']:.4f}" if latest.get('sp500_gold') else "  S&P/Gold:   N/A")

    file_size = os.path.getsize(HISTORY_FILE)
    print(f"\nFile size: {file_size / 1024 / 1024:.1f} MB")

    # Show ratio trends (last 5 trading days)
    if len(history) >= 5:
        print(f"\nLast 5 trading days:")
        print(f"  {'Date':<12} {'Gold':>10} {'Dow/Gold':>10} {'S&P/Gold':>10} {'GSR':>8}")
        print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
        for r in history[-5:]:
            gold_str = f"${r['gold']:,.0f}" if r.get('gold') else "N/A"
            dg_str = f"{r['dow_gold']:.2f}" if r.get('dow_gold') else "N/A"
            sg_str = f"{r['sp500_gold']:.4f}" if r.get('sp500_gold') else "N/A"
            gsr_str = f"{r['gsr']:.1f}" if r.get('gsr') else "N/A"
            print(f"  {r['date']:<12} {gold_str:>10} {dg_str:>10} {sg_str:>10} {gsr_str:>8}")


def show_briefing():
    """Output a concise summary suitable for inclusion in market briefings."""
    history = load_history()
    if not history or len(history) < 2:
        print("Insufficient data for briefing. Run --backfill first.")
        return

    latest = history[-1]
    prev = history[-2]

    print(f"## Market Ratios ({latest['date']})")
    print()

    # Gold/Silver
    if latest.get('gsr') and prev.get('gsr'):
        gsr_chg = latest['gsr'] - prev['gsr']
        direction = "+" if gsr_chg >= 0 else ""
        print(f"- **Gold/Silver Ratio:** {latest['gsr']:.1f} ({direction}{gsr_chg:.2f})")
        print(f"  - Gold: ${latest['gold']:,.2f} | Silver: ${latest['silver']:.2f}")

    # Dow/Gold
    if latest.get('dow_gold') and prev.get('dow_gold'):
        dg_chg = latest['dow_gold'] - prev['dow_gold']
        direction = "+" if dg_chg >= 0 else ""
        print(f"- **Dow/Gold Ratio:** {latest['dow_gold']:.2f} ({direction}{dg_chg:.3f})")
        print(f"  - Dow: {latest['dow']:,.2f} | Gold: ${latest['gold']:,.2f}")

    # S&P/Gold
    if latest.get('sp500_gold') and prev.get('sp500_gold'):
        sg_chg = latest['sp500_gold'] - prev['sp500_gold']
        direction = "+" if sg_chg >= 0 else ""
        print(f"- **S&P 500/Gold Ratio:** {latest['sp500_gold']:.4f} ({direction}{sg_chg:.4f})")
        print(f"  - S&P 500: {latest['sp500']:,.2f} | Gold: ${latest['gold']:,.2f}")

    # Context
    print()
    if len(history) >= 252:
        year_ago = history[-252]
        if year_ago.get('dow_gold') and latest.get('dow_gold'):
            ytd_chg = ((latest['dow_gold'] / year_ago['dow_gold']) - 1) * 100
            print(f"- Dow/Gold 1-year change: {ytd_chg:+.1f}% (from {year_ago['dow_gold']:.2f})")
        if year_ago.get('gsr') and latest.get('gsr'):
            gsr_ytd = ((latest['gsr'] / year_ago['gsr']) - 1) * 100
            print(f"- GSR 1-year change: {gsr_ytd:+.1f}% (from {year_ago['gsr']:.1f})")


def main():
    parser = argparse.ArgumentParser(
        description='Market Ratios Data Collector - Gold, Silver, Dow, S&P 500 with ratio calculations',
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
        """
    )
    parser.add_argument('--backfill', action='store_true',
                        help='Pull full historical data (run once to initialize)')
    parser.add_argument('--start', type=str, default=DEFAULT_START,
                        help=f'Start date for backfill (default: {DEFAULT_START})')
    parser.add_argument('--status', action='store_true',
                        help='Show current data status and exit')
    parser.add_argument('--briefing', action='store_true',
                        help='Output market briefing summary (for inclusion in reports)')
    parser.add_argument('--csv', nargs='?', const='', default=None,
                        help='Export history to CSV (optional: specify output path)')

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


if __name__ == '__main__':
    main()
