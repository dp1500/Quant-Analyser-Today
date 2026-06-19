from __future__ import annotations

from io import StringIO
from typing import List

import pandas as pd
import requests


NIFTY_100_FALLBACK = [
    "ABB", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "AMBUJACEM", "APOLLOHOSP", "ASIANPAINT",
    "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BAJAJHLDNG", "BANKBARODA", "BEL", "BHARTIARTL",
    "BOSCHLTD", "BPCL", "BRITANNIA", "CANBK", "CHOLAFIN", "CIPLA", "COALINDIA", "DABUR", "DIVISLAB",
    "DLF", "DMART", "DRREDDY", "EICHERMOT", "ETERNAL", "GAIL", "GODREJCP", "GRASIM", "HAL", "HAVELLS",
    "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "HYUNDAI", "ICICIBANK",
    "ICICIGI", "ICICIPRULI", "INDHOTEL", "INDIGO", "INDUSINDBK", "INFY", "IOC", "IRFC", "ITC", "JINDALSTEL",
    "JIOFIN", "JSWENERGY", "JSWSTEEL", "KOTAKBANK", "LICI", "LODHA", "LT", "LTIM", "M&M", "MARUTI",
    "MAXHEALTH", "MOTHERSON", "NAUKRI", "NESTLEIND", "NTPC", "ONGC", "PFC", "PIDILITIND", "PNB",
    "POWERGRID", "RECLTD", "RELIANCE", "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN", "SIEMENS",
    "SUNPHARMA", "SWIGGY", "TATACONSUM", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TITAN", "TORNTPHARM",
    "TRENT", "TVSMOTOR", "ULTRACEMCO", "UNITDSPR", "VBL", "VEDL", "WIPRO", "ZYDUSLIFE", "TMPV", "TMCV",
]


def yahoo_symbol(symbol: str) -> str:
    return f"{symbol}.NS"


def load_nifty100_symbols() -> List[str]:
    url = "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        if "Symbol" in df.columns and not df.empty:
            return sorted(df["Symbol"].dropna().astype(str).str.strip().unique().tolist())
    except Exception as exc:
        print(f"Nifty 100 constituent fetch failed, using fallback list: {exc}")
    return NIFTY_100_FALLBACK
