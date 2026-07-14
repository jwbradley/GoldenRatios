# GoldenRatios — Gold/Silver & Market Ratio Collectors

Local Python tools that **collect**, **store**, and **chart** a few classic macro ratios:

| Ratio | Formula | Typical use (context only) |
|-------|---------|----------------------------|
| **GSR** | Gold ÷ Silver | Relative strength of silver vs gold |
| **Dow/Gold** | Dow Jones ÷ Gold ($/oz) | Equities vs gold (very rough) |
| **S&P/Gold** | S&P 500 ÷ Gold ($/oz) | Same idea for the S&P |

> **Educational / informational only.** Not investment advice. Not guaranteed to make money.  
> **Past ratios are not predictive.** Full text: [DISCLAIMER.md](DISCLAIMER.md).

Companion idea: pair these macro snapshots with equity breadth tools (e.g. a separate MarketBreadth package) for research context—not automated trading.

---

## Documentation map

| Doc | Contents |
|-----|----------|
| [BEST_PRACTICES.md](BEST_PRACTICES.md) | Cron, venv, data quality, interpretation caveats |
| [DISCLAIMER.md](DISCLAIMER.md) | Risk / no-advice disclaimer |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [SECURITY.md](SECURITY.md) | Secrets, reporting, ops hygiene |
| [LICENSE](LICENSE) | MIT |

---

## Scripts

| Script | Data sources | Purpose |
|--------|--------------|---------|
| `gsr_data_collector.py` | yfinance `GC=F`/`SI=F`; optional FRED gold | GSR history + latest |
| `market_ratios_collector.py` | yfinance gold, silver, `^DJI`, `^GSPC` | GSR + Dow/Gold + S&P/Gold |
| `update_gsr_chart.py` | Local `gsr_history.json` | PNG chart |
| `run_daily.sh` | — | Soft-fail daily: GSR → ratios → chart |

### Which collector to use?

| Need | Use |
|------|-----|
| GSR only + chart | `gsr_data_collector.py` + `update_gsr_chart.py` |
| GSR + equity/gold ratios + briefing markdown | `market_ratios_collector.py` |
| Unattended daily stack | `./run_daily.sh` |

Both collectors can run; they write **different** history files.

---

## Requirements

- Python **3.10+** recommended  
- Packages: see [requirements.txt](requirements.txt)

```bash
cd /path/to/GoldenRatios
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```

**Why a venv?** Mixing system `matplotlib` with a newer user-site `numpy` often breaks chart generation. The project venv avoids that.

### Optional: FRED API key (GSR gold fix)

Only needed if you want LBMA-style gold from FRED instead of futures when available.

1. Free key: https://fredaccount.stlouisfed.org/apikeys  
2. Store one of:
   - `export FRED_API_KEY="..."`  
   - `echo "..." > ~/.fred_api_key && chmod 600 ~/.fred_api_key`  

Never commit the key file (see [SECURITY.md](SECURITY.md)).

---

## Configuration

| Variable | Used by | Default |
|----------|---------|---------|
| `GSR_DATA_DIR` | GSR collector, chart, daily script | Directory of the scripts |
| `MARKET_RATIOS_DIR` | Market ratios collector | `GSR_DATA_DIR` if set, else script dir |
| `FRED_API_KEY` | Optional FRED gold | unset |

Logs are written under `$GSR_DATA_DIR/logs/` (created automatically).

---

## Quick start

```bash
# 1) History (once)
.venv/bin/python gsr_data_collector.py --backfill --start 2000-01-01
.venv/bin/python market_ratios_collector.py --backfill --start 2000-01-01

# 2) Check
.venv/bin/python gsr_data_collector.py --status
.venv/bin/python market_ratios_collector.py --status

# 3) Chart + briefing
.venv/bin/python update_gsr_chart.py --years 10
.venv/bin/python market_ratios_collector.py --briefing
```

### Daily updates

```bash
# Individual
.venv/bin/python gsr_data_collector.py
.venv/bin/python market_ratios_collector.py
.venv/bin/python update_gsr_chart.py

# Or all soft-fail steps + shared run log
./run_daily.sh
```

### Cron example

```cron
# After US cash close (adjust path/timezone for your box)
30 17 * * 1-5 /home/james/myPrograms/KSI/GoldenRatios/run_daily.sh
```

---

## Data sources (important)

### GSR collector (`gsr_data_collector.py`)

