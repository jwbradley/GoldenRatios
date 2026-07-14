#!/usr/bin/env python3
"""
Update Gold/Silver Ratio chart from collected JSON data.

Reads gsr_history.json (produced by gsr_data_collector.py) and generates
a PNG chart with gold price, silver price, and GSR overlay.

Usage:
  python3 update_gsr_chart.py                  # Default: last 10 years
  python3 update_gsr_chart.py --years 5        # Last 5 years
  python3 update_gsr_chart.py --years 25       # Longer window
  python3 update_gsr_chart.py --all            # Everything in the JSON file
  python3 update_gsr_chart.py --output /tmp/gsr.png

Environment:
  GSR_DATA_DIR  — directory containing gsr_history.json (default: script dir)

Requires: matplotlib, pandas
Educational / informational use only — see DISCLAIMER.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import pandas as pd
except ImportError as e:
    print(f"ERROR importing dependencies: {e}", file=sys.stderr)
    print(
        "Use a dedicated venv with matching numpy/matplotlib versions, e.g.:",
        file=sys.stderr,
    )
    print("  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("GSR_DATA_DIR", str(SCRIPT_DIR)))
HISTORY_FILE = DATA_DIR / "gsr_history.json"
DEFAULT_OUTPUT = DATA_DIR / "GSR_chart.png"


def load_data(years: int = 10, use_all: bool = False) -> pd.DataFrame:
    """Load price history from JSON and filter by date range."""
    if not HISTORY_FILE.is_file():
        print(f"ERROR: {HISTORY_FILE} not found.", file=sys.stderr)
        print("Run gsr_data_collector.py --backfill first.", file=sys.stderr)
        sys.exit(1)

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        print("ERROR: History file is empty.", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    required = {"gold", "silver", "gsr"}
    missing = required - set(df.columns)
    if missing:
        print(f"ERROR: History missing columns: {sorted(missing)}", file=sys.stderr)
        sys.exit(1)

    if not use_all:
        cutoff = datetime.now() - timedelta(days=365 * years)
        df = df[df.index >= cutoff]

    if df.empty:
        print("ERROR: No rows in selected date range.", file=sys.stderr)
        sys.exit(1)

    print(
        f"Loaded {len(df)} records "
        f"({df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')})"
    )
    return df


def generate_chart(df: pd.DataFrame, output_file: Path | str = DEFAULT_OUTPUT) -> None:
    """Generate the GSR chart with dual-axis overlay."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax1 = plt.subplots(figsize=(14, 8))

    color_gold = "#B8860B"
    ax1.plot(df.index, df["gold"], color=color_gold, linewidth=1.5, label="Gold ($/oz)", alpha=0.9)
    ax1.set_xlabel("Date", fontsize=11)
    ax1.set_ylabel("Gold Price ($/oz)", fontsize=11, color=color_gold)
    ax1.tick_params(axis="y", labelcolor=color_gold)
    ax1.grid(True, alpha=0.2)

    ax2 = ax1.twinx()
    color_silver = "#708090"
    ax2.plot(
        df.index, df["silver"], color=color_silver, linewidth=1.5, label="Silver ($/oz)", alpha=0.9
    )
    ax2.set_ylabel("Silver Price ($/oz)", fontsize=11, color=color_silver)
    ax2.tick_params(axis="y", labelcolor=color_silver)

    ax3 = ax1.twinx()
    ax3.spines["right"].set_position(("outward", 65))
    color_gsr = "#1E3A8A"
    ax3.plot(
        df.index, df["gsr"], color=color_gsr, linewidth=1.8, label="Gold/Silver Ratio", alpha=0.8
    )
    ax3.set_ylabel("Gold/Silver Ratio (GSR)", fontsize=11, color=color_gsr)
    ax3.tick_params(axis="y", labelcolor=color_gsr)

    avg_gsr = float(df["gsr"].mean())
    ax3.axhline(y=avg_gsr, color=color_gsr, linestyle="--", alpha=0.4, linewidth=1)
    ax3.text(
        df.index[int(len(df) * 0.02)],
        avg_gsr + 1,
        f"Avg GSR: {avg_gsr:.1f}",
        color=color_gsr,
        fontsize=8,
        alpha=0.7,
    )

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    if len(df) > 365 * 5:
        ax1.xaxis.set_major_locator(mdates.YearLocator())
    else:
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

    date_range = (
        f"{df.index[0].strftime('%b %Y')} - {df.index[-1].strftime('%b %d, %Y')}"
    )
    plt.title(
        f"Gold vs Silver with Gold/Silver Ratio Overlay\n{date_range}",
        fontsize=13,
        pad=20,
    )

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    lines3, labels3 = ax3.get_legend_handles_labels()
    ax1.legend(
        lines1 + lines2 + lines3,
        labels1 + labels2 + labels3,
        loc="upper left",
        fontsize=9,
        framealpha=0.9,
    )

    latest = df.iloc[-1]
    latest_date = df.index[-1].strftime("%b %d, %Y")
    annotation = (
        f"Latest ({latest_date}):\n"
        f"Gold: ${latest['gold']:,.2f}\n"
        f"Silver: ${latest['silver']:.2f}\n"
        f"GSR: {latest['gsr']:.1f}"
    )
    ax1.text(
        0.98,
        0.02,
        annotation,
        transform=ax1.transAxes,
        fontsize=9,
        verticalalignment="bottom",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.85, edgecolor="gray"),
    )

    high_gsr = float(df["gsr"].max())
    low_gsr = float(df["gsr"].min())
    high_date = df["gsr"].idxmax().strftime("%Y-%m-%d")
    low_date = df["gsr"].idxmin().strftime("%Y-%m-%d")
    stats = (
        f"GSR Range:\n"
        f"High: {high_gsr:.1f} ({high_date})\n"
        f"Low: {low_gsr:.1f} ({low_date})\n"
        f"Avg: {avg_gsr:.1f}"
    )
    ax1.text(
        0.98,
        0.98,
        stats,
        transform=ax1.transAxes,
        fontsize=8,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.85, edgecolor="gray"),
    )

    # Small footer disclaimer on the figure
    fig.text(
        0.5,
        0.01,
        "Educational chart only — not investment advice. Data may be delayed or incomplete.",
        ha="center",
        fontsize=7,
        color="gray",
        style="italic",
    )

    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()

    print(f"Chart saved to: {output_path}")
    print(f"  Gold:   ${latest['gold']:,.2f}")
    print(f"  Silver: ${latest['silver']:.2f}")
    print(f"  GSR:    {latest['gsr']:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Gold/Silver Ratio chart from collected data"
    )
    parser.add_argument("--years", type=int, default=10, help="Years to display (default: 10)")
    parser.add_argument("--all", action="store_true", help="Plot all available data")
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help="Output PNG file path",
    )

    args = parser.parse_args()
    df = load_data(years=args.years, use_all=args.all)
    generate_chart(df, output_file=args.output)


if __name__ == "__main__":
    main()
