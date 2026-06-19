import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd


def ensure_data_dirs(data_dir: Path) -> None:
    for child in ["raw", "options", "processed"]:
        (data_dir / child).mkdir(parents=True, exist_ok=True)


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def save_dashboard_payload(payload: dict[str, Any], data_dir: Path) -> Path:
    path = data_dir / "processed" / "dashboard_payload.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    return path


def load_dashboard_payload(data_dir: Path) -> Optional[dict[str, Any]]:
    path = data_dir / "processed" / "dashboard_payload.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")
