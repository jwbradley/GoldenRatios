#!/usr/bin/env python3
"""
Gold/Silver Ratio Data Collector
Pulls daily gold and silver prices from FRED API and maintains a local JSON history.

First run: Downloads full history back to 1968 (or specified start date)
Subsequent runs: Appends only new data points since last collection

Setup:
  1. pip install fredapi pandas
  2. Set environment variable: export FRED_API_KEY="your_32_char_key"
     Or create a file: ~/.fred_api_key containing just the key
  3. Run once manually to pull historical data: python3 gsr_data_collector.py --backfill
  4. Add to crontab for daily updates: python3 gsr_data_collector.py

Crontab example (run at 6 PM CT Monday-Friday, after London fix publishes):
  0 18 * * 1-5 /usr/bin/python3 /home/pi/gsr_data_collector.py >> /home/pi/logs/gsr_collector.log 2>&1

Output:
  - gsr_history.json: Full price history with gold, silver, and calculated GSR
  - gsr_latest.json: Most recent data point only (for quick reads)
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    from fredapi import Fred
    import pandas as pd
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Run: pip install fredapi pandas")
    sys.exit(1)

# Configuration
GOLD_SERIES = 'GOLDAMGBD228NLBM'   # Gold Fixing Price 10:30 AM London (USD/Troy Oz)
SILVER_SERIES = 'SLVPRUSD'          # Silver Fixing Price London (USD/Troy Oz)
DEFAULT_START = '1968-04-01'         # FRED earliest available date for both series

# File paths - adjust for your Raspberry Pi
DATA_DIR = os.environ.get('GSR_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(DATA_DIR, 'gsr_history.json')
LATEST_FILE = os.path.join(DATA_DIR, 'gsr_latest.json')
LOG_PREFIX = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_fred_client():
    """Initialize FRED API client from environment or key file."""
    api_key = os.environ.get('FRED_API_KEY')

    if not api_key:
        key_file = os.path.expanduser('~/.fred_api_key')
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                api_key = f.read().strip()

    if not api_key:
        print(f"[{LOG_PREFIX}] ERROR: No FRED API key found.")
        print("Set FRED_API_KEY environment variable or create ~/.fred_api_key")
        sys.exit(1)

    return Fred(api_key=api_key)


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


def fetch_data(fred, start_date, end_date=None):
    """Fetch gold and silver prices from FRED for the given date range."""
    print(f"[{LOG_PREFIX}] Fetching data from {start_date} to {end_date or 'today'}...")

    kwargs = {'observation_start': start_date}
    if end_date:
        kwargs['observation_end'] = end_date

    gold = fred.get_series(GOLD_SERIES, **kwargs)
    silver = fred.get_series(SILVER_SERIES, **kwargs)

    # Align on common dates and drop NaN
    df = pd.DataFrame({'gold': gold, 'silver': silver}).dropna()

    if df.empty:
        print(f"[{LOG_PREFIX}] No new data available for the requested range.")
        return []

    # Calculate GSR and build records
    records = []
    for date, row in df.iterrows():
        gsr = round(row['gold'] / row['silver'], 4) if row['silver'] > 0 else None
        records.append({
            'date': date.strftime('%Y-%m-%d'),
            'gold': round(float(row['gold']), 2),
            'silver': round(float(row['silver']), 4),
            'gsr': gsr
        })

    print(f"[{LOG_PREFIX}] Fetched {len(records)} data points.")
    return records


def backfill(fred, start_date=DEFAULT_START):
    """Pull full historical data from start_date to today."""
    print(f"[{LOG_PREFIX}] BACKFILL: Pulling full history from {start_date}...")
    records = fetch_data(fred, start_date)

    if records:
        save_history(records)
        save_latest(records[-1])
        print(f"[{LOG_PREFIX}] Backfill complete: {len(records)} records")
        print(f"[{LOG_PREFIX}]   First: {records[0]['date']} - Gold: ${records[0]['gold']}, Silver: ${records[0]['silver']}, GSR: {records[0]['gsr']}")
        print(f"[{LOG_PREFIX}]   Last:  {records[-1]['date']} - Gold: ${records[-1]['gold']}, Silver: ${records[-1]['silver']}, GSR: {records[-1]['gsr']}")
    else:
        print(f"[{LOG_PREFIX}] ERROR: No data returned from FRED.")

    return records


def daily_update(fred):
    """Append new data points since last collection."""
    history = load_history()

    if not history:
        print(f"[{LOG_PREFIX}] No existing history found. Run with --backfill first.")
        sys.exit(1)

    last_date = history[-1]['date']
    # Start from the day after last recorded date
    start = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Don't fetch if last date is today or in the future
    if start > datetime.now().strftime('%Y-%m-%d'):
        print(f"[{LOG_PREFIX}] Already up to date (last record: {last_date}). Nothing to fetch.")
        return

    print(f"[{LOG_PREFIX}] DAILY UPDATE: Fetching from {start} (last record: {last_date})...")
    new_records = fetch_data(fred, start)

    if new_records:
        # Deduplicate - ensure no date overlap
        existing_dates = {r['date'] for r in history}
        new_unique = [r for r in new_records if r['date'] not in existing_dates]

        if new_unique:
            history.extend(new_unique)
            # Sort by date just in case
            history.sort(key=lambda x: x['date'])
            save_history(history)
            save_latest(history[-1])
            print(f"[{LOG_PREFIX}] Added {len(new_unique)} new records (total: {len(history)})")
            for r in new_unique:
                print(f"[{LOG_PREFIX}]   {r['date']} - Gold: ${r['gold']}, Silver: ${r['silver']}, GSR: {r['gsr']}")
        else:
            print(f"[{LOG_PREFIX}] No new unique records to add.")
    else:
        print(f"[{LOG_PREFIX}] No new data available from FRED yet.")


def export_csv(output_path=None):
    """Export history to CSV file for spreadsheet use."""
    import csv

    history = load_history()
    if not history:
        print("No history file found. Run with --backfill first.")
        return

    if not output_path:
        output_path = os.path.join(DATA_DIR, 'gsr_history.csv')

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'gold', 'silver', 'gsr'])
        writer.writeheader()
        writer.writerows(history)

    print(f"[{LOG_PREFIX}] Exported {len(history)} records to {output_path}")


def show_status():
    """Display current data status."""
    history = load_history()
    if not history:
        print("No history file found. Run with --backfill to initialize.")
        return

    print(f"History file: {HISTORY_FILE}")
    print(f"Total records: {len(history)}")
    print(f"Date range: {history[0]['date']} to {history[-1]['date']}")
    print(f"\nLatest record:")
    print(f"  Date:   {history[-1]['date']}")
    print(f"  Gold:   ${history[-1]['gold']}")
    print(f"  Silver: ${history[-1]['silver']}")
    print(f"  GSR:    {history[-1]['gsr']}")

    # Check for gaps
    file_size = os.path.getsize(HISTORY_FILE)
    print(f"\nFile size: {file_size / 1024 / 1024:.1f} MB")


def main():
    parser = argparse.ArgumentParser(
        description='Gold/Silver Ratio Data Collector - Pulls prices from FRED API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  First run (full history):   python3 gsr_data_collector.py --backfill
  Daily cron update:          python3 gsr_data_collector.py
  Custom start date:          python3 gsr_data_collector.py --backfill --start 2000-01-01
  Check status:               python3 gsr_data_collector.py --status
  Export to CSV:              python3 gsr_data_collector.py --csv
  Export to specific path:    python3 gsr_data_collector.py --csv /path/to/output.csv
  Last 10 years only:         python3 gsr_data_collector.py --backfill --start 2016-01-01
        """
    )
    parser.add_argument('--backfill', action='store_true',
                        help='Pull full historical data (run once to initialize)')
    parser.add_argument('--start', type=str, default=DEFAULT_START,
                        help=f'Start date for backfill (default: {DEFAULT_START})')
    parser.add_argument('--status', action='store_true',
                        help='Show current data status and exit')
    parser.add_argument('--csv', nargs='?', const='', default=None,
                        help='Export history to CSV (optional: specify output path)')

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.csv is not None:
        export_csv(args.csv if args.csv else None)
        return

    fred = get_fred_client()

    if args.backfill:
        backfill(fred, args.start)
    else:
        daily_update(fred)


if __name__ == '__main__':
    main()
