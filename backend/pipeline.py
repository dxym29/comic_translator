from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .storage import connect, get_data_dir

router = APIRouter(prefix="/api/v1", tags=["pipeline"])
STAGES = ["import", "extract", "remove", "translate", "typeset", "export"]


class StageInput(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    manual: bool = False


class StageEdit(BaseModel):
    output: dict[str, Any]


def _ensure_table() -> None:
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS stage_runs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            chapter_id TEXT, stage TEXT NOT NULL, status TEXT NOT NULL,
            input_json TEXT NOT NULL, output_json TEXT NOT NULL DEFAULT '{}',
            manual INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_stage_project ON stage_runs(project_id, chapter_id, stage)")


def _project(project_id: str) -> dict:
    with connect() as db:
        row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Project not found")
    return dict(row)


def _save(project_id: str, chapter_id: str | None, stage: str, status: str,
          input_data: dict, output_data: dict, manual: bool = False, error: str = "") -> dict:
    now = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{time.time_ns() % 1_000_000_000:09d}Z"
    run_id = str(uuid.uuid4())
    with connect() as db:
        db.execute("""INSERT INTO stage_runs
          (id,project_id,chapter_id,stage,status,input_json,output_json,manual,error,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (run_id, project_id, chapter_id, stage, status,
           json.dumps(input_data, ensure_ascii=False), json.dumps(output_data, ensure_ascii=False),
           int(manual), error, now, now))
    return {"id": run_id, "stage": stage, "status": status, "input": input_data,
            "output": output_data, "manual": manual, "error": error, "updated_at": now}


def _latest(project_id: str, chapter_id: str | None = None) -> list[dict]:
    with connect() as db:
        rows = db.execute("""SELECT s.* FROM stage_runs s
          JOIN (SELECT stage, MAX(created_at) AS newest FROM stage_runs
          WHERE project_id=? AND chapter_id IS ? GROUP BY stage) x
          ON s.stage=x.stage AND s.created_at=x.newest
          WHERE s.project_id=? AND s.chapter_id IS ? ORDER BY s.created_at""",
          (project_id, chapter_id, project_id, chapter_id)).fetchall()
    return [{"id": r["id"], "stage": r["stage"], "status": r["status"],
             "input": json.loads(r["input_json"]), "output": json.loads(r["output_json"]),
             "manual": bool(r["manual"]), "error": r["error"], "updated_at": r["updated_at"]}
            for r in rows]


def _ocr_extract(data: dict, project: dict) -> dict:
    image_path = Path(str(data.get("image_path", ""))).expanduser()
    if not image_path.is_file():
        raise ValueError("extract stage requires a valid image_path")
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is not installed. Install backend/requirements-ocr-cpu.txt first.") from exc
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not read the image for OCR.")
    from .ocr import model_label, recognize_image
    language = data.get("language") or project.get("source_language") or "English"
    regions = recognize_image(image, language=language)
    return {
        "model": model_label(language),
        "image_path": str(image_path),
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "regions": regions,
        "count": len(regions),
        "note": "PP-OCR text-line boxes; review and edit before removing text."
    }

def _gemini_translate(data: dict, project: dict) -> dict:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("Set GEMINI_API_KEY in the local environment before translation")
    items = data.get("regions")
    if not isinstance(items, list) or not items:
        raise ValueError("translate stage requires a non-empty regions array")
    source = project["source_language"]
    target = project["target_language"]
    prompt = ("Translate the following comic dialogue from " + source + " to " + target +
              ". Preserve region IDs and return ONLY JSON {translations:[{id,text}]}. "
              "Keep character names consistent and concise for speech bubbles.\n" +
              json.dumps(items, ensure_ascii=False))
    models = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
    attempts = []
    for model in models:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}},
            timeout=120)
        if response.ok:
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text)
            return {"model": model, "fallback_used": model != models[0],
                    "translations": result.get("translations", []), "attempts": attempts}
        detail = response.text[:1000]
        attempts.append({"model": model, "status": response.status_code, "detail": detail})
        quota = response.status_code == 429 or "quota" in detail.lower() or "resource_exhausted" in detail.lower()
        if model == models[0] and quota:
            continue
        raise RuntimeError(f"{model} failed ({response.status_code}); fallback is quota-only. {detail}")
    raise RuntimeError("Both Gemini models are quota limited: " + json.dumps(attempts))


def _run_stage(stage: str, data: dict, project: dict) -> dict:
    if stage == "import":
        raise ValueError("Import files using the Import button; website fetching is disabled.")
    if stage == "extract":
        return _ocr_extract(data, project)
    if stage == "remove":
        from .image_inpainting import inpaint_with_model
        image_path = str(data.get("image_path", ""))
        output_path = str(data.get("output_path") or (
            get_data_dir() / "projects" / project["id"] / "cleaned" /
            (Path(image_path).stem + "-cleaned.png")
        ))
        return inpaint_with_model(image_path, data.get("regions", []), output_path,
                                  float(data.get("padding_ratio", 0.18)),
                                  str(data.get("model", "lama_manga")) )
    if stage == "translate":
        return _gemini_translate(data, project)
    if stage == "typeset":
        from .typesetting import render_page
        output_path = str(data.get("output_path") or (
            get_data_dir() / "projects" / project["id"] / "rendered" /
            (Path(str(data.get("image_path", ""))).stem + "-mm.png")
        ))
        return render_page(
            str(data.get("image_path", "")), data.get("regions", []), output_path,
            font_family=str(data.get("font_family") or project.get("font_family") or "Noto Sans Myanmar"),
            style=str(data.get("style") or project.get("typesetting_style") or "original_bubble"),
            font_size=int(data.get("font_size", 30)),
            text_color=str(data.get("text_color", "#171717")),
            outline_color=str(data.get("outline_color", "#ffffff")),
        )
    if stage == "export":
        from .exporting import export_chapter
        output_format = str(data.get("format", "zip")).lower()
        if output_format not in {"epub", "zip", "cbz"}:
            raise ValueError("Export format must be EPUB, ZIP or CBZ.")
        extension = ".epub" if output_format == "epub" else (".cbz" if output_format == "cbz" else ".zip")
        output_path = str(data.get("output_path") or (
            get_data_dir() / "projects" / project["id"] / "exports" /
            ("chapter-" + re.sub(r"[^0-9A-Za-z_-]", "_", str(data.get("chapter_number", "1"))) + extension)
        ))
        return export_chapter(data.get("pages", []), output_path,
                              str(data.get("title", "Comic Chapter")), output_format)
    raise ValueError("Unknown pipeline stage")


@router.post("/projects/{project_id}/import-epub")
async def import_epub(project_id: str, file: UploadFile = File(...), chapter_id: str | None = None):
    _ensure_table()
    project = _project(project_id)
    filename = file.filename or "manga.epub"
    if Path(filename).suffix.lower() != ".epub":
        raise HTTPException(415, "Please choose an .epub file.")
    raw = await file.read(500 * 1024 * 1024 + 1)
    if len(raw) > 500 * 1024 * 1024:
        raise HTTPException(413, "EPUB file is larger than the 500 MB upload limit.")
    try:
        from .epub_import import extract_epub
        output = extract_epub(raw, Path(project["storage_path"]), filename)
        saved = _save(
            project_id, chapter_id, "import", "completed",
            {"source_type": "epub", "filename": Path(filename).name},
            output, False
        )
        return {"run": saved, "import": output}
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, detail=f"EPUB import failed: {exc}") from exc
    finally:
        await file.close()


@router.post("/projects/{project_id}/import-zip")
async def import_zip(project_id: str, file: UploadFile = File(...), chapter_id: str | None = None):
    _ensure_table()
    project = _project(project_id)
    filename = file.filename or "comic.zip"
    if Path(filename).suffix.lower() != ".zip":
        raise HTTPException(415, "Please choose a .zip file.")
    raw = await file.read(500 * 1024 * 1024 + 1)
    try:
        if len(raw) > 500 * 1024 * 1024:
            raise ValueError("ZIP file is larger than the 500 MB upload limit.")
        from .file_import import extract_zip
        output = extract_zip(raw, Path(project["storage_path"]), filename)
        saved = _save(project_id, chapter_id, "import", "completed",
                      {"source_type": "zip", "filename": Path(filename).name}, output)
        return {"run": saved, "import": output}
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, detail=f"ZIP import failed: {exc}") from exc
    finally:
        await file.close()


@router.post("/projects/{project_id}/import-images")
async def import_manual_images(
    project_id: str,
    files: list[UploadFile] = File(...),
    chapter_id: str | None = None,
):
    _ensure_table()
    project = _project(project_id)
    try:
        entries = []
        total = 0
        for upload in files:
            raw = await upload.read(100 * 1024 * 1024 + 1)
            total += len(raw)
            if total > 500 * 1024 * 1024:
                raise ValueError("Selected images exceed the 500 MB total upload limit.")
            entries.append((upload.filename or "page.png", raw))
        from .file_import import import_images
        output = import_images(entries, Path(project["storage_path"]))
        previous = next((item for item in reversed(_latest(project_id, chapter_id))
                         if item["stage"] == "import"), None)
        previous_output = previous["output"] if previous else {}
        if previous_output.get("source_type") == "images":
            combined = list(previous_output.get("pages", [])) + list(output.get("pages", []))
            for index, page in enumerate(combined, 1):
                page["index"] = index
            output["pages"] = combined
            output["count"] = len(combined)
        saved = _save(project_id, chapter_id, "import", "completed",
                      {"source_type": "images", "file_count": len(output["pages"])}, output)
        return {"run": saved, "import": output}
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, detail=f"Image import failed: {exc}") from exc
    finally:
        for upload in files:
            await upload.close()


@router.get("/projects/{project_id}/export-file")
def download_export(project_id: str, path: str):
    project = _project(project_id)
    root = (Path(project["storage_path"]) / "exports").resolve()
    candidate = Path(path).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise HTTPException(403, "Export path is outside this project.")
    if not candidate.is_file() or candidate.suffix.lower() not in {".epub", ".zip", ".cbz"}:
        raise HTTPException(404, "Export file not found.")
    return FileResponse(candidate, filename=candidate.name)


@router.get("/projects/{project_id}/pipeline")
def pipeline_state(project_id: str, chapter_id: str | None = None):
    _ensure_table()
    _project(project_id)
    latest = {item["stage"]: item for item in _latest(project_id, chapter_id)}
    return {"stages": [{"name": stage, "status": latest.get(stage, {}).get("status", "pending"),
                         "input": latest.get(stage, {}).get("input", {}),
                         "output": latest.get(stage, {}).get("output", {}),
                         "manual": latest.get(stage, {}).get("manual", False),
                         "error": latest.get(stage, {}).get("error", "")}
                        for stage in STAGES]}


@router.post("/projects/{project_id}/pipeline/{stage}/run")
def run_pipeline_stage(project_id: str, stage: str, payload: StageInput, chapter_id: str | None = None):
    _ensure_table()
    project = _project(project_id)
    if stage not in STAGES:
        raise HTTPException(404, "Unknown pipeline stage")
    try:
        output = _run_stage(stage, payload.input, project)
        return {"run": _save(project_id, chapter_id, stage, "completed", payload.input,
                             output, payload.manual)}
    except Exception as exc:
        _save(project_id, chapter_id, stage, "failed", payload.input, {}, payload.manual, str(exc))
        raise HTTPException(422, detail=str(exc)) from exc


@router.put("/projects/{project_id}/pipeline/{stage}/output")
def edit_pipeline_output(project_id: str, stage: str, payload: StageEdit, chapter_id: str | None = None):
    _ensure_table()
    _project(project_id)
    if stage not in STAGES:
        raise HTTPException(404, "Unknown pipeline stage")
    previous = next((x for x in reversed(_latest(project_id, chapter_id)) if x["stage"] == stage), None)
    source_input = previous["input"] if previous else {}
    saved = _save(project_id, chapter_id, stage, "reviewed", source_input, payload.output, True)
    return {"run": saved, "message": "Manual output saved as the input source for the next stage."}
