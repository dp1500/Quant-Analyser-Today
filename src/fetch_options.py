from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.storage import save_parquet


def _as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return {}


def _nested(obj: dict[str, Any], *keys: str) -> Any:
    cursor: Any = obj
    for key in keys:
        if cursor is None:
            return None
        cursor = _as_dict(cursor) if not isinstance(cursor, dict) else cursor
        cursor = cursor.get(key)
    return cursor


def _option_candles_to_df(candles, strike: float, side: str, instrument_key: str, expiry: str) -> pd.DataFrame:
    rows = []
    for candle in candles or []:
        values = list(candle)
        if len(values) < 7:
            continue
        rows.append(
            {
                "timestamp": pd.to_datetime(values[0]).tz_localize(None),
                "open": values[1],
                "high": values[2],
                "low": values[3],
                "close": values[4],
                "volume": values[5],
                "oi": values[6],
                "strike": float(strike),
                "side": side,
                "instrument_key": instrument_key,
                "expiry": expiry,
            }
        )
    return pd.DataFrame(rows)


def fetch_latest_nifty_oi(access_token: str, data_dir: Path, atm_reference: Optional[float] = None) -> pd.DataFrame:
    """Fetch a compact latest-expiry Nifty option OI snapshot when Upstox allows it.

    Upstox SDK method names have changed across versions. This function uses the
    common option-chain endpoint shape first and raises a clear error if the
    installed SDK/account does not expose it.
    """
    if not access_token:
        return pd.DataFrame()

    import upstox_client

    config = upstox_client.Configuration()
    config.access_token = access_token
    api_client = upstox_client.ApiClient(config)
    history_api = upstox_client.HistoryApi(api_client)

    if not hasattr(upstox_client, "OptionsApi"):
        raise RuntimeError("Installed upstox_client does not expose OptionsApi.")

    option_api = upstox_client.OptionsApi(api_client)
    if not hasattr(option_api, "get_put_call_option_chain"):
        raise RuntimeError("Installed Upstox OptionsApi has no get_put_call_option_chain method.")

    contracts_resp = option_api.get_option_contracts("NSE_INDEX|Nifty 50")
    contracts = [_as_dict(item) for item in getattr(contracts_resp, "data", []) or []]
    today = datetime.now().date()
    expiries = sorted(
        {
            row.get("expiry").date()
            for row in contracts
            if row.get("expiry") and row.get("expiry").date() >= today
        }
    )
    if not expiries:
        raise RuntimeError("No Nifty option expiries returned by Upstox.")
    target_expiries = [expiry_date.strftime("%Y-%m-%d") for expiry_date in expiries[:2]]

    rows = []
    for expiry in target_expiries:
        response = option_api.get_put_call_option_chain("NSE_INDEX|Nifty 50", expiry)
        for item in getattr(response, "data", []) or []:
            record = _as_dict(item)
            ce = _as_dict(record.get("call_options"))
            pe = _as_dict(record.get("put_options"))
            ce_market = _as_dict(ce.get("market_data"))
            pe_market = _as_dict(pe.get("market_data"))
            call_oi = ce_market.get("oi") or 0
            put_oi = pe_market.get("oi") or 0
            call_prev_oi = ce_market.get("prev_oi") or 0
            put_prev_oi = pe_market.get("prev_oi") or 0
            rows.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "expiry": expiry,
                    "strike": record.get("strike_price"),
                    "underlying_spot": record.get("underlying_spot_price"),
                    "atm_reference": atm_reference,
                    "call_key": ce.get("instrument_key"),
                    "put_key": pe.get("instrument_key"),
                    "call_oi": call_oi,
                    "put_oi": put_oi,
                    "call_prev_oi": call_prev_oi,
                    "put_prev_oi": put_prev_oi,
                    "call_oi_change": call_oi - call_prev_oi,
                    "put_oi_change": put_oi - put_prev_oi,
                    "call_ltp": ce_market.get("ltp"),
                    "put_ltp": pe_market.get("ltp"),
                }
            )

    df = pd.DataFrame(rows).dropna(how="all")
    if not df.empty:
        df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
        df["underlying_spot"] = pd.to_numeric(df["underlying_spot"], errors="coerce")
        spot = float(atm_reference) if atm_reference else float(df["underlying_spot"].dropna().iloc[0]) if df["underlying_spot"].notna().any() else float(df["strike"].median())
        atm = int(round(spot / 50) * 50)
        target_strikes = set(np.arange(atm - 500, atm + 501, 50, dtype=float))
        intraday_frames = []
        for row in df[df["strike"].isin(target_strikes)].itertuples(index=False):
            for side, key_attr in [("CALL", "call_key"), ("PUT", "put_key")]:
                instrument_key = getattr(row, key_attr, None)
                if not instrument_key:
                    continue
                try:
                    candle_resp = history_api.get_intra_day_candle_data(instrument_key, "1minute", "2.0")
                    candles = getattr(getattr(candle_resp, "data", None), "candles", [])
                    candle_df = _option_candles_to_df(candles, row.strike, side, instrument_key, row.expiry)
                    if not candle_df.empty:
                        intraday_frames.append(candle_df)
                except Exception as exc:
                    print(f"Intraday OI fetch failed for {side} {row.strike}: {exc}")

        if intraday_frames:
            intraday_df = pd.concat(intraday_frames, ignore_index=True)
            intraday_df = intraday_df.sort_values(["timestamp", "strike", "side"])
            save_parquet(intraday_df, data_dir / "options" / "latest_nifty_oi_intraday.parquet")

    if not df.empty:
        save_parquet(df, data_dir / "options" / "latest_nifty_oi.parquet")
    return df
