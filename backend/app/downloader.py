import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "soundcloud.com",
    "www.soundcloud.com",
}

SOURCE_HOSTS = {
    "youtube": {"youtube.com", "www.youtube.com", "music.youtube.com", "youtu.be"},
    "soundcloud": {"soundcloud.com", "www.soundcloud.com"},
}

_semaphore: threading.Semaphore | None = None


def infer_source(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_HOSTS:
        raise ValueError("Only YouTube and SoundCloud URLs are supported.")
    for source, hosts in SOURCE_HOSTS.items():
        if host in hosts:
            return source
    raise ValueError("Unsupported source.")


def create_job(user_id: int, url: str) -> dict:
    from .db import connect, now_iso

    source = infer_source(url)
    job_id = uuid.uuid4().hex
    timestamp = now_iso()
    with connect() as db:
        db.execute(
            """
            INSERT INTO jobs (id, user_id, source, url, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, user_id, source, url, "queued", timestamp, timestamp),
        )
        job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()
    return job


def get_job(job_id: str, user_id: int) -> dict | None:
    from .db import connect

    with connect() as db:
        return db.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id),
        ).fetchone()


def list_jobs(user_id: int) -> list[dict]:
    from .db import connect

    with connect() as db:
        return db.execute(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 25",
            (user_id,),
        ).fetchall()


def update_job(job_id: str, **fields: str | None) -> None:
    from .db import connect, now_iso

    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(job_id)
    with connect() as db:
        db.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)


def command_for(source: str, url: str, output_dir: Path) -> list[str]:
    if source == "soundcloud":
        return [
            "scdl",
            "-l",
            url,
            "--path",
            str(output_dir),
            "--onlymp3",
            "-c",
            "--hidewarnings",
        ]

    return [
        "yt-dlp",
        "--yes-playlist",
        "--ignore-errors",
        "--no-overwrites",
        "--restrict-filenames",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--embed-metadata",
        "--embed-thumbnail",
        "--paths",
        str(output_dir),
        "-o",
        "%(playlist_index|00)s-%(title).180B.%(ext)s",
        url,
    ]


def run_job(job_id: str) -> None:
    from .config import get_settings
    from .db import connect

    global _semaphore
    settings = get_settings()
    if _semaphore is None:
        _semaphore = threading.Semaphore(settings.max_concurrent_jobs)

    with connect() as db:
        job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        return

    job_dir = settings.downloads_dir / job_id
    media_dir = job_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    with _semaphore:
        update_job(job_id, status="running", progress="Starting download...")
        try:
            process = subprocess.Popen(
                command_for(job["source"], job["url"], media_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                cleaned = line.strip()
                if cleaned:
                    update_job(job_id, progress=cleaned[-500:])

            return_code = process.wait()
            if return_code != 0:
                raise RuntimeError(f"Downloader exited with code {return_code}.")

            archive_base = job_dir / "catalog"
            archive_path = Path(shutil.make_archive(str(archive_base), "zip", media_dir))
            update_job(
                job_id,
                status="complete",
                progress="Archive ready.",
                archive_path=str(archive_path),
                error=None,
            )
        except Exception as exc:
            update_job(job_id, status="failed", error=str(exc), progress="Download failed.")