| Field | Default source | Optional |
|-------|----------------|----------|
| Gold | CME futures `GC=F` (yfinance) | FRED `GOLDAMGBD228NLBM` if key + `fredapi` work |
| Silver | CME futures `SI=F` (yfinance) | — |
| GSR | Gold ÷ Silver on overlapping dates | — |

Futures are **not** spot bullion. Contract rolls can introduce small jumps. FRED gold + futures silver is a **hybrid** series—fine for monitoring, not a pure academic LBMA GSR.

Default history start: **2000-01-01** (futures availability). Older pure FRED/LBMA series are out of scope of the default path.

### Market ratios (`market_ratios_collector.py`)

| Field | Symbol |
|-------|--------|
| Gold | `GC=F` |
| Silver | `SI=F` |
| Dow | `^DJI` |
| S&P 500 | `^GSPC` |

Yahoo Finance can occasionally return **empty index series** for a day. Collectors retry and **re-merge** a short overlap window on daily runs so null Dow/S&P can be filled later. Always check `--status` if briefings look incomplete.

---

## CLI reference

### `gsr_data_collector.py`

| Flag | Action |
|------|--------|
| `--backfill` | Full pull from `--start` |
| `--start YYYY-MM-DD` | Backfill start (default `2000-01-01`) |
| *(none)* | Daily update + overlap refresh |
| `--status` | Record count, range, latest |
| `--briefing` | Markdown GSR snippet |
| `--csv [path]` | Export `gsr_history.csv` |

### `market_ratios_collector.py`

| Flag | Action |
|------|--------|
| `--backfill` / `--start` | Full history |
| *(none)* | Daily update + overlap merge |
| `--status` | Status + last 5 days table |
| `--briefing` | Markdown for reports |
| `--csv [path]` | Export full history CSV |

### `update_gsr_chart.py`

| Flag | Action |
|------|--------|
| `--years N` | Window (default 10) |
| `--all` | Entire JSON history |
| `--output path` | PNG path (default `GSR_chart.png` in data dir) |

---

## Output files

Generated files are **gitignored** by default (regenerate locally).

| File | Producer |
|------|----------|
| `gsr_history.json` / `gsr_latest.json` | GSR collector |
| `gsr_history.csv` | GSR `--csv` |
| `market_ratios_history.json` / `market_ratios_latest.json` | Market ratios collector |
| `market_ratios_history.csv` | Market ratios `--csv` |
| `GSR_chart.png` | Chart script |
| `logs/gsr_collector.log` | GSR + chart logging |
| `logs/market_ratios.log` | Market ratios logging |
| `logs/run_daily.log` | `run_daily.sh` |

### Sample GSR record

```json
{
  "date": "2026-07-14",
  "gold": 4035.9,
  "silver": 58.415,
  "gsr": 69.0901
}
```

### Sample market ratios record

```json
{
  "date": "2026-07-14",
  "gold": 4035.9,
  "silver": 58.415,
  "dow": 44750.12,
  "sp500": 6250.45,
  "gsr": 69.0901,
  "dow_gold": 11.088,
  "sp500_gold": 1.549
}
```

---

## Workflow

```
          yfinance (+ optional FRED gold)
                    |
        +-----------+-----------+
        v                       v
 gsr_data_collector    market_ratios_collector
        |                       |
        v                       v
 gsr_history.json      market_ratios_history.json
        |
        v
 update_gsr_chart.py  -->  GSR_chart.png

 run_daily.sh  runs all three (soft-fail) and logs under logs/
```

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| `ModuleNotFoundError` | Install into `.venv` from `requirements.txt` |
| matplotlib / numpy import crash | Use `.venv` (see [BEST_PRACTICES.md](BEST_PRACTICES.md)) |
| No history | Run `--backfill` once |
| Latest Dow/S&P is null | Re-run market ratios later; check network / Yahoo |
| FRED not used | Key missing or `fredapi` not installed — falls back to `GC=F` |
| Chart says history missing | Run GSR collector first; check `GSR_DATA_DIR` |
| Weekend “already up to date” | Normal for business-day series |

---

## Using the data (example)

```python
import json
from pathlib import Path

data = json.loads(Path("gsr_history.json").read_text())
print(f"GSR: {data[-1]['gsr']} ({data[-1]['date']})")
recent = data[-30:]
print(f"30-day avg GSR: {sum(r['gsr'] for r in recent)/len(recent):.2f}")
```

---

## License

[MIT](LICENSE) © James W. Bradley — applies to software and docs in this repo, **not** to third-party market data.

**By using these tools you agree to [DISCLAIMER.md](DISCLAIMER.md).**
