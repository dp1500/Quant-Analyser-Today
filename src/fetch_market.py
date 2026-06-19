from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import gzip
import json

import pandas as pd
import requests
import yfinance as yf

from src.storage import save_parquet
from src.universe import load_nifty100_symbols, yahoo_symbol


def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df = df.rename(
        columns={
            date_col: "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    keep = [col for col in ["date", "open", "high", "low", "close", "adj_close", "volume"] if col in df.columns]
    df = df[keep].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df.dropna(subset=["open", "high", "low", "close"])


def _upstox_candles_to_df(candles) -> pd.DataFrame:
    rows = []
    for candle in candles or []:
        values = list(candle)
        rows.append(
            {
                "date": pd.to_datetime(values[0]).strftime("%Y-%m-%d"),
                "open": values[1],
                "high": values[2],
                "low": values[3],
                "close": values[4],
                "volume": values[5] if len(values) > 5 else None,
            }
        )
    return pd.DataFrame(rows).dropna(subset=["open", "high", "low", "close"])


def fetch_nifty_index_from_upstox(access_token: str, data_dir: Path, days: int = 365) -> pd.DataFrame:
    if not access_token:
        return pd.DataFrame()

    import upstox_client

    config = upstox_client.Configuration()
    config.access_token = access_token
    api_client = upstox_client.ApiClient(config)
    history_api = upstox_client.HistoryApi(api_client)

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    response = history_api.get_historical_candle_data1(
        "NSE_INDEX|Nifty 50",
        "day",
        to_date,
        from_date,
        "2.0",
    )
    candles = getattr(getattr(response, "data", None), "candles", [])
    df = _upstox_candles_to_df(candles).sort_values("date").tail(days)
    if not df.empty:
        save_parquet(df, data_dir / "raw" / "nifty_1y.parquet")
    return df


def _history_api(access_token: str):
    import upstox_client

    config = upstox_client.Configuration()
    config.access_token = access_token
    api_client = upstox_client.ApiClient(config)
    return upstox_client.HistoryApi(api_client)


def _fetch_upstox_daily(history_api, instrument_key: str, days: int) -> pd.DataFrame:
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=int(days * 1.55) + 20)).strftime("%Y-%m-%d")
    response = history_api.get_historical_candle_data1(instrument_key, "day", to_date, from_date, "2.0")
    candles = getattr(getattr(response, "data", None), "candles", [])
    return _upstox_candles_to_df(candles).sort_values("date").tail(days)


def _load_upstox_nse_equity_map(data_dir: Path) -> dict[str, str]:
    cache_path = data_dir / "raw" / "upstox_nse_instruments.json.gz"
    if not cache_path.exists():
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        cache_path.write_bytes(response.content)

    with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
        instruments = json.load(handle)

    mapping = {}
    for item in instruments:
        if item.get("segment") == "NSE_EQ" and item.get("instrument_type") == "EQ":
            symbol = item.get("trading_symbol") or item.get("tradingsymbol")
            key = item.get("instrument_key")
            if symbol and key:
                mapping[symbol] = key
    return mapping


def fetch_nifty_index(symbol: str, data_dir: Path, access_token: str = "") -> pd.DataFrame:
    if access_token:
        try:
            df = fetch_nifty_index_from_upstox(access_token, data_dir)
            if not df.empty:
                return df
        except Exception as exc:
            print(f"Upstox Nifty OHLC fetch failed, falling back to yfinance: {exc}")

    raw = yf.download(symbol, period="1y", interval="1d", auto_adjust=False, progress=False)
    df = _clean_ohlcv(raw)
    if df.empty:
        raise RuntimeError(f"No index data returned by yfinance for {symbol}")
    save_parquet(df, data_dir / "raw" / "nifty_1y.parquet")
    return df


def fetch_nifty100_stocks(data_dir: Path, access_token: str = "", days: int = 504) -> pd.DataFrame:
    symbols = load_nifty100_symbols()
    frames: list[pd.DataFrame] = []
    upstox_map = {}
    history_api = None
    if access_token:
        try:
            upstox_map = _load_upstox_nse_equity_map(data_dir)
            history_api = _history_api(access_token)
        except Exception as exc:
            print(f"Upstox equity mapper unavailable, falling back to yfinance: {exc}")

    for symbol in symbols:
        df = pd.DataFrame()
        if history_api and symbol in upstox_map:
            try:
                df = _fetch_upstox_daily(history_api, upstox_map[symbol], days)
            except Exception as exc:
                print(f"Upstox stock fetch failed for {symbol}, falling back: {exc}")

        if df.empty:
            raw = yf.download(yahoo_symbol(symbol), period="2y", interval="1d", auto_adjust=False, progress=False)
            df = _clean_ohlcv(raw).tail(days)

        if df.empty:
            continue
        df["symbol"] = symbol
        frames.append(df)
    if not frames:
        raise RuntimeError("No Nifty 100 stock data returned")
    result = pd.concat(frames, ignore_index=True)
    result["fetched_at"] = datetime.now(timezone.utc).isoformat()
    save_parquet(result, data_dir / "raw" / "nifty100_stocks_2y.parquet")
    return result
