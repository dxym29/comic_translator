# Comic Translator

A separate Windows desktop application for translating comic chapters into Myanmar.

## Current implementation

- Electron desktop shell with a local Python API.
- Local SQLite database stored under the operating system's application-data directory.
- Create and list local comic projects.
- Per-project source/target language, source URL, font and lettering style settings.
- Project folders for source images, cleaned images, rendered pages and exports.
- Database tables prepared for chapters, pages, detected text regions and resumable jobs.
- Optional CPU OCR integration using PaddleOCR PP-OCRv5 mobile detection/recognition models.
- OCR preview API returns text-line boxes, recognized text and confidence values.
- Nearby OCR lines are conservatively grouped into editable text-block suggestions.
- Users can edit each block's recognized text and X/Y/width/height before preview cleanup.
- OpenCV Telea inpainting preview can remove detected text regions on a copy of the image.
- OCR/image-processing dependencies are optional and are not required for the desktop shell to start.
- Gemini model settings documented as the planned translation route:
  - Primary: Gemini 3.1 Flash-Lite
  - Quota fallback: Gemini 3.5 Flash-Lite

## Not implemented yet

Website-specific chapter fetching, automatic speech-bubble boundary detection and reliable artwork-aware text removal, Gemini translation, Myanmar text layout/rendering, batch execution and CBZ/ZIP export are not implemented yet. OCR and cleanup are currently exposed as local preview API endpoints, not a finished user-facing workflow.

## Hardware target

Initial development targets CPU-first operation on an Intel Core i5-8265U with 16GB RAM and Intel UHD 620 integrated graphics. The intended initial image-processing concurrency is one image at a time.

## Development requirements

- Node.js 20 or newer
- Python 3.10 or newer

Install:

```bash
npm install
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

# Optional CPU OCR and image cleanup:
pip install -r backend/requirements-ocr-cpu.txt
```

PaddleOCR downloads its selected model files on first use. The current OCR setup selects PP-OCRv5 mobile models and CPU execution to limit resource use. See the [official PaddleOCR CPU installation guide](https://www.paddleocr.ai/latest/en/quick_start.html).

Run the desktop application:

```bash
npm start
```

Electron starts the local Python API automatically. For backend-only development:

```bash
python -m backend
```

The API listens only on `127.0.0.1:43128`.

Local image preview endpoints:
- `POST /api/v1/images/ocr-preview` — multipart fields `file` and optional `language` (`en`, `ch`, `japan`, `korean`, `th`).
- `POST /api/v1/images/group-regions` — JSON body with a `regions` list; returns suggested text blocks.
- `POST /api/v1/images/clean-preview` — multipart fields `file` and `regions_json` (the region list returned by OCR).

OCR boxes are text-line detections, not guaranteed speech-bubble boundaries. Always review detections before cleaning an original image. Cleanup uses a basic OpenCV inpainting baseline; complex textures and overlapping artwork may need manual correction.

## Local data

On Windows, application data is stored under `%LOCALAPPDATA%\ComicTranslator`. Set `COMIC_TRANSLATOR_DATA_DIR` to override the location.

## Security

- Never commit Gemini API keys, cookies, session tokens, or downloaded comic images.
- Real API credentials will be configured locally in a later settings step.
- Fetching adapters must respect website access rules and user permissions.

## Project separation

This repository is independent of `dxym29/t_app`. No changes are made to the Webnovel Translator.

## End-to-end pipeline

The project workspace now exposes six persisted stages: Fetch, Ollama Vision extraction,
LaMa AI inpainting, Gemini translation, Myanmar typesetting, and CBZ/ZIP export.
Each stage has editable JSON input/output, a manual-output save action, and an automatic
one-page-at-a-time chapter runner. Stage results are stored in SQLite so a reviewed result
can be reused without rerunning earlier stages.

### Install the core desktop backend

```bash
pip install -r backend/requirements.txt
```

Install and start Ollama, then pull a compatible vision model:

```bash
ollama pull qwen2.5vl:3b
```

Set `GEMINI_API_KEY` in the environment before running the translation stage.

### Optional CPU LaMa inpainting

Text removal uses a real LaMa model adapter, not the OpenCV Telea preview operation.
It is optional because its PyTorch CPU runtime and model weights are large:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r backend/requirements-lama-cpu.txt
```

The first LaMa run downloads model weights and can be slow on an i5-8265U CPU.
Install the selected Myanmar font in Windows. Pillow's RAQM text layout support is
used when available; verify Myanmar shaping on the installed Pillow build before
processing a full chapter.

### Current operational notes

- Generic Fetch supports ordinary HTML image tags. JavaScript-rendered, login-gated,
  encrypted, or protected comic sites require a dedicated site adapter.
- The automatic runner processes one page at a time and checkpoints each stage.
  Pause takes effect between stage operations; it does not interrupt a running model call.
- The stage editor stores JSON. Review OCR coordinates and translations before committing
  a chapter; manual output can be saved and reused by downstream stages.
- CPU performance and Myanmar font rendering depend on the local model, installed fonts,
  and Pillow/RAQM build. No speed guarantee is made for this hardware.
