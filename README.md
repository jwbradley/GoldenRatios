# Gold/Silver Ratio & Market Ratios — Data Collectors & Chart Generator

Automated daily collection of precious metals and index prices with ratio calculations and chart generation.

## Scripts

| Script | Source | Purpose |
|--------|--------|---------|
| `gsr_data_collector.py` | FRED API | Gold/silver prices from 1968, maintains `gsr_history.json` |
| `market_ratios_collector.py` | Yahoo Finance | Gold, silver, Dow, S&P 500 from 2000, calculates GSR + Dow/Gold + S&P/Gold ratios |
| `update_gsr_chart.py` | Local JSON | Reads history JSON and generates PNG chart |

### Which collector to use?

| Need | Use |
|------|-----|
| Precious metals only, back to 1968 | `gsr_data_collector.py` (FRED) |
| All ratios (GSR + Dow/Gold + S&P/Gold), from 2000 | `market_ratios_collector.py` (yfinance) |
| Briefing-ready ratio summary for reports | `market_ratios_collector.py --briefing` |
| Both (long history metals + index ratios) | Run both on cron |

---

## Overview

This script runs in two modes:

| Mode | Command | Purpose |
|------|---------|---------|
| Backfill | `python3 gsr_data_collector.py --backfill` | One-time pull of full historical data (back to 1968) |
| Daily | `python3 gsr_data_collector.py` | Appends only new data since last run |

Designed to run unattended on a Raspberry Pi (or any Linux box) via cron.

---

## Data Source

| Field | Source Series | Description |
|-------|--------------|-------------|
| Gold | GOLDAMGBD228NLBM | London Bullion Market Association Gold Fixing Price 10:30 AM (USD/Troy Oz) |
| Silver | SLVPRUSD | London Bullion Market Association Silver Fixing Price (USD/Troy Oz) |
| GSR | Calculated | Gold price / Silver price |

- **Provider:** Federal Reserve Bank of St. Louis (FRED)
- **Frequency:** Daily (business days only)
- **History available:** April 1, 1968 to present
- **Update time:** Typically available by 3-4 PM ET same day

---

## Requirements

- Python 3.7+
- `fredapi` — FRED API wrapper
- `pandas` — data manipulation
- A free FRED API key

### Install Dependencies

```bash
pip install fredapi pandas
```

### Get a FRED API Key (Free)

1. Create account: https://fredaccount.stlouisfed.org/login/secure/
2. Request API key: https://fredaccount.stlouisfed.org/apikeys
3. Key is issued instantly (32-character alphanumeric string)

---

## Configuration

The script looks for your API key in this order:

1. **Environment variable:** `FRED_API_KEY`
2. **Key file:** `~/.fred_api_key` (plain text, just the key)

### Option A: Environment Variable

```bash
# Add to ~/.bashrc or ~/.profile
export FRED_API_KEY="abcdef1234567890abcdef1234567890"
```

### Option B: Key File

```bash
echo "abcdef1234567890abcdef1234567890" > ~/.fred_api_key
chmod 600 ~/.fred_api_key
```

### Data Directory

By default, output files are written to the same directory as the script. Override with:

```bash
export GSR_DATA_DIR="/home/pi/data/metals"
```

---

## Usage

### First Run: Backfill Historical Data

```bash
# Full history from 1968
python3 gsr_data_collector.py --backfill

# Or just the last 10 years
python3 gsr_data_collector.py --backfill --start 2016-01-01

# Or from year 2000
python3 gsr_data_collector.py --backfill --start 2000-01-01
```

This creates `gsr_history.json` with all available data points.

### Daily Updates (Cron)

```bash
python3 gsr_data_collector.py
```

Reads the last date in `gsr_history.json`, fetches any new data since then, deduplicates, and appends.

### Check Status

```bash
python3 gsr_data_collector.py --status
```

Shows total records, date range, latest values, and file size.

### Export to CSV (for spreadsheet analysis)

```bash
# Default (saves to gsr_history.csv in same directory)
python3 gsr_data_collector.py --csv

# Custom output path
python3 gsr_data_collector.py --csv ~/Documents/gold_silver_history.csv
```

Columns: `date, gold, silver, gsr`

---

## Cron Setup

