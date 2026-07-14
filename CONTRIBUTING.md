# Contributing

Thanks for interest in improving GoldenRatios.

## Principles

1. **No investment-advice framing.** Docs and CLI text should stay educational/operational. Keep [DISCLAIMER.md](DISCLAIMER.md) intact and linked from user-facing surfaces.  
2. **Prefer small, reviewable changes.** One concern per PR when practical.  
3. **Do not commit secrets** (API keys, `.env`, personal `.fred_api_key`).  
4. **Do not commit large generated data** by default (`*.json` history, `*.csv`, charts, logs)—see `.gitignore`.  
5. **Keep collectors runnable offline after backfill** (chart script should only need local JSON).

## Local setup

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python gsr_data_collector.py --backfill --start 2024-01-01
.venv/bin/python market_ratios_collector.py --backfill --start 2024-01-01
.venv/bin/python update_gsr_chart.py --years 2
```

## Pull requests

1. Describe **what** changed and **why**.  
2. Note any CLI or file-format changes.  
3. Update [README.md](README.md) and [CHANGELOG.md](CHANGELOG.md) when behavior changes.  
4. Run a short smoke test (`--status`, chart generation) before asking for review.

## Code style

- Python 3.10+ friendly; type hints welcome where they clarify.  
- Prefer explicit paths via `pathlib` / env vars over hard-coded home directories.  
- Soft-fail and clear log lines for cron-friendly operation.

## License

Contributions are expected to be compatible with the project [MIT License](LICENSE).
