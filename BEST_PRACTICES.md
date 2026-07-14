# Best practices

Operational guidance for running GoldenRatios reliably. **Not investment advice.** See [DISCLAIMER.md](DISCLAIMER.md).

## Prefer a project virtualenv

System Python often mixes distro `matplotlib` with a newer user-site `numpy`, which can crash chart generation. Use:

```bash
cd /path/to/GoldenRatios
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Point cron at `.venv/bin/python` or use `./run_daily.sh` (auto-detects the venv).

## Initialize once, then append daily

| Script | First run | Ongoing |
|--------|-----------|---------|
| `gsr_data_collector.py` | `--backfill` | no flags |
| `market_ratios_collector.py` | `--backfill` | no flags |
| `update_gsr_chart.py` | after GSR history exists | after each GSR update |

Daily mode re-fetches a short **overlap window** so late prints and partial prior days can be refreshed (especially useful when Dow/S&P were temporarily missing).

## When to run cron

| Goal | Suggested local time (US) | Why |
|------|---------------------------|-----|
| Futures + indices (yfinance) | ~5:30–6:30 PM CT weekdays | After US cash equity close |
| Chart refresh | Immediately after GSR collect | Uses local JSON only |

Weekends/holidays often produce “already up to date” — that is normal.

## Interpreting ratios (context only)

| Ratio | Informal reading (heuristic, not a signal) |
|-------|--------------------------------------------|
| GSR ↑ | Silver weaker vs gold historically in that window |
| GSR ↓ | Silver stronger vs gold |
| Dow/Gold or S&P/Gold ↑ | Equities expensive vs gold (by this crude measure) |
| Dow/Gold or S&P/Gold ↓ | Equities cheap vs gold (by this crude measure) |

These do **not** imply mean reversion timing. Extreme readings can persist for years.

## Data quality checks

```bash
.venv/bin/python gsr_data_collector.py --status
.venv/bin/python market_ratios_collector.py --status
.venv/bin/python market_ratios_collector.py --briefing
```

If latest Dow or S&P is `null`:

1. Re-run the market ratios collector later the same evening.  
2. Confirm network access to Yahoo Finance.  
3. Overlap merge should fill nulls on a later successful download.

## Futures vs spot / FRED

- Default GSR path uses **CME futures** (`GC=F`, `SI=F`). Continuous futures roll can create small jumps.  
- Optional **FRED** gold fix is closer to a bullion reference but still not identical to every retail quote.  
- Do not mix unrelated series in external analysis without noting the source.

## Storage layout

Default: files live next to the scripts. Override with:

```bash
export GSR_DATA_DIR="/var/lib/goldenratios"
export MARKET_RATIOS_DIR="/var/lib/goldenratios"
```

Logs go under `$GSR_DATA_DIR/logs/` (created automatically).

## What not to commit

- History JSON/CSV, PNG charts, `logs/`, `.venv/`, API keys.  
- Keep the repo as **code + docs**; regenerate data on each machine.

## Companion tools

Macro ratios pair well with equity breadth / screening workflows (e.g. a separate MarketBreadth package) for **context**, not for automatic trade execution.
