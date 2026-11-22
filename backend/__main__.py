import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("COMIC_TRANSLATOR_HOST", "127.0.0.1"),
        port=int(os.getenv("COMIC_TRANSLATOR_PORT", "43128")),
        log_level="info",
    )
