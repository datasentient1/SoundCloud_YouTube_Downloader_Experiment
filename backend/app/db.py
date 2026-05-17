import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import get_settings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict:
    fields = [column[0] for column in cursor.description]
    return {key: row[index] for index, key in enumerate(fields)}


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path: Path = get_settings().database_path
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = dict_factory
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with connect() as db:
        db.execute("PRAGMA foreign_keys = OFF")
        existing_jobs = db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
        ).fetchone()

        if existing_jobs:
            columns = [
                row["name"]
                for row in db.execute("PRAGMA table_info(jobs)").fetchall()
            ]
            if "user_id" in columns:
                db.executescript(
                    """
                    ALTER TABLE jobs RENAME TO jobs_legacy;
                    CREATE TABLE jobs (
                        id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        url TEXT NOT NULL,
                        status TEXT NOT NULL,
                        progress TEXT NOT NULL DEFAULT '',
                        error TEXT,
                        archive_path TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    INSERT INTO jobs (id, source, url, status, progress, error, archive_path, created_at, updated_at)
                    SELECT id, source, url, status, progress, error, archive_path, created_at, updated_at
                    FROM jobs_legacy;
                    DROP TABLE jobs_legacy;
                    """
                )

        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                progress TEXT NOT NULL DEFAULT '',
                error TEXT,
                archive_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            DROP TABLE IF EXISTS users;
            """
        )
        db.execute("PRAGMA foreign_keys = ON")
