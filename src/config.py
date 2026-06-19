from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    nifty_symbol: str
    upstox_access_token: str


def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.getenv("DATA_DIR", "data")),
        nifty_symbol=os.getenv("NIFTY_SYMBOL", "^NSEI"),
        upstox_access_token=os.getenv("UPSTOX_ACCESS_TOKEN", "").strip(),
    )
