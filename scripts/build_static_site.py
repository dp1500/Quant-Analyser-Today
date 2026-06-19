from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
STATIC = ROOT / "static"
PAYLOAD = ROOT / "data" / "processed" / "dashboard_payload.json"


def main() -> None:
    if not PAYLOAD.exists():
        raise FileNotFoundError(f"Missing {PAYLOAD}. Run scripts/update_data.py first.")

    STATIC.mkdir(exist_ok=True)
    shutil.copyfile(FRONTEND / "index.html", ROOT / "index.html")
    shutil.copyfile(FRONTEND / "app.js", STATIC / "app.js")
    shutil.copyfile(FRONTEND / "styles.css", STATIC / "styles.css")
    shutil.copyfile(PAYLOAD, ROOT / "dashboard_payload.json")
    (ROOT / ".nojekyll").touch()
    print("Static GitHub Pages site built at repository root.")


if __name__ == "__main__":
    main()
