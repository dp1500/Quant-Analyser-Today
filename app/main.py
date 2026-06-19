from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import get_settings
from src.storage import load_dashboard_payload


settings = get_settings()
BASE_DIR = Path(__file__).resolve().parents[1]
PUBLIC_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Local Nifty Quant Dashboard")
app.mount("/static", StaticFiles(directory=PUBLIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/api/dashboard")
def dashboard():
    payload = load_dashboard_payload(settings.data_dir)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="No processed dashboard data found. Run scripts/update_data.py first.",
        )
    return payload


@app.get("/api/health")
def health():
    return {"ok": True, "data_dir": str(settings.data_dir)}
