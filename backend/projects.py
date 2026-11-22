from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .storage import connect, get_data_dir, row_to_dict, write_project_config


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_projects() -> list[dict]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC, name COLLATE NOCASE"
        ).fetchall()
    return [dict(row) for row in rows]


def create_project(
    name: str,
    source_language: str = "English",
    target_language: str = "Myanmar",
    typesetting_style: str = "original_bubble",
    font_family: str = "Noto Sans Myanmar",
    source_url: str = "",
) -> dict:
    project_id = str(uuid4())
    now = utc_now()
    project_dir = get_data_dir() / "projects" / project_id
    project = {
        "id": project_id,
        "name": name.strip(),
        "source_language": source_language,
        "target_language": target_language,
        "typesetting_style": typesetting_style,
        "font_family": font_family,
        "source_url": source_url.strip(),
        "storage_path": str(project_dir),
        "created_at": now,
        "updated_at": now,
    }
    project_dir.mkdir(parents=True, exist_ok=False)
    try:
        with connect() as db:
            db.execute("""
                INSERT INTO projects (
                    id, name, source_language, target_language,
                    typesetting_style, font_family, source_url,
                    storage_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, tuple(project[key] for key in (
                "id", "name", "source_language", "target_language",
                "typesetting_style", "font_family", "source_url",
                "storage_path", "created_at", "updated_at"
            )))
        write_project_config(project_dir, project)
    except Exception:
        # Keep failed creation from leaving an orphaned project directory.
        import shutil
        shutil.rmtree(project_dir, ignore_errors=True)
        raise
    return project


def get_project(project_id: str) -> dict | None:
    with connect() as db:
        row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row_to_dict(row)
