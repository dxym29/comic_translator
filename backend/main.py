from contextlib import asynccontextmanager
import importlib.util
import json
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .projects import create_project, get_project, list_projects
from .schemas import ProjectCreate
from .storage import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Comic Translator Local API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", "file://"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "comic-translator-local", "version": "0.2.0"}


@app.get("/api/v1/capabilities")
def capabilities():
    return {
        "projects": True,
        "database": True,
        "fetch": False,
        "ocr": importlib.util.find_spec("paddleocr") is not None,
        "text_removal": importlib.util.find_spec("cv2") is not None,
        "translation": False,
        "typesetting": False,
        "export": False,
        "message": "Project management is ready. Comic processing modules are next."
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


@app.post("/api/v1/images/ocr-preview")
async def ocr_preview(
    file: UploadFile = File(...),
    language: str = Form("en"),
):
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
    return {
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "regions": regions,
        "count": len(regions),
        "note": "OCR boxes are text-line detections. Review them before removing artwork."
    }


@app.post("/api/v1/images/clean-preview")
async def clean_preview(
    file: UploadFile = File(...),
    regions_json: str = Form(...),
):
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