Edit crontab on your Raspberry Pi:

```bash
crontab -e
```

Add this line (runs at 6:00 PM CT Monday-Friday):

```cron
0 18 * * 1-5 /usr/bin/python3 /home/pi/gsr_data_collector.py >> /home/pi/logs/gsr_collector.log 2>&1
```

**Why 6 PM?** The London gold/silver fix happens at 10:30 AM and 3:00 PM London time (5:30 AM and 10:00 AM ET). FRED typically publishes the data by early afternoon ET. Running at 6 PM ensures the data is available.

Create the log directory:

```bash
mkdir -p /home/pi/logs
```

---

## Output Files

### gsr_history.json

Full price history as a JSON array. Each record:

```json
[
  {
    "date": "1968-04-01",
    "gold": 37.37,
    "silver": 2.145,
    "gsr": 17.4219
  },
  {
    "date": "1968-04-02",
    "gold": 37.75,
    "silver": 2.17,
    "gsr": 17.3963
  }
]
```

Full history from 1968 is approximately 14,000+ records (~1.5 MB).

### gsr_latest.json

Just the most recent data point (useful for dashboards or quick reads):

```json
{
  "date": "2026-06-20",
  "gold": 4142.80,
  "silver": 62.19,
  "gsr": 66.6131
}
```

### GSR_chart.png

Generated PNG chart (200 DPI) showing gold price, silver price, and GSR overlay with:
- Dual Y-axes (gold left, silver right)
- GSR on offset third axis
- Historical average GSR line
- Stats box (high/low/avg GSR with dates)
- Latest values annotation

---

## Chart Generator (update_gsr_chart.py)

Reads `gsr_history.json` and produces a PNG chart. Run after the data collector, or chain them together.

### Usage

```bash
# Default: last 10 years
python3 update_gsr_chart.py

# Last 5 years
python3 update_gsr_chart.py --years 5

# Last 25 years
python3 update_gsr_chart.py --years 25

# Everything in the JSON file
python3 update_gsr_chart.py --all

# Custom output path
python3 update_gsr_chart.py --output /home/pi/charts/gold_silver.png
```

### Chaining with Data Collector

Run both sequentially — collect new data, then regenerate the chart:

```bash
python3 gsr_data_collector.py && python3 update_gsr_chart.py
```

Or in a single cron entry:

```cron
0 18 * * 1-5 /usr/bin/python3 /home/pi/scripts/gsr_data_collector.py && /usr/bin/python3 /home/pi/scripts/update_gsr_chart.py >> /home/pi/logs/gsr_collector.log 2>&1
```

### Chart Features

- **Gold price** — dark gold line, left Y-axis
- **Silver price** — slate gray line, right Y-axis
- **GSR** — dark blue line, offset right Y-axis
- **Average GSR** — dashed blue line showing period mean
- **Stats box** — GSR high/low/average with dates
- **Latest values** — current gold, silver, and GSR in annotation box
- **Auto-scaling** — X-axis adapts tick spacing based on date range

### Requirements

```bash
pip install matplotlib pandas
```

(`fredapi` is NOT needed for the chart script — it only reads the JSON file.)

---

## Market Ratios Collector (market_ratios_collector.py)

Pulls gold, silver, Dow Jones, and S&P 500 from Yahoo Finance and calculates three ratios. No API key required.

### Requirements

```bash
pip install yfinance pandas
```

### Usage

```bash
# Initial backfill (full history from 2000)
python3 market_ratios_collector.py --backfill

# From a specific year
python3 market_ratios_collector.py --backfill --start 2016-01-01

# Daily update (appends new data)
python3 market_ratios_collector.py

# Check status with last 5 days
python3 market_ratios_collector.py --status

# Output briefing snippet (markdown, for market reports)
python3 market_ratios_collector.py --briefing

# Export to CSV (for spreadsheet analysis)
python3 market_ratios_collector.py --csv

# Export to specific path
python3 market_ratios_collector.py --csv ~/Documents/market_ratios.csv
```

CSV columns: `date, gold, silver, dow, sp500, gsr, dow_gold, sp500_gold`

### Data Collected

