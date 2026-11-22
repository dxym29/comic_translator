# Comic Translator

A separate Windows desktop application for translating comic chapters into Myanmar.

## Project goals

- Fetch comic chapters and source images from supported websites.
- Detect text and speech-bubble regions locally.
- Remove source text locally and retain the original artwork.
- Translate detected text with Gemini:
  - Primary: Gemini 3.1 Flash-Lite
  - Quota fallback: Gemini 3.5 Flash-Lite
- Fit Myanmar text into the original regions and render translated pages.
- Support both **Original Bubble Style** and **Professional Typesetting**.
- Batch chapters with checkpoints, retries, resumable jobs, and export to CBZ/ZIP.
- Keep the existing Webnovel Translator repository and its behavior completely untouched.

## Initial architecture

- **Electron**: Windows desktop shell and user interface.
- **Python + FastAPI**: local processing service.
- **SQLite**: projects, chapters, OCR results, job state, and cache.
- **Local image pipeline**: OCR/text detection, inpainting, Myanmar text layout, and rendering.
- **Gemini API**: translation only; API keys are configured locally and must never be committed.

The initial scaffold intentionally starts with a small health-check backend and a minimal desktop shell. OCR, image cleanup, fetching adapters, translation, and export will be added as separate tested modules.

## Development

Requirements:
- Node.js 20 or newer
- Python 3.10 or newer

Install dependencies:

```bash
npm install
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

Run the local Python API in one terminal:

```bash
npm run backend
```

Run the desktop shell in another terminal:

```bash
npm start
```

The desktop shell expects the local API at `http://127.0.0.1:43128`.

## Security

- Never commit Gemini API keys, cookies, session tokens, or downloaded copyrighted chapter images.
- Local credentials will be stored using the operating system's secure credential storage in a later implementation step.
- Fetching adapters must respect site access rules and user-provided permissions.

## Current status

Scaffold only. The actual fetching, OCR, text removal, Gemini translation, Myanmar typesetting, and CBZ/ZIP export pipelines are not implemented yet.
