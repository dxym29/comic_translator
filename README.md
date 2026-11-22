# Comic Translator

A separate Windows desktop application for translating comic chapters into Myanmar.

## Current implementation

- Electron desktop shell with a local Python API.
- Local SQLite database stored under the operating system's application-data directory.
- Create and list local comic projects.
- Per-project source/target language, source URL, font and lettering style settings.
- Project folders for source images, cleaned images, rendered pages and exports.
- Database tables prepared for chapters, pages, detected text regions and resumable jobs.
- Gemini model settings documented as the planned translation route:
  - Primary: Gemini 3.1 Flash-Lite
  - Quota fallback: Gemini 3.5 Flash-Lite

## Not implemented yet

Website-specific chapter fetching, OCR/text detection, image text removal, Gemini translation, Myanmar text layout/rendering, batch execution and CBZ/ZIP export are not implemented yet. The UI does not claim these functions are ready.

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
```

Run the desktop application:

```bash
npm start
```

Electron starts the local Python API automatically. For backend-only development:

```bash
python -m backend
```

The API listens only on `127.0.0.1:43128`.

## Local data

On Windows, application data is stored under `%LOCALAPPDATA%\ComicTranslator`. Set `COMIC_TRANSLATOR_DATA_DIR` to override the location.

## Security

- Never commit Gemini API keys, cookies, session tokens, or downloaded comic images.
- Real API credentials will be configured locally in a later settings step.
- Fetching adapters must respect website access rules and user permissions.

## Project separation

This repository is independent of `dxym29/t_app`. No changes are made to the Webnovel Translator.