| Field | Symbol | Source |
|-------|--------|--------|
| Gold | GC=F | CME Gold Futures |
| Silver | SI=F | CME Silver Futures |
| Dow | ^DJI | Dow Jones Industrial Average |
| S&P 500 | ^GSPC | S&P 500 Index |

### Ratios Calculated

| Ratio | Formula | Interpretation |
|-------|---------|----------------|
| GSR (Gold/Silver) | Gold / Silver | Higher = silver undervalued vs gold |
| Dow/Gold | Dow / Gold per oz | Higher = stocks outperforming gold |
| S&P/Gold | S&P 500 / Gold per oz | Higher = stocks outperforming gold |

### Output Files

- `market_ratios_history.json` — Full history (~1.2 MB for 6,400+ records from 2000)
- `market_ratios_latest.json` — Most recent data point

### Sample Record

```json
{
  "date": "2026-06-22",
  "gold": 4182.30,
  "silver": 65.55,
  "dow": 51712.71,
  "sp500": 7472.79,
  "gsr": 63.80,
  "dow_gold": 12.37,
  "sp500_gold": 1.7869
}
```

### Briefing Output (--briefing)

Produces markdown suitable for pasting into morning/afternoon market reports:

```
## Market Ratios (2026-06-22)

- **Gold/Silver Ratio:** 63.8 (+2.10)
  - Gold: $4,182.30 | Silver: $65.55
- **Dow/Gold Ratio:** 12.37 (+0.160)
  - Dow: 51,712.71 | Gold: $4,182.30
- **S&P 500/Gold Ratio:** 1.7869 (+0.0112)
  - S&P 500: 7,472.79 | Gold: $4,182.30

- Dow/Gold 1-year change: +5.2% (from 11.76)
- GSR 1-year change: -12.3% (from 72.8)
```

### Cron (run after market close)

```cron
30 17 * * 1-5 /usr/bin/python3 /home/pi/scripts/market_ratios_collector.py >> /home/pi/logs/market_ratios.log 2>&1
```

---

## Raspberry Pi Deployment

### Complete Setup (from scratch)

```bash
# 1. Install Python packages
pip install fredapi pandas matplotlib yfinance

# 2. Store your FRED API key (only needed for gsr_data_collector.py)
echo "your_key_here" > ~/.fred_api_key
chmod 600 ~/.fred_api_key

# 3. Create directories
mkdir -p /home/pi/scripts /home/pi/data/metals /home/pi/logs

# 4. Copy all scripts
cp gsr_data_collector.py /home/pi/scripts/
cp market_ratios_collector.py /home/pi/scripts/
cp update_gsr_chart.py /home/pi/scripts/

# 5. Set data directory (shared by all scripts)
echo 'export GSR_DATA_DIR="/home/pi/data/metals"' >> ~/.bashrc
echo 'export MARKET_RATIOS_DIR="/home/pi/data/metals"' >> ~/.bashrc
source ~/.bashrc

# 6. Run initial backfills
python3 /home/pi/scripts/gsr_data_collector.py --backfill --start 2000-01-01
python3 /home/pi/scripts/market_ratios_collector.py --backfill

# 7. Verify both
python3 /home/pi/scripts/gsr_data_collector.py --status
python3 /home/pi/scripts/market_ratios_collector.py --status

# 8. Generate initial chart
python3 /home/pi/scripts/update_gsr_chart.py

# 9. Add cron jobs
(crontab -l 2>/dev/null; echo '# Gold/Silver (FRED) + chart - 6 PM M-F') | crontab -
(crontab -l 2>/dev/null; echo '0 18 * * 1-5 /usr/bin/python3 /home/pi/scripts/gsr_data_collector.py && /usr/bin/python3 /home/pi/scripts/update_gsr_chart.py >> /home/pi/logs/gsr_collector.log 2>&1') | crontab -
(crontab -l 2>/dev/null; echo '# Market ratios (yfinance) - 5:30 PM M-F') | crontab -
(crontab -l 2>/dev/null; echo '30 17 * * 1-5 /usr/bin/python3 /home/pi/scripts/market_ratios_collector.py >> /home/pi/logs/market_ratios.log 2>&1') | crontab -
```

### Verify Cron is Running

After the first scheduled run, check:

```bash
# Check the log
tail -20 /home/pi/logs/gsr_collector.log

# Check the data
python3 /home/pi/scripts/gsr_data_collector.py --status
```

