from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def get_data_dir() -> Path:
    override = os.getenv("COMIC_TRANSLATOR_DATA_DIR")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ComicTranslator"
    else:
        root = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "comic-translator"
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects").mkdir(exist_ok=True)
    (root / "cache").mkdir(exist_ok=True)
    return root


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(get_data_dir() / "comic_translator.sqlite3", timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA busy_timeout = 20000")
    return db


def initialize_database() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_language TEXT NOT NULL DEFAULT 'English',
            target_language TEXT NOT NULL DEFAULT 'Myanmar',
            typesetting_style TEXT NOT NULL DEFAULT 'original_bubble',
            font_family TEXT NOT NULL DEFAULT 'Noto Sans Myanmar',
            source_url TEXT NOT NULL DEFAULT '',
            storage_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chapters (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            chapter_number TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(project_id, chapter_number)
        );
        CREATE TABLE IF NOT EXISTS pages (
            id TEXT PRIMARY KEY,
            chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            page_index INTEGER NOT NULL,
            original_path TEXT NOT NULL,
            cleaned_path TEXT NOT NULL DEFAULT '',
            rendered_path TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            UNIQUE(chapter_id, page_index)
        );
        CREATE TABLE IF NOT EXISTS text_regions (
            id TEXT PRIMARY KEY,
            page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            region_index INTEGER NOT NULL,
            x REAL NOT NULL,
            y REAL NOT NULL,
            width REAL NOT NULL,
            height REAL NOT NULL,
            source_text TEXT NOT NULL DEFAULT '',
            translated_text TEXT NOT NULL DEFAULT '',
            confidence REAL,
            status TEXT NOT NULL DEFAULT 'detected',
            UNIQUE(page_id, region_index)
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            chapter_id TEXT REFERENCES chapters(id) ON DELETE SET NULL,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            stage TEXT NOT NULL DEFAULT 'queued',
            progress REAL NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chapters_project ON chapters(project_id);
        CREATE INDEX IF NOT EXISTS idx_pages_chapter ON pages(chapter_id);
        CREATE INDEX IF NOT EXISTS idx_regions_page ON text_regions(page_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def write_project_config(project_dir: Path, project: dict[str, Any]) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "project_id": project["id"],
        "name": project["name"],
        "source_language": project["source_language"],
        "target_language": project["target_language"],
        "typesetting": {
            "style": project["typesetting_style"],
            "font_family": project["font_family"],
            "alignment": "center",
            "auto_fit": True
        },
        "translation": {
            "primary_model": "gemini-3.1-flash-lite",
            "fallback_model": "gemini-3.5-flash-lite"
        }
    }
    (project_dir / "project.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for folder in ("source", "cleaned", "rendered", "exports"):
        (project_dir / folder).mkdir(exist_ok=True)
