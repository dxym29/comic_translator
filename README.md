# Comic Translator

A local-first Windows desktop application for translating comic pages into Myanmar.

## Workflow

The application uses local files only. Website fetching has been removed from the normal workflow.

1. Create or open a project.
2. Import an **EPUB**, **ZIP**, or one/multiple **JPG, PNG, WEBP, GIF, BMP** images.
3. Detect text with PaddleOCR through ONNX Runtime CPU.
4. Review detected text and remove the original lettering with LaMa Manga or AOT-GAN.
5. Translate with Gemini 3.1 Flash-Lite; Gemini 3.5 Flash-Lite is used only as the quota fallback.
6. Typeset the Myanmar translation onto the page.
7. Export the finished chapter.

The **Start translation** button runs the imported pages through the pipeline. Each stage can still be selected and run separately; the Advanced review section contains editable stage input/output for manual correction.

## Import and export behavior

- **EPUB in → EPUB out.** Page images are extracted in EPUB spine reading order. The output is rebuilt as a valid image-based EPUB containing the translated pages.
- **ZIP in → ZIP out.** Images are imported in natural filename order (page 1, page 2, page 10) and exported as a ZIP.
- **Manual images → ZIP out.** You can add one image at a time or select multiple images. Images added one at a time are appended to the current manual-image chapter.
- ZIP imports are limited to 500 MB compressed / 1 GB expanded. Individual images are limited to 100 MB and chapters to 2,000 pages.
- Exported files are saved in the project exports folder. A Download link appears after export.

EPUB output preserves the EPUB file format and comic page sequence, but it is rebuilt from the translated page images; it does not preserve the original publisher's metadata, navigation, or text layout.

## Local processing

- OCR: PaddleOCR 3.7.0 + ONNX Runtime CPU. English is the default; PP-OCRv6 is selected for English/Japanese/Chinese and PP-OCRv5 for Korean/Thai.
- Text removal: selectable LaMa Manga and AOT-GAN CPU models.
- Translation: Gemini 3.1 Flash-Lite primary, Gemini 3.5 Flash-Lite quota fallback.
- Typesetting: Pillow RAQM + FriBiDi with the selected installed font.
- Storage: local SQLite and project folders under `%LOCALAPPDATA%\\ComicTranslator`.

## Requirements

- Windows 10/11
- Node.js 20+
- Python 3.10+ (Python 3.13 is recommended for the optional OCR dependencies)
- Gemini API key configured in the local environment as `GEMINI_API_KEY`

Install:

```bash
npm install
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m backend.install_raqm
pip install -r backend/requirements-ocr-cpu.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r backend/requirements-lama-cpu.txt
npm start
```

PaddleOCR downloads its selected model files on first use. Inpainting model weights are downloaded and checksum-verified on first use.

## Hardware target

Designed for CPU-first operation on an Intel Core i5-8265U with 16 GB RAM and Intel UHD 620. Image processing runs one page at a time. Large chapters and local model inference may take time.

## Important limitations

- OCR detects text lines, not guaranteed speech-bubble boundaries. Review and correct regions before removing text.
- AI inpainting depends on mask quality and surrounding artwork; inspect each result.
- Myanmar text rendering uses Pillow RAQM + FriBiDi; the setup downloads the required FriBiDi DLL automatically on Windows.
- Website chapter fetching is intentionally disabled. Import files from your computer instead.

## Project separation

This repository is independent of `dxym29/t_app` and `dxym29/t_app_local_ai`.