---

## Log Output Examples

### Successful backfill:

```
2026-06-23 10:00:00 BACKFILL: Pulling full history from 2000-01-01...
2026-06-23 10:00:00 Fetching data from 2000-01-01 to today...
2026-06-23 10:00:03 Fetched 6472 data points.
2026-06-23 10:00:03 Saved 6472 records to /home/pi/data/metals/gsr_history.json
2026-06-23 10:00:03 Backfill complete: 6472 records
2026-06-23 10:00:03   First: 2000-01-04 - Gold: $282.05, Silver: $5.33, GSR: 52.9175
2026-06-23 10:00:03   Last:  2026-06-20 - Gold: $4142.80, Silver: $62.19, GSR: 66.6131
```

### Successful daily update:

```
2026-06-23 18:00:00 DAILY UPDATE: Fetching from 2026-06-21 (last record: 2026-06-20)...
2026-06-23 18:00:00 Fetching data from 2026-06-21 to today...
2026-06-23 18:00:01 Fetched 2 data points.
2026-06-23 18:00:01 Added 2 new records (total: 6474)
2026-06-23 18:00:01   2026-06-21 - Gold: $4150.00, Silver: $62.50, GSR: 66.4000
2026-06-23 18:00:01   2026-06-23 - Gold: $4160.25, Silver: $63.10, GSR: 65.9310
```

### Already up to date:

```
2026-06-23 18:00:00 Already up to date (last record: 2026-06-23). Nothing to fetch.
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No FRED API key found` | Set `FRED_API_KEY` env var or create `~/.fred_api_key` |
| `No existing history found` | Run with `--backfill` first to initialize |
| `No new data available` | FRED may not have published today's fix yet (try later) |
| `ModuleNotFoundError: fredapi` | Run `pip install fredapi pandas` |
| Weekend/holiday shows no data | Normal — London fix only occurs on business days |
| Rate limited (HTTP 429) | Unlikely with single daily call; wait 60 seconds if hit |

---

## Using the Data

### Quick Python read:

```python
import json

with open('gsr_history.json') as f:
    data = json.load(f)

# Latest GSR
print(f"GSR: {data[-1]['gsr']} ({data[-1]['date']})")

# Average GSR last 30 trading days
recent = data[-30:]
avg = sum(r['gsr'] for r in recent) / len(recent)
print(f"30-day avg GSR: {avg:.2f}")
```

### Generate a chart:

```bash
# After collecting data, generate the chart
python3 update_gsr_chart.py --years 10 --output /home/pi/charts/GSR_10yr.png
```

---

## File Summary

| File | Created By | Purpose |
|------|-----------|---------|
| `gsr_data_collector.py` | You | Pulls gold/silver from FRED (1968+) |
| `market_ratios_collector.py` | You | Pulls gold/silver/Dow/S&P from Yahoo Finance (2000+) |
| `update_gsr_chart.py` | You | Reads JSON, generates PNG chart |
| `gsr_history.json` | FRED collector | Gold/silver price history |
| `gsr_latest.json` | FRED collector | Most recent gold/silver point |
| `market_ratios_history.json` | Ratios collector | Full history with all ratios |
| `market_ratios_latest.json` | Ratios collector | Most recent ratios point |
| `GSR_chart.png` | Chart script | Generated chart image |
| `~/.fred_api_key` | You (manual) | Your FRED API key |

---

## Workflow Diagram

```
     FRED API                          Yahoo Finance
        |                                    |
        v                                    v
+---------------------+        +----------------------------+
| gsr_data_collector   |        | market_ratios_collector     |
| (6 PM M-F)          |        | (5:30 PM M-F)              |
+---------------------+        +----------------------------+
    |           |                   |              |
    v           v                   v              v
gsr_history  gsr_latest    market_ratios     market_ratios
   .json       .json       _history.json     _latest.json
    |                              |
    v                              v
+---------------------+    (--briefing flag)
| update_gsr_chart.py |           |
+---------------------+           v
    |                    Morning/Afternoon
    v                    Market Briefings
GSR_chart.png
```

---

## License

Internal use. Data sourced from FRED (Federal Reserve Bank of St. Louis) under their terms of use.
