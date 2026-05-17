from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import (
    create_access_token,
    current_user,
    get_user_by_email,
    hash_password,
    require_terms,
    verify_password,
)
from .config import get_settings
from .db import connect, init_db, now_iso
from .downloader import create_job, get_job, list_jobs
from .schemas import AuthInput, DownloadInput, TermsInput, TokenOut

app = FastAPI(title="Artist Catalog Downloader")

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


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "termsAccepted": bool(user.get("terms_accepted_at")),
        "termsAcceptedAt": user.get("terms_accepted_at"),
    }


@app.post("/api/auth/register", response_model=TokenOut)
def register(payload: AuthInput) -> dict:
    existing = get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="An account already exists for this email.")

    timestamp = now_iso()
    with connect() as db:
        db.execute(
            """
            INSERT INTO users (email, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (payload.email.lower(), hash_password(payload.password), timestamp),
        )
        user = db.execute("SELECT * FROM users WHERE lower(email) = lower(?)", (payload.email,)).fetchone()

    return {"access_token": create_access_token(user["id"]), "user": public_user(user)}


@app.post("/api/auth/login", response_model=TokenOut)
def login(payload: AuthInput) -> dict:
    user = get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {"access_token": create_access_token(user["id"]), "user": public_user(user)}


@app.get("/api/me")
def me(user: dict = Depends(current_user)) -> dict:
    return public_user(user)


@app.post("/api/terms")
def accept_terms(payload: TermsInput, user: dict = Depends(current_user)) -> dict:
    if not payload.accepted:
        raise HTTPException(status_code=400, detail="Terms must be accepted to continue.")
    with connect() as db:
        db.execute(
            "UPDATE users SET terms_accepted_at = ? WHERE id = ?",
            (now_iso(), user["id"]),
        )
        updated = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return public_user(updated)


@app.post("/api/downloads")
def start_download(payload: DownloadInput, user: dict = Depends(require_terms)) -> dict:
    try:
        return create_job(user["id"], str(payload.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/downloads")
def downloads(user: dict = Depends(require_terms)) -> list[dict]:
    return list_jobs(user["id"])


@app.get("/api/downloads/{job_id}")
def download_status(job_id: str, user: dict = Depends(require_terms)) -> dict:
    job = get_job(job_id, user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found.")
    return job


@app.get("/api/downloads/{job_id}/archive")
def download_archive(job_id: str, user: dict = Depends(require_terms)) -> FileResponse:
    job = get_job(job_id, user["id"])
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
