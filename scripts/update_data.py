from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis import build_dashboard_payload
from src.config import get_settings
from src.fetch_market import fetch_nifty100_stocks, fetch_nifty_index
from src.fetch_options import fetch_latest_nifty_oi
from src.storage import ensure_data_dirs, save_dashboard_payload


def main() -> None:
    settings = get_settings()
    ensure_data_dirs(settings.data_dir)

    print("Fetching Nifty index data...")
    nifty = fetch_nifty_index(settings.nifty_symbol, settings.data_dir, settings.upstox_access_token)

    print("Fetching Nifty 100 constituent data...")
    stocks = fetch_nifty100_stocks(settings.data_dir, settings.upstox_access_token)

    if settings.upstox_access_token:
        print("Fetching optional Upstox latest Nifty OI snapshot...")
        try:
            oi = fetch_latest_nifty_oi(
                settings.upstox_access_token,
                settings.data_dir,
                float(nifty.sort_values("date")["close"].iloc[-1]),
            )
            print(f"Saved OI rows: {len(oi)}")
        except Exception as exc:
            print(f"OI fetch skipped: {exc}")
    else:
        print("UPSTOX_ACCESS_TOKEN not set. Skipping OI fetch.")

    print("Building dashboard payload...")
    payload = build_dashboard_payload(nifty, stocks, settings.data_dir)
    output_path = save_dashboard_payload(payload, settings.data_dir)
    print(f"Done. Wrote {output_path}")


if __name__ == "__main__":
    main()
