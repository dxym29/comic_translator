from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
        "ocr": False,
        "text_removal": False,
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
