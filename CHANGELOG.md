# Changelog

All notable changes to this project are documented here.

## [1.1.0] — 2026-07-14

### Improved

- **`gsr_data_collector.py`**: Real hybrid path — optional FRED gold (`GOLDAMGBD228NLBM`) with yfinance `GC=F` fallback; silver from `SI=F`. Atomic JSON writes, file logging under `logs/`, daily **overlap refresh**, `--briefing`, clearer status.
- **`market_ratios_collector.py`**: Download **retries**, atomic JSON writes, file logging, daily overlap merge that **prefers non-null** Dow/S&P when refreshing a day, better null handling in status/briefing.
- **`update_gsr_chart.py`**: Safer imports/error messages for numpy/matplotlib mismatches; creates output dirs; small figure disclaimer footer.
- **`run_daily.sh`**: Soft-fail orchestrator (GSR → market ratios → chart) with combined log; prefers project `.venv`.
- **Repo hygiene**: Expanded `.gitignore`, `requirements.txt`, untrack large generated JSON from version control.
- **Docs**: Accurate README (sources match code), [DISCLAIMER.md](DISCLAIMER.md), [BEST_PRACTICES.md](BEST_PRACTICES.md), [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), this changelog.

### Notes

- Futures-based history is **not** identical to LBMA/FRED-only series; re-backfill if you change preferred gold source and need a consistent series.
- Improvements are operational/engineering only. They do **not** guarantee trading profits. See [DISCLAIMER.md](DISCLAIMER.md).

## [1.0.0] — 2026-06

- Initial collectors: GSR (hybrid/yfinance evolution), market ratios (yfinance), chart generator.
- README and MIT license.
