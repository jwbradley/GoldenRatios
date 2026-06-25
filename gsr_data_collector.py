#!/usr/bin/env python3
"""
Gold/Silver Ratio Data Collector (Hybrid Version)
- Gold: FRED (London AM Fix) with yfinance fallback
- Silver: yfinance (SI=F)
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Try to import required packages
try:
    import pandas as pd
    import yfinance as yf
    from fredapi import Fred
except ImportError as e:
    print("ERROR: Missing packages.")
    print("Run: python3 -m pip install fredapi pandas yfinance --break-system-packages")
    sys.exit(1)

# Configuration
GOLD_SERIES = 'GOLDAMGBD228NLBM'   # FRED Gold AM London Fix
GOLD_FALLBACK_TICKER = 'GC=F'      # Gold Futures
SILVER_TICKER = 'SI=F'             # Silver Futures

DEFAULT_START = '2000-01-01' # Futures data start date

# File paths
DATA_DIR = os.environ.get('GSR_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(DATA_DIR, 'gsr_history.json')
LATEST_FILE = os.path.join(DATA_DIR, 'gsr_latest.json')
LOG_PREFIX = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_fred_client():
    """Initialize FRED client if key is available."""
    api_key = os.environ.get('FRED_API_KEY')
    if not api_key:
        key_file = os.path.expanduser('~/.fred_api_key')
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                api_key = f.read().strip()
    if api_key:
        return Fred(api_key=api_key)
    return None


def fetch_gold_fred(fred, start_date, end_date=None):
    """Try to fetch gold from FRED."""
    if not fred:
        return None
    try:
        kwargs = {'observation_start': start_date}
        if end_date:
            kwargs['observation_end'] = end_date
        return fred.get_series(GOLD_SERIES, **kwargs)
    except Exception:
        return None


def fetch_data(start_date, end_date=None):
    """Clean yfinance fetch using concat (most reliable)."""
    print(f"[{LOG_PREFIX}] Fetching data from {start_date} to {end_date or 'today'} using yfinance...")

    gold_df = yf.download(GOLD_FALLBACK_TICKER, start=start_date, end=end_date, progress=False, auto_adjust=True)
    silver_df = yf.download(SILVER_TICKER, start=start_date, end=end_date, progress=False, auto_adjust=True)

    print(f"[{LOG_PREFIX}] Gold rows: {len(gold_df)}, Silver rows: {len(silver_df)}")

    if gold_df.empty or silver_df.empty:
        print(f"[{LOG_PREFIX}] No data downloaded.")
        return []

    # Most reliable way to combine
    df = pd.concat(
        [gold_df['Close'], silver_df['Close']],
        axis=1,
        join='inner'
    )
    df.columns = ['gold', 'silver']
    df = df.dropna(how='any')

    if df.empty:
        print(f"[{LOG_PREFIX}] No valid overlapping data.")
        return []

    records = []
    for date, row in df.iterrows():
        gsr = round(float(row['gold']) / float(row['silver']), 4) if float(row['silver']) > 0 else None
        records.append({
            'date': date.strftime('%Y-%m-%d'),
            'gold': round(float(row['gold']), 2),
            'silver': round(float(row['silver']), 4),
            'gsr': gsr
        })

    print(f"[{LOG_PREFIX}] Fetched {len(records)} data points.")
    return records

# === The rest of your original functions (load/save/status etc.) remain almost identical ===

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []


def save_history(data):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[{LOG_PREFIX}] Saved {len(data)} records to {HISTORY_FILE}")


def save_latest(record):
    with open(LATEST_FILE, 'w') as f:
        json.dump(record, f, indent=2)


def backfill(start_date=DEFAULT_START):
    print(f"[{LOG_PREFIX}] BACKFILL: Pulling full history from {start_date}...")
    records = fetch_data(start_date)
    if records:
        save_history(records)
        save_latest(records[-1])
        print(f"[{LOG_PREFIX}] Backfill complete: {len(records)} records")
    return records


def daily_update():
    history = load_history()
    if not history:
        print(f"[{LOG_PREFIX}] No history found. Run with --backfill first.")
        sys.exit(1)

    last_date = history[-1]['date']
    start = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    if start > datetime.now().strftime('%Y-%m-%d'):
        print(f"[{LOG_PREFIX}] Already up to date.")
        return

    new_records = fetch_data(start)
    if new_records:
        existing_dates = {r['date'] for r in history}
        new_unique = [r for r in new_records if r['date'] not in existing_dates]
        if new_unique:
            history.extend(new_unique)
            history.sort(key=lambda x: x['date'])
            save_history(history)
            save_latest(history[-1])
            print(f"[{LOG_PREFIX}] Added {len(new_unique)} new records.")


def export_csv(output_path=None):
    import csv
    history = load_history()
    if not history:
        print("No history file found.")
        return
    if not output_path:
        output_path = os.path.join(DATA_DIR, 'gsr_history.csv')
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'gold', 'silver', 'gsr'])
        writer.writeheader()
        writer.writerows(history)
    print(f"[{LOG_PREFIX}] Exported to {output_path}")


def show_status():
    history = load_history()
    if not history:
        print("No history file found.")
        return
    print(f"Total records: {len(history)}")
    print(f"Date range: {history[0]['date']} to {history[-1]['date']}")
    print(f"Latest: {history[-1]}")


def main():
    parser = argparse.ArgumentParser(description='Gold/Silver Ratio Data Collector (Hybrid)')
    parser.add_argument('--backfill', action='store_true', help='Full historical backfill')
    parser.add_argument('--start', type=str, default=DEFAULT_START, help='Start date for backfill')
    parser.add_argument('--status', action='store_true', help='Show status')
    parser.add_argument('--csv', nargs='?', const='', default=None, help='Export to CSV')

    args = parser.parse_args()

    if args.status:
        show_status()
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
