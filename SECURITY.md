# Security Policy

## This project’s risk profile

GoldenRatios is a set of **local scripts** that download **public market data** and write **JSON/CSV/PNG/logs** on disk. By default it does not:

- Hold brokerage credentials  
- Place orders  
- Open network ports  
- Require cloud accounts  

An optional **FRED API key** may be used for LBMA-style gold fix data. Treat that key as a secret.

## Secrets

| Secret | Recommended storage |
|--------|---------------------|
| FRED API key | `FRED_API_KEY` environment variable, or `~/.fred_api_key` with mode `600` |

**Do not commit** `.fred_api_key`, `.env`, or other credential files. They are listed in `.gitignore`.

## Reporting a vulnerability

If you find a security issue (unsafe path handling, accidental secret logging, dependency issues):

1. Prefer a **private** report to the repository maintainer (GitHub Security Advisory if enabled).  
2. Please avoid public exploit details for severe issues until a fix is available.

## Operational hygiene

- Do not point cron logs at world-writable shared paths without access control.  
- History JSON files grow over time; keep disk quotas in mind.  
- Treat downloaded price data as untrusted input (unexpected sizes, missing fields).  
- Prefer a project **venv** so system package conflicts (e.g. numpy/matplotlib) do not surface as opaque failures.

## Dependencies

Pin or periodically update `yfinance`, `pandas`, `matplotlib`, `numpy`, and optional `fredapi`. Report supply-chain issues to those upstream projects as well.

## Disclaimer

Security of your trading capital is separate from software security. See [DISCLAIMER.md](DISCLAIMER.md).
