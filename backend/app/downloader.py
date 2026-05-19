import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

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

AUDIO_SUFFIXES = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}

TRANSIENT_SUFFIXES = {
    ".aria2",
    ".description",
    ".part",
    ".temp",
    ".tmp",
    ".url",
    ".webloc",
    ".ytdl",
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


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if host in SOURCE_HOSTS["soundcloud"]:
        query = parse_qs(parsed.query)
        playlist_context = query.get("in", [""])[0].strip("/")
        if "/sets/" in playlist_context:
            return f"https://soundcloud.com/{playlist_context}"
        if "/sets/" not in parsed.path:
            raise ValueError("Paste a SoundCloud playlist URL, such as https://soundcloud.com/artist/sets/playlist.")
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))

    if host in SOURCE_HOSTS["youtube"]:
        query = parse_qs(parsed.query)
        kept_query = {
            key: values[0]
            for key, values in query.items()
            if key in {"list", "v"} and values
        }
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                "",
                urlencode(kept_query),
                "",
            )
        )

    return url


def create_job(url: str) -> dict:
    from .db import connect, now_iso

    url = normalize_url(url)
    source = infer_source(url)
    job_id = uuid.uuid4().hex
    timestamp = now_iso()
    with connect() as db:
        db.execute(
            """
            INSERT INTO jobs (id, source, url, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, source, url, "queued", timestamp, timestamp),
        )
        job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()
    return job


def get_job(job_id: str) -> dict | None:
    from .db import connect

    with connect() as db:
        return db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()


def list_jobs() -> list[dict]:
    from .db import connect

    with connect() as db:
        return db.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 25",
        ).fetchall()


def update_job(job_id: str, **fields: str | None) -> None:
    from .db import connect, now_iso

    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(job_id)
    with connect() as db:
        db.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)


def youtube_extra_args(job_dir: Path) -> list[str]:
    """Return optional yt-dlp network/auth arguments from deployment settings.

    Public YouTube URLs usually work without cookies. Some hosting providers' IP
    ranges are challenged by YouTube, though. In that case, the operator can set
    either APP_YTDLP_COOKIES_PATH or APP_YTDLP_COOKIES. The latter is written to
    a per-job file so the cookie contents are never exposed in the command line.
    """
    from .config import get_settings

    settings = get_settings()
    args = []

    if settings.ytdlp_impersonate:
        args.extend(["--impersonate", settings.ytdlp_impersonate])

    if settings.ytdlp_cookies_path:
        cookie_path = Path(settings.ytdlp_cookies_path)
        if cookie_path.exists():
            args.extend(["--cookies", str(cookie_path)])
            return args

    if settings.ytdlp_cookies:
        cookie_path = job_dir / "youtube.cookies.txt"
        cookie_path.write_text(settings.ytdlp_cookies, encoding="utf-8")
        os.chmod(cookie_path, 0o600)
        args.extend(["--cookies", str(cookie_path)])
        return args

    return args


def command_for(source: str, url: str, output_dir: Path, job_dir: Path | None = None) -> list[str]:
    if source == "soundcloud":
        return [
            "scdl",
            "-l",
            url,
            "--path",
            str(output_dir),
            "--onlymp3",
            "--force-metadata",
            "--addtofile",
            "--playlist-name-format",
            "{user[username]} - {title}",
            "--name-format",
            "{user[username]} - {title}",
            "--hidewarnings",
        ]

    extra_args = youtube_extra_args(job_dir or output_dir.parent)
    return [
        "yt-dlp",
        "--newline",
        "--yes-playlist",
        "--no-abort-on-error",
        "--no-overwrites",
        "--restrict-filenames",
        "--format",
        "bestaudio/best",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--prefer-ffmpeg",
        "--convert-thumbnails",
        "jpg",
        "--embed-thumbnail",
        "--embed-metadata",
        "--parse-metadata",
        "%(uploader|)s:%(meta_artist)s",
        "--parse-metadata",
        "%(title)s:%(meta_title)s",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--extractor-retries",
        "3",
        "--socket-timeout",
        "30",
        "--paths",
        str(output_dir),
        "-o",
        "%(artist,uploader,channel|Unknown Artist).120B - %(title).180B.%(ext)s",
        *extra_args,
        url,
    ]


def media_files(media_dir: Path) -> list[Path]:
    return [
        path
        for path in media_dir.rglob("*")
        if path.is_file()
        and path.name != ".DS_Store"
        and path.suffix.lower() not in TRANSIENT_SUFFIXES
    ]


def audio_files(media_dir: Path) -> list[Path]:
    return [path for path in media_files(media_dir) if path.suffix.lower() in AUDIO_SUFFIXES]


def archive_media(job_id: str, job_dir: Path, media_dir: Path, progress: str) -> None:
    archive_base = job_dir / "catalog"
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", media_dir))
    update_job(
        job_id,
        status="complete",
        progress=progress,
        archive_path=str(archive_path),
        error=None,
    )


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
    log_path = job_dir / "downloader.log"

    with _semaphore:
        update_job(job_id, status="running", progress="Starting download...")
        try:
            last_line = ""
            command = command_for(job["source"], job["url"], media_dir, job_dir)
            with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    cleaned = line.strip()
                    log_file.write(line)
                    log_file.flush()
                    if cleaned:
                        last_line = cleaned[-500:]
                        update_job(job_id, progress=cleaned[-500:])

                return_code = process.wait()

            downloaded_audio = audio_files(media_dir)
            if downloaded_audio:
                if return_code == 0:
                    archive_media(job_id, job_dir, media_dir, "Archive ready.")
                    return

                archive_media(
                    job_id,
                    job_dir,
                    media_dir,
                    f"Archive ready with warnings. Downloader exited with code {return_code}: {last_line}",
                )
                return

            detail = f": {last_line}" if last_line else f". See {log_path}."
            if return_code != 0:
                raise RuntimeError(f"Downloader exited with code {return_code}{detail}")

            raise RuntimeError(
                "Downloader finished but produced no audio files. "
                "For YouTube, this commonly means the host IP was challenged, the playlist is unavailable, "
                "or post-processing failed before an MP3 was written."
            )
        except Exception as exc:
            update_job(job_id, status="failed", error=str(exc), progress="Download failed.")
