from contextlib import asynccontextmanager
import importlib.util
import json
import requests
import shutil
import mimetypes
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .projects import create_project, get_project, list_projects
from .region_grouping import group_text_regions
from .schemas import ProjectCreate
from .storage import initialize_database, get_data_dir
from .pipeline import router as pipeline_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Comic Translator Local API", version="0.3.0", lifespan=lifespan)
app.include_router(pipeline_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", "file://"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "comic-translator-local", "version": "0.3.0"}


@app.get("/api/v1/capabilities")
def capabilities():
    return {
        "projects": True,
        "database": True,
        "pipeline_stage_history": True,
        "fetch_generic_images": True,
        "epub_import": True,
        "ollama_vision_extraction": True,
        "gemini_translation": True,
        "ai_text_removal": importlib.util.find_spec("torch") is not None,
        "typesetting": importlib.util.find_spec("PIL") is not None,
        "export": True,
        "paddleocr_preview": importlib.util.find_spec("paddleocr") is not None,
        "opencv_preview_cleanup": importlib.util.find_spec("cv2") is not None,
        "message": "LaMa Manga and AOT-GAN CPU inpainting download verified model weights on first use; Myanmar rendering requires a supported installed font."
    }


@app.get("/api/v1/projects")
def projects():
    return {"projects": list_projects()}


@app.post("/api/v1/projects", status_code=201)
def projects_create(payload: ProjectCreate):
    try:
        project = create_project(**payload.model_dump())
        return {"project": project}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create project: {exc}") from exc



@app.delete("/api/v1/projects/{project_id}")
def projects_delete(project_id: str):
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Only allow deleting a project folder directly inside the app's projects directory.
    expected_root = (get_data_dir() / "projects").resolve()
    project_dir = Path(project["storage_path"]).expanduser().resolve()
    if project_dir.name != project_id or project_dir.parent != expected_root:
        raise HTTPException(status_code=400, detail="Project storage path is invalid")

    trash_dir = expected_root / (".deleting-" + project_id + "-" + uuid.uuid4().hex)
    try:
        if project_dir.exists():
            project_dir.rename(trash_dir)
        from .storage import connect
        with connect() as db:
            db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        if trash_dir.exists():
            shutil.rmtree(trash_dir)
        return {"deleted": True, "project_id": project_id}
    except Exception as exc:
        if trash_dir.exists() and not project_dir.exists():
            try:
                trash_dir.rename(project_dir)
            except OSError:
                pass
        raise HTTPException(status_code=500, detail=f"Could not delete project: {exc}") from exc


@app.get("/api/v1/projects/{project_id}/image")
def project_image(project_id: str, path: str):
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    root = Path(project["storage_path"]).resolve()
    candidate = Path(path).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Image path is outside this project folder")
    if not candidate.is_file() or candidate.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise HTTPException(status_code=404, detail="Project image not found")
    return FileResponse(candidate, media_type=mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")

@app.get("/api/v1/projects/{project_id}")
def project_detail(project_id: str):
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": project}


MAX_IMAGE_BYTES = 20 * 1024 * 1024


async def _read_image(upload: UploadFile) -> Any:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Install the optional CPU image-processing requirements first.") from exc
    if upload.content_type and not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Please upload an image file.")
    data = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 20 MB.")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="The uploaded file is not a supported image.")
    return image


@app.post("/api/v1/projects/{project_id}/images/ollama-detect")
async def ollama_detect_preview(project_id: str, file: UploadFile = File(...)):
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Please upload an image file.")
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 20 MB.")
    try:
        import cv2
        import numpy as np
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=400, detail="The uploaded file is not a supported image.")
        suffix = Path(file.filename or "comic-image.png").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = ".png"
        with tempfile.TemporaryDirectory(prefix="comic-ollama-") as temp_dir:
            image_path = Path(temp_dir) / ("input" + suffix)
            image_path.write_bytes(data)
            from .pipeline import _ollama_extract
            result = _ollama_extract({"image_path": str(image_path)})
        return {
            "width": int(image.shape[1]), "height": int(image.shape[0]),
            "regions": result["regions"], "count": len(result["regions"]),
            "model": result["model"],
            "note": "Text and coordinates detected locally by Ollama Vision."
        }
    except HTTPException:
        raise
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {exc}") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"Ollama could not return valid text regions: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ollama text detection failed: {exc}") from exc


@app.post("/api/v1/images/ocr-preview")
async def ocr_preview(file: UploadFile = File(...), language: str = Form("en")):
    image = await _read_image(file)
    try:
        from .ocr import recognize_image
        regions = recognize_image(image, language=language)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}") from exc
    return {"width": int(image.shape[1]), "height": int(image.shape[0]),
            "regions": regions, "count": len(regions),
            "note": "OCR boxes are text-line detections. Review them before cleaning."}


@app.post("/api/v1/images/clean-preview")
async def clean_preview(file: UploadFile = File(...), regions_json: str = Form(...)):
    image = await _read_image(file)
    try:
        import cv2
        regions = json.loads(regions_json)
        if not isinstance(regions, list) or len(regions) > 1000:
            raise ValueError("Regions must be a list containing at most 1000 items.")
        from .image_cleanup import remove_text
        cleaned = remove_text(image, regions)
        ok, encoded = cv2.imencode(".png", cleaned)
        if not ok:
            raise RuntimeError("Could not encode cleaned preview.")
        return Response(content=encoded.tobytes(), media_type="image/png")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid text regions: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image cleanup failed: {exc}") from exc


@app.post("/api/v1/images/group-regions")
def group_regions(payload: dict):
    regions = payload.get("regions")
    if not isinstance(regions, list) or len(regions) > 1000:
        raise HTTPException(status_code=400, detail="Regions must be a list containing at most 1000 items.")
    try:
        groups = group_text_regions(regions)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not group OCR text lines: {exc}") from exc
    return {"groups": groups, "count": len(groups)}
