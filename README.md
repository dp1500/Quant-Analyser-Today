# Local Nifty Quant Dashboard

Local-first market analytics app for Nifty 50 index, Nifty 50 constituents, and optional Upstox option OI data.

## Tech Stack

- Python data pipeline: `pandas`, `numpy`, `yfinance`, `scipy`, `statsmodels`
- Optional broker data: `upstox-python-sdk`
- Backend/API: `FastAPI`
- Frontend: static HTML, Tailwind CDN, Plotly.js CDN
- Storage: local `data/` artifacts, mainly Parquet plus dashboard JSON

This avoids a frontend build step and keeps daily compute on your laptop.

## Runtime

Use your existing venv:

```powershell
& 'D:\upstocks data fetch  jan 2025\venv\Scripts\python.exe' -m pip install -r requirements.txt
```

Create local env config:

```powershell
Copy-Item .env.example .env
```

Put a fresh Upstox token in `.env` only if you want option OI fetching. Do not commit or paste tokens.

## Daily Flow

1. Fetch market data and compute analytics:

```powershell
& 'D:\upstocks data fetch  jan 2025\venv\Scripts\python.exe' scripts\update_data.py
```

2. Start the dashboard:

```powershell
& 'D:\upstocks data fetch  jan 2025\venv\Scripts\python.exe' -m uvicorn app.main:app --reload --port 8000
```

3. Open:

```text
http://127.0.0.1:8000
```

## Current Dashboard

- Nifty 1-year OHLC chart with 1-year and 1-month ATH/ATL lines
- Regime table for 1-year, 6-month, 3-month, 1-month, and 1-week windows
- Last 5 trading days plus next 5 sessions volatility/range forecast
- Nifty 50 constituent breadth, trend, return, and volatility summary
- Optional option OI panel from saved Upstox artifacts

## Data Layout

- `data/raw/nifty_1y.parquet`
- `data/raw/nifty50_stocks_120d.parquet`
- `data/options/latest_nifty_oi.parquet`
- `data/processed/dashboard_payload.json`

The frontend only reads the processed JSON through the backend.
