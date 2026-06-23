#!/usr/bin/env python3
"""
Update Gold/Silver Ratio chart from collected JSON data.

Reads gsr_history.json (produced by gsr_data_collector.py) and generates
a PNG chart with gold price, silver price, and GSR overlay.

Usage:
  python3 update_gsr_chart.py                  # Default: last 10 years
  python3 update_gsr_chart.py --years 5        # Last 5 years
  python3 update_gsr_chart.py --years 25       # Full history from 2000
  python3 update_gsr_chart.py --all            # Everything in the JSON file

Output:
  GSR_chart.png (in same directory as script, or GSR_DATA_DIR)

Requires: matplotlib, pandas
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import pandas as pd
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Run: pip install matplotlib pandas")
    sys.exit(1)

DATA_DIR = os.environ.get('GSR_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(DATA_DIR, 'gsr_history.json')
OUTPUT_FILE = os.path.join(DATA_DIR, 'GSR_chart.png')


def load_data(years=10, use_all=False):
    """Load price history from JSON and filter by date range."""
    if not os.path.exists(HISTORY_FILE):
        print(f"ERROR: {HISTORY_FILE} not found.")
        print("Run gsr_data_collector.py --backfill first.")
        sys.exit(1)

    with open(HISTORY_FILE, 'r') as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)

    if not use_all:
        cutoff = datetime.now() - timedelta(days=365 * years)
        df = df[df.index >= cutoff]

    print(f"Loaded {len(df)} records ({df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')})")
    return df


def generate_chart(df, output_file=OUTPUT_FILE):
    """Generate the GSR chart with dual-axis overlay."""
    fig, ax1 = plt.subplots(figsize=(14, 8))

    # Gold on left axis
    color_gold = '#B8860B'
    ax1.plot(df.index, df['gold'], color=color_gold, linewidth=1.5, label='Gold ($/oz)', alpha=0.9)
    ax1.set_xlabel('Date', fontsize=11)
    ax1.set_ylabel('Gold Price ($/oz)', fontsize=11, color=color_gold)
    ax1.tick_params(axis='y', labelcolor=color_gold)
    ax1.grid(True, alpha=0.2)

    # Silver on secondary right axis
    ax2 = ax1.twinx()
    color_silver = '#708090'
    ax2.plot(df.index, df['silver'], color=color_silver, linewidth=1.5, label='Silver ($/oz)', alpha=0.9)
    ax2.set_ylabel('Silver Price ($/oz)', fontsize=11, color=color_silver)
    ax2.tick_params(axis='y', labelcolor=color_silver)

    # GSR on third axis (offset right)
    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 65))
    color_gsr = '#1E3A8A'
    ax3.plot(df.index, df['gsr'], color=color_gsr, linewidth=1.8, label='Gold/Silver Ratio', alpha=0.8)
    ax3.set_ylabel('Gold/Silver Ratio (GSR)', fontsize=11, color=color_gsr)
    ax3.tick_params(axis='y', labelcolor=color_gsr)

    # GSR historical average line
    avg_gsr = df['gsr'].mean()
    ax3.axhline(y=avg_gsr, color=color_gsr, linestyle='--', alpha=0.4, linewidth=1)
    ax3.text(df.index[int(len(df)*0.02)], avg_gsr + 1, f'Avg GSR: {avg_gsr:.1f}',
             color=color_gsr, fontsize=8, alpha=0.7)

    # X-axis formatting
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    if len(df) > 365 * 5:
        ax1.xaxis.set_major_locator(mdates.YearLocator())
    else:
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Title
    date_range = f"{df.index[0].strftime('%b %Y')} - {df.index[-1].strftime('%b %d, %Y')}"
    plt.title(f'Gold vs Silver with Gold/Silver Ratio Overlay\n{date_range}',
              fontsize=13, pad=20)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    lines3, labels3 = ax3.get_legend_handles_labels()
    ax1.legend(lines1 + lines2 + lines3, labels1 + labels2 + labels3,
               loc='upper left', fontsize=9, framealpha=0.9)

    # Latest values annotation box
    latest = df.iloc[-1]
    latest_date = df.index[-1].strftime('%b %d, %Y')
    annotation = (f"Latest ({latest_date}):\n"
                  f"Gold: ${latest['gold']:,.2f}\n"
                  f"Silver: ${latest['silver']:.2f}\n"
                  f"GSR: {latest['gsr']:.1f}")
    ax1.text(0.98, 0.02, annotation, transform=ax1.transAxes,
             fontsize=9, verticalalignment='bottom', horizontalalignment='right',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.85, edgecolor='gray'))

    # Stats box (top right)
    high_gsr = df['gsr'].max()
    low_gsr = df['gsr'].min()
    high_date = df['gsr'].idxmax().strftime('%Y-%m-%d')
    low_date = df['gsr'].idxmin().strftime('%Y-%m-%d')
    stats = (f"GSR Range:\n"
             f"High: {high_gsr:.1f} ({high_date})\n"
             f"Low: {low_gsr:.1f} ({low_date})\n"
             f"Avg: {avg_gsr:.1f}")
    ax1.text(0.98, 0.98, stats, transform=ax1.transAxes,
             fontsize=8, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.85, edgecolor='gray'))

    plt.tight_layout()
    plt.savefig(output_file, dpi=200, bbox_inches='tight')
    plt.close()

    print(f"Chart saved to: {output_file}")
    print(f"  Gold:   ${latest['gold']:,.2f}")
    print(f"  Silver: ${latest['silver']:.2f}")
    print(f"  GSR:    {latest['gsr']:.1f}")


def main():
    parser = argparse.ArgumentParser(description='Generate Gold/Silver Ratio chart from collected data')
    parser.add_argument('--years', type=int, default=10, help='Number of years to display (default: 10)')
    parser.add_argument('--all', action='store_true', help='Plot all available data')
    parser.add_argument('--output', type=str, default=OUTPUT_FILE, help='Output PNG file path')

    args = parser.parse_args()

    df = load_data(years=args.years, use_all=args.all)
    generate_chart(df, output_file=args.output)


if __name__ == '__main__':
    main()
