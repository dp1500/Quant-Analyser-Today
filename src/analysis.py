from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller


WINDOWS = {
    "1Y": 252,
    "6M": 126,
    "3M": 63,
    "1M": 21,
    "1W": 5,
}

MOMENTUM_WINDOWS = {
    "6M": 126,
    "3M": 63,
    "15D": 15,
}


def _records(df: pd.DataFrame, cols: list[str]) -> list[dict[str, Any]]:
    out = df[cols].replace({np.nan: None}).to_dict(orient="records")
    return out


def ath_atl(nifty: pd.DataFrame) -> dict[str, Any]:
    df = nifty.copy()
    one_month = df.tail(21)
    return {
        "one_year": {
            "ath": round(float(df["high"].max()), 2),
            "atl": round(float(df["low"].min()), 2),
        },
        "one_month": {
            "ath": round(float(one_month["high"].max()), 2),
            "atl": round(float(one_month["low"].min()), 2),
        },
    }


def _hurst_exponent(series: pd.Series) -> float:
    values = np.asarray(series.dropna(), dtype=float)
    if len(values) < 30:
        return 0.5
    lags = range(2, min(20, len(values) // 2))
    tau = [np.std(values[lag:] - values[:-lag]) for lag in lags]
    tau = np.asarray([x for x in tau if x > 0])
    if len(tau) < 4:
        return 0.5
    poly = np.polyfit(np.log(list(lags)[: len(tau)]), np.log(tau), 1)
    return float(max(0.0, min(1.0, poly[0])))


def _variance_ratio(log_prices: pd.Series, lag: int = 5) -> float:
    returns = log_prices.diff().dropna()
    if len(returns) < lag * 3:
        return 1.0
    one_period_var = returns.var()
    multi_period_var = log_prices.diff(lag).dropna().var() / lag
    if not one_period_var or pd.isna(one_period_var):
        return 1.0
    return float(multi_period_var / one_period_var)


def _adf_pvalue(log_prices: pd.Series) -> float:
    if len(log_prices.dropna()) < 30:
        return 1.0
    try:
        return float(adfuller(log_prices.dropna(), autolag="AIC")[1])
    except Exception:
        return 1.0


def _trend_stats(log_prices: pd.Series) -> dict[str, float]:
    y = np.asarray(log_prices.dropna(), dtype=float)
    if len(y) < 5:
        return {"slope": 0.0, "t_stat": 0.0, "r2": 0.0}
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    resid = y - fitted
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2)) or 1.0
    r2 = max(0.0, 1 - ss_res / ss_tot)
    denom = np.sqrt(ss_res / max(len(y) - 2, 1)) / np.sqrt(np.sum((x - x.mean()) ** 2))
    t_stat = float(slope / denom) if denom else 0.0
    return {"slope": float(slope), "t_stat": t_stat, "r2": float(r2)}


