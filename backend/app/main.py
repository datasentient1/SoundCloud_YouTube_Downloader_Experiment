from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .downloader import create_job, get_job, list_jobs
from .schemas import DownloadInput

app = FastAPI(title="Playlist MP3 Downloader")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_origin, "http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/downloads")
def start_download(payload: DownloadInput) -> dict:
    try:
        return create_job(str(payload.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/downloads")
def downloads() -> list[dict]:
    return list_jobs()


@app.get("/api/downloads/{job_id}")
def download_status(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found.")
    return job


@app.get("/api/downloads/{job_id}/log")
def download_log(job_id: str) -> PlainTextResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found.")

    log_path = settings.downloads_dir / job_id / "downloader.log"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log is not available yet.")

    return PlainTextResponse(log_path.read_text(encoding="utf-8", errors="replace"))


@app.get("/api/downloads/{job_id}/archive")
def download_archive(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found.")
    if job["status"] != "complete" or not job.get("archive_path"):
        raise HTTPException(status_code=409, detail="Archive is not ready yet.")

    archive = Path(job["archive_path"])
    if not archive.exists():
        raise HTTPException(status_code=410, detail="Archive has expired.")
    return FileResponse(archive, filename=f"catalog-{job_id}.zip", media_type="application/zip")


static_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
