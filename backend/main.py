from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Comic Translator Local API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", "file://"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "comic-translator-local", "version": "0.1.0"}

@app.get("/api/v1/capabilities")
def capabilities():
    return {
        "fetch": False,
        "ocr": False,
        "text_removal": False,
        "translation": False,
        "typesetting": False,
        "export": False,
        "message": "Processing modules are not implemented yet."
    }