def _regime_for_window(df: pd.DataFrame) -> dict[str, Any]:
    returns = df["close"].pct_change().dropna()
    if len(returns) < 4:
        return {"label": "Insufficient data", "score": 0, "autocorr": None, "trend_strength": None}

    close = df["close"].astype(float)
    log_price = np.log(close)
    autocorr = returns.autocorr(lag=1)
    hurst = _hurst_exponent(log_price)
    variance_ratio = _variance_ratio(log_price, lag=min(5, max(2, len(df) // 4)))
    adf_p = _adf_pvalue(log_price)
    trend = _trend_stats(log_price)
    ret_pct = float((close.iloc[-1] / close.iloc[0] - 1) * 100)
    realized_vol = float(returns.std() * sqrt(252) * 100)
    ma = close.rolling(min(20, len(close))).mean().iloc[-1]
    extension_pct = float((close.iloc[-1] / ma - 1) * 100) if ma else 0.0

    momentum_score = (
        (0.35 * np.tanh(trend["t_stat"] / 3))
        + (0.25 * np.tanh(ret_pct / 8))
        + (0.20 * np.tanh((hurst - 0.5) * 6))
        + (0.20 * np.tanh((variance_ratio - 1) * 2))
    )
    reversion_score = (
        (0.35 * np.tanh(((0.5 - hurst) * 6)))
        + (0.25 * np.tanh((1 - variance_ratio) * 2))
        + (0.20 * (1 - min(adf_p, 1.0)))
        + (0.20 * np.tanh(abs(extension_pct) / 4))
    )

    if len(df) <= 7:
        if abs(ret_pct) >= 1.2 or abs(trend["t_stat"]) >= 1.4:
            label = "Bullish momentum" if ret_pct > 0 else "Bearish momentum"
        else:
            label = "Short-window chop"
    elif momentum_score > reversion_score and abs(trend["t_stat"]) >= 1.2:
        label = "Bullish momentum" if trend["slope"] > 0 else "Bearish momentum"
    elif reversion_score > momentum_score and (hurst < 0.48 or variance_ratio < 0.9 or adf_p < 0.1):
        label = "Mean reverting"
    else:
        label = "Mixed / choppy"

    return {
        "label": label,
        "score": round(float(momentum_score - reversion_score), 3),
        "momentum_score": round(float(momentum_score), 3),
        "reversion_score": round(float(reversion_score), 3),
        "autocorr": round(float(autocorr), 3) if pd.notna(autocorr) else None,
        "hurst": round(float(hurst), 3),
        "variance_ratio": round(float(variance_ratio), 3),
        "adf_pvalue": round(float(adf_p), 3),
        "trend_tstat": round(float(trend["t_stat"]), 2),
        "trend_strength": round(float(trend["r2"]), 3),
        "return_pct": round(ret_pct, 2),
        "realized_vol_pct": round(realized_vol, 2),
    }


def regime_summary(nifty: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for label, lookback in WINDOWS.items():
        window_df = nifty.tail(min(lookback, len(nifty)))
        row = {"window": label}
        row.update(_regime_for_window(window_df))
        rows.append(row)
    return rows


def forecast_ranges(nifty: pd.DataFrame) -> dict[str, Any]:
    df = nifty.copy()
    returns = np.log(df["close"]).diff().dropna()
    recent = df.tail(5)
    last_close = float(df["close"].iloc[-1])

    if len(returns) >= 20:
        ewma_var = returns.pow(2).ewm(span=20, adjust=False).mean().iloc[-1]
    else:
        ewma_var = returns.var()
    daily_sigma = float(np.sqrt(max(ewma_var, 1e-8)))

    forecasts = []
    cursor = pd.to_datetime(df["date"].iloc[-1])
    for step in range(1, 6):
        cursor = cursor + pd.offsets.BDay(1)
        width = 1.65 * daily_sigma * sqrt(step)
        forecasts.append(
            {
                "date": cursor.strftime("%Y-%m-%d"),
                "mid": round(last_close, 2),
                "low": round(last_close * np.exp(-width), 2),
                "high": round(last_close * np.exp(width), 2),
                "model": "EWMA volatility range",
            }
        )

    return {
        "history": _records(recent, ["date", "open", "high", "low", "close"]),
        "forecast": forecasts,
        "daily_vol_pct": round(daily_sigma * 100, 2),
    }


def stock_breadth(stocks: pd.DataFrame) -> dict[str, Any]:
    latest_rows = []
    for symbol, sdf in stocks.sort_values("date").groupby("symbol"):
        if len(sdf) < 20:
            continue
        close = sdf["close"].astype(float)
        latest_rows.append(
            {
                "symbol": symbol.replace(".NS", ""),
                "close": round(float(close.iloc[-1]), 2),
                "return_5d": round(float((close.iloc[-1] / close.iloc[-6] - 1) * 100), 2) if len(close) >= 6 else None,
                "return_20d": round(float((close.iloc[-1] / close.iloc[-21] - 1) * 100), 2) if len(close) >= 21 else None,
                "above_20dma": bool(close.iloc[-1] > close.rolling(20).mean().iloc[-1]),
                "vol_20d": round(float(close.pct_change().tail(20).std() * sqrt(252) * 100), 2),
            }
        )

    table = pd.DataFrame(latest_rows)
    if table.empty:
        return {"summary": {}, "leaders": [], "laggards": [], "table": []}

    summary = {
        "stocks_loaded": int(len(table)),
        "above_20dma_pct": round(float(table["above_20dma"].mean() * 100), 1),
        "median_5d_return": round(float(table["return_5d"].median()), 2),
        "median_20d_return": round(float(table["return_20d"].median()), 2),
    }
    leaders = table.sort_values("return_5d", ascending=False).head(8).to_dict(orient="records")
    laggards = table.sort_values("return_5d", ascending=True).head(8).to_dict(orient="records")
    return {"summary": summary, "leaders": leaders, "laggards": laggards, "table": table.to_dict(orient="records")}


def _stock_window_signal(sdf: pd.DataFrame, lookback: int) -> dict[str, Any]:
    window = sdf.tail(min(lookback, len(sdf))).copy()
    if len(window) < min(lookback, 30) and lookback > 30:
        return {"valid": False}
    regime = _regime_for_window(window)
    close = window["close"].astype(float)
    mean = close.rolling(min(50, len(close))).mean().iloc[-1]
    std = close.rolling(min(50, len(close))).std().iloc[-1]
    zscore = float((close.iloc[-1] - mean) / std) if std and pd.notna(std) else 0.0
    regime.update({"valid": True, "zscore": round(zscore, 2)})
    return regime


def stock_quant_scanner(stocks: pd.DataFrame) -> dict[str, Any]:
    rows = []
    for symbol, sdf in stocks.sort_values("date").groupby("symbol"):
        if len(sdf) < 60:
            continue
        close = sdf["close"].astype(float)
        mean_windows = {label: _stock_window_signal(sdf, lookback) for label, lookback in {"1Y": 252, "6M": 126, "1M": 21}.items()}
        mom_windows = {label: _stock_window_signal(sdf, lookback) for label, lookback in MOMENTUM_WINDOWS.items()}
        latest = float(close.iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])

        mean_hits = sum(1 for item in mean_windows.values() if item.get("label") == "Mean reverting")
        avg_z = float(np.nanmean([item.get("zscore", 0.0) for item in mean_windows.values()]))
        mean_tip = "Long reversion" if avg_z <= -0.6 else "Short reversion" if avg_z >= 0.6 else "Wait for edge"
        mean_score = float(np.nanmean([item.get("reversion_score", 0.0) for item in mean_windows.values()]))

        bullish_hits = sum(1 for item in mom_windows.values() if item.get("label") == "Bullish momentum")
        bearish_hits = sum(1 for item in mom_windows.values() if item.get("label") == "Bearish momentum")
        mom_score = float(np.nanmean([item.get("momentum_score", 0.0) for item in mom_windows.values()]))
        mom_tip = "Bullish continuation" if bullish_hits >= 2 and latest > ma20 > ma50 else "Short continuation" if bearish_hits >= 2 and latest < ma20 < ma50 else "No clean momentum"

        rows.append(
            {
                "symbol": symbol,
                "close": round(latest, 2),
                "mean_windows": mean_windows,
                "momentum_windows": mom_windows,
                "mean_hits": int(mean_hits),
                "mean_score": round(mean_score, 3),
                "mean_zscore": round(avg_z, 2),
                "mean_tip": mean_tip,
                "momentum_score": round(mom_score, 3),
                "bullish_hits": int(bullish_hits),
                "bearish_hits": int(bearish_hits),
                "momentum_tip": mom_tip,
                "return_15d": round(float((close.iloc[-1] / close.iloc[-16] - 1) * 100), 2) if len(close) >= 16 else None,
                "return_3m": round(float((close.iloc[-1] / close.iloc[-64] - 1) * 100), 2) if len(close) >= 64 else None,
                "return_6m": round(float((close.iloc[-1] / close.iloc[-127] - 1) * 100), 2) if len(close) >= 127 else None,
            }
        )

    table = pd.DataFrame(rows)
    if table.empty:
        return {"mean_reversion": [], "momentum": [], "summary": {"scanned": 0}}

    mean_reversion = table[
        (table["mean_hits"] >= 2)
        & (table["mean_tip"].isin(["Long reversion", "Short reversion"]))
    ].sort_values(["mean_hits", "mean_score"], ascending=False).head(15)

    momentum = table[
        table["momentum_tip"].isin(["Bullish continuation", "Short continuation"])
    ].sort_values(["bullish_hits", "bearish_hits", "momentum_score"], ascending=False).head(15)

    return {
        "summary": {
            "scanned": int(len(table)),
            "mean_reversion_count": int(len(mean_reversion)),
            "momentum_count": int(len(momentum)),
        },
        "mean_reversion": mean_reversion.replace({np.nan: None}).to_dict(orient="records"),
        "momentum": momentum.replace({np.nan: None}).to_dict(orient="records"),
    }


def option_oi_summary(options_path: Path) -> dict[str, Any]:
    intraday_path = options_path.parent / "latest_nifty_oi_intraday.parquet"
    if not options_path.exists():
        return {"available": False, "message": "No Upstox OI artifact saved yet.", "expiries": []}

    df = pd.read_parquet(options_path)
    if df.empty:
        return {"available": False, "message": "Upstox OI artifact is empty.", "expiries": []}

    numeric_cols = ["strike", "underlying_spot", "atm_reference", "call_oi", "put_oi", "call_oi_change", "put_oi_change"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["call_oi"] = df.get("call_oi", 0).fillna(0)
    df["put_oi"] = df.get("put_oi", 0).fillna(0)
    df["total_oi"] = df["call_oi"] + df["put_oi"]
    df["total_oi_change"] = df.get("call_oi_change", 0).fillna(0) + df.get("put_oi_change", 0).fillna(0)

    expiries = []
    for expiry, expiry_df in df.sort_values(["expiry", "strike"]).groupby("expiry"):
        reference = expiry_df["atm_reference"].dropna()
        spot = expiry_df["underlying_spot"].dropna()
        last_spot = float(reference.iloc[0]) if not reference.empty else float(spot.iloc[0]) if not spot.empty else float(expiry_df["strike"].median())
        atm = round(last_spot / 50) * 50
        strike_band = set(np.arange(atm - 500, atm + 501, 50, dtype=float))
        profile = expiry_df[expiry_df["strike"].isin(strike_band)].copy().sort_values("strike")
        levels = profile[["strike", "call_oi", "put_oi", "call_oi_change", "put_oi_change"]].replace({np.nan: None})
        expiries.append(
            {
                "expiry": str(expiry)[:10],
                "spot": round(last_spot, 2),
                "atm": int(atm),
                "levels": levels.to_dict(orient="records"),
                "changes": option_oi_change_summary(expiry_df, intraday_path, str(expiry)[:10]),
            }
        )

    return {
        "available": True,
        "message": "Nearest two Nifty expiries, ±10 strikes from latest Nifty close.",
        "expiries": expiries,
    }


def option_oi_change_summary(snapshot: pd.DataFrame, intraday_path: Path, expiry: str) -> dict[str, list[dict[str, Any]]]:
    if intraday_path.exists():
        intraday = pd.read_parquet(intraday_path)
        if not intraday.empty:
            intraday["timestamp"] = pd.to_datetime(intraday["timestamp"])
            intraday["oi"] = pd.to_numeric(intraday["oi"], errors="coerce")
            intraday["strike"] = pd.to_numeric(intraday["strike"], errors="coerce")
            if "expiry" in intraday.columns:
                intraday = intraday[intraday["expiry"].astype(str).str[:10] == expiry].copy()
            if intraday.empty:
                return {"30m": [], "1h": [], "2h": [], "day": []}
            latest_time = intraday["timestamp"].max()
            windows = {"30m": 30, "1h": 60, "2h": 120, "day": None}
            result = {}
            for label, minutes in windows.items():
                if minutes is None:
                    window_df = intraday.copy()
                else:
                    window_df = intraday[intraday["timestamp"] >= latest_time - pd.Timedelta(minutes=minutes)].copy()
                if window_df.empty:
                    result[label] = []
                    continue
                first = window_df.sort_values("timestamp").groupby(["strike", "side"], as_index=False).first()
                last = window_df.sort_values("timestamp").groupby(["strike", "side"], as_index=False).last()
                merged = last.merge(first[["strike", "side", "oi"]], on=["strike", "side"], suffixes=("", "_start"))
                merged["oi_change"] = merged["oi"] - merged["oi_start"]
                merged["oi_change_pct"] = np.where(merged["oi_start"] > 0, merged["oi_change"] / merged["oi_start"] * 100, None)
                top = merged.reindex(merged["oi_change"].abs().sort_values(ascending=False).index).head(8)
                result[label] = top[["strike", "side", "oi", "oi_change", "oi_change_pct"]].replace({np.nan: None}).to_dict(orient="records")
            return result

    rows = []
    for row in snapshot.itertuples(index=False):
        rows.append({"strike": row.strike, "side": "CALL", "oi": row.call_oi, "oi_change": row.call_oi_change, "oi_change_pct": None})
        rows.append({"strike": row.strike, "side": "PUT", "oi": row.put_oi, "oi_change": row.put_oi_change, "oi_change_pct": None})
    fallback = pd.DataFrame(rows)
    if fallback.empty:
        return {"30m": [], "1h": [], "2h": [], "day": []}
    top = fallback.reindex(fallback["oi_change"].abs().sort_values(ascending=False).index).head(8)
    return {"30m": [], "1h": [], "2h": [], "day": top.replace({np.nan: None}).to_dict(orient="records")}


def build_dashboard_payload(nifty: pd.DataFrame, stocks: pd.DataFrame, data_dir: Path) -> dict[str, Any]:
    nifty = nifty.sort_values("date").copy()
    stocks = stocks.sort_values(["symbol", "date"]).copy()
    analysis_till = pd.to_datetime(nifty["date"].iloc[-1])
    analysis_for = analysis_till + pd.offsets.BDay(1)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "local_post_market_compute",
        "analysis_till": analysis_till.strftime("%Y-%m-%d"),
        "analysis_for": analysis_for.strftime("%Y-%m-%d"),
        "nifty": {
            "ohlc": _records(nifty, ["date", "open", "high", "low", "close", "volume"]),
            "levels": ath_atl(nifty),
            "regimes": regime_summary(nifty),
            "forecast": forecast_ranges(nifty),
        },
        "stocks": {
            "breadth": stock_breadth(stocks),
            "scanner": stock_quant_scanner(stocks),
        },
        "options": option_oi_summary(data_dir / "options" / "latest_nifty_oi.parquet"),
    }
