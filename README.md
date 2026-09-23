# SlideDrop

SlideDrop is a local desktop app for macOS and Windows with two document workflows:

- convert PowerPoint or PDF slide decks into high-resolution PNG images
- merge multiple PDFs into one final PDF with page-range selection and manual ordering

The app is packaged as a native `.app` bundle with PyInstaller, renders its interface with `pywebview`, serves the UI from a local FastAPI backend, and uses a statically built Next.js frontend.

## What The App Does

SlideDrop has two main tools.

### 1. Slides to Images

This workflow is for lecture decks, class slides, design reviews, and exported PDFs that you want as standalone images.

What it does:

- accepts a single `.pptx` or `.pdf`
- converts PowerPoint files to PDF using LibreOffice in headless mode
- renders each page to a PNG image at 300 DPI using Poppler via `pdf2image`
- writes output into an organized folder, typically in `~/Downloads`
- optionally runs local lecture-note extraction with Ollama after rendering
- can also extract a page range into a smaller PDF
- can extract embedded PDF text into a `.txt` file

Typical output:

- `slide_1.png`
- `slide_2.png`
- `slide_3.png`
- `lecture_extraction.txt` when text extraction is enabled

### 2. PDF Workspace

This workflow is for assembling handouts, notes, readings, or combined packets.

What it does:

- opens the native multi-file PDF picker on macOS or Windows
- inspects each selected PDF and reads its page count
- lets you drag files into the final merge order
- lets you choose page selections per file with formats like `1-3,5,8-10`
- saves the merged PDF to a custom folder or your Downloads folder
- reveals the merged file in Finder or File Explorer

Typical use cases:

- combine readings from several classes into one file
- pull only certain pages from larger PDFs
- reorder packets before sharing or printing
- merge scans, notes, and exported slides into one document

## Architecture

The app is made of four parts:

- Python 3.12 backend: FastAPI + uvicorn
- Next.js frontend: exported static build served locally
- pywebview shell: renders the native desktop window on macOS and Windows
- PyInstaller packaging: creates the `.app` bundle and DMG

At runtime:

1. `launcher.py` starts the FastAPI server in-process on a local port.
2. The bundled frontend is served from the embedded backend.
3. `pywebview` opens a native desktop window pointed at the local app URL.
4. File conversion and PDF operations happen locally on the machine.

No cloud upload is required for the core app workflows.

## Key Features

- local-first desktop app for macOS and Windows
- single-file slide conversion for `.pptx` and `.pdf`
- dedicated PDF merge workspace
- page-range extraction for PDFs
- embedded text extraction from PDFs
- optional Ollama-based lecture-note extraction
- native folder picker for save destinations
- native file picker for multi-PDF merge selection
- packaged `.app` bundle and `.dmg` output
- works in development mode and bundled mode

## Requirements

### Runtime dependencies

The packaged app includes its Python and frontend dependencies. PowerPoint conversion still requires LibreOffice, and optional local lecture extraction requires Ollama.

| Dependency | Why it is needed | Install command |
| --- | --- | --- |
| Dependency | macOS | Windows |
| --- | --- | --- |
| Python 3.12+ (builds only) | `brew install python@3.12` | Install from python.org |
| Node.js 20+ (builds only) | `brew install node` | Install from nodejs.org |
| LibreOffice | `brew install --cask libreoffice` | Install from libreoffice.org |
| PDF renderer | `brew install poppler` | Included through PyMuPDF |
| Packaging | `brew install create-dmg` | No additional tool |

### Python packages

Install from:

```bash
pip install -r backend/requirements.txt
```

Main Python packages used by the app:

- `fastapi`
- `uvicorn`
- `pywebview`
- `pypdf`
- `pdf2image`
- `Pillow`
- `httpx`

### Frontend packages

Install from the frontend directory:

```bash
cd frontend
npm ci
```

## Development Setup

### 1. Clone the project

```bash
cd SlideDrop
```

### 2. Install backend dependencies

```bash
python3 -m pip install -r backend/requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend
npm ci
cd ..
```

### 4. Run the app in development mode

```bash
python3 run_app.py
```

This starts:

- the backend on `http://127.0.0.1:8000`
- the frontend dev server on `http://127.0.0.1:3000`

### Manual dev startup

Backend:

```bash
cd backend
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm run dev
```

## Desktop Builds

The same command builds the native package for the operating system it runs on:

- macOS: `dist/SlideDrop.app` and `dist/SlideDrop.dmg`
- Windows: `dist/SlideDrop/SlideDrop.exe` and `dist/SlideDrop-Windows.zip`

Build command:

```bash
python build.py
```

What the build script does:

1. cleans previous `dist`, `build`, and `frontend_dist` output
2. runs `npm ci`
3. runs the production frontend build
4. copies the static frontend export into `frontend_dist`
5. selects `SlideDrop.spec` on macOS or `SlideDrop.windows.spec` on Windows
6. creates a DMG on macOS or a portable ZIP containing the Windows app

PyInstaller does not cross-compile. Build on the target operating system, or push to `master`/`main`: `.github/workflows/build-desktop.yml` builds both platforms in parallel and publishes both packages as workflow artifacts. The backend, frontend, launcher, and conversion logic remain shared, while native dialogs and file-manager actions live behind `backend/platform_services.py`.

If you only want to rebuild the app bundle manually:

```bash
export SLIDEDROP_DESKTOP_BUILD=1
cd frontend && npm run build && cd ..
mkdir -p frontend_dist
rm -rf frontend_dist/*
cp -R frontend/out/. frontend_dist/
python3 -m PyInstaller SlideDrop.spec --noconfirm --clean
```

## Running The Packaged App

After building, launch the app bundle normally from Finder or run it from Terminal for visible logs.

```bash
dist/SlideDrop.app/Contents/MacOS/SlideDrop
```

Running from Terminal is helpful when debugging packaging or startup issues because windowed macOS apps do not always show Python exceptions directly.

## Desktop Packaging Notes

The project is set up to work in both development mode and bundled mode.

Important packaging behaviors:

- frontend assets are bundled from `frontend_dist`
- the launcher resolves paths through `sys._MEIPASS` when frozen
- `pywebview` hidden imports are declared in the spec files
- the app starts the backend safely in a background thread
- startup errors are written to a log file when needed
- Homebrew paths are added at runtime so Poppler and LibreOffice are visible inside the packaged app

Relevant files:

- `launcher.py`
- `SlideDrop.spec`
- `build.py`
- `backend/main.py`
- `frontend/next.config.ts`
- `frontend/lib/api.ts`

## PDF Merge Workflow Details

The merge workspace is intentionally separate from the slide converter.

Current merge flow:

1. open the PDF workspace from the home screen
2. click `Choose PDFs`
3. select one or more PDFs in the native system picker
4. drag file cards into the order you want
5. edit page ranges per file
6. choose an output filename
7. optionally choose a save folder
8. click `Merge PDFs`
9. reveal the merged file in Finder or File Explorer

Page selection format:

- `all`
- `1`
- `1-4`
- `1-3,5,8-10`

Validation rules:

- page numbers must start at 1
- ranges must be ascending
- selected pages must exist within that PDF
- at least one page must be selected overall

## Slide Conversion Workflow Details

Current conversion flow:

1. open `Slides to Images`
2. upload one `.pptx` or `.pdf`
3. optionally choose a custom save folder
4. optionally enable Ollama lecture-note extraction
5. click `Convert Slides`
6. watch live progress during rendering
7. open the output folder in the system file manager from the completion screen

If the uploaded file is a PowerPoint:

- LibreOffice converts it to PDF first
- the PDF is then rendered page-by-page to PNGs

If the uploaded file is a PDF:

- the PDF is rendered directly to PNGs

## API Overview

The frontend talks to the local FastAPI backend.

### Conversion endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/upload` | upload a single `.pptx` or `.pdf` |
| `POST` | `/convert` | start slide conversion for a job |
| `GET` | `/status?job_id=...` | poll conversion progress |
| `POST` | `/extract-pdf-range` | download a smaller PDF for a selected page range |
| `POST` | `/extract-pdf-text` | download embedded PDF text as `.txt` |

### Merge endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/dialog/select-pdfs` | open the native PDF picker |
| `POST` | `/pdfs/inspect` | inspect selected PDFs and get page counts |
| `POST` | `/merge-pdfs` | merge ordered PDF inputs with page ranges |
| `POST` | `/dialog/select-folder` | open the native folder picker |
| `POST` | `/open-location` | reveal a file or open a folder in the system file manager |

### Utility endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | health check |
| `GET` | `/debug/ollama` | local Ollama debug information |

## Project Structure

```text
SlideDrop/
├── README.md
├── .gitignore
├── SlideDrop.spec
├── SlideDrop.windows.spec
├── MyApp.spec
├── launcher.py
├── build.py
├── build.sh
├── run_app.py
├── resources/
├── backend/
│   ├── main.py
│   ├── platform_services.py
│   ├── requirements.txt
│   ├── converters/
│   │   ├── pdf_to_images.py
│   │   ├── pptx_to_pdf.py
│   │   └── slide_extractor.py
│   └── utils/
│       └── file_manager.py
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── next.config.ts
│   └── package.json
└── frontend_dist/
```

## Troubleshooting

### The packaged app opens and immediately closes

Run it from Terminal:

```bash
dist/SlideDrop.app/Contents/MacOS/SlideDrop
```

Then check:

- missing hidden imports in the spec file
- missing `frontend_dist` assets
- incorrect path handling in bundled mode
- backend startup errors in `launcher.py`

On Windows, logs are stored under `%LOCALAPPDATA%\SlideDrop\Logs\error.log`. On macOS, they remain under `~/Library/Logs/SlideDrop/error.log`.

### Poppler appears installed but the app says it is missing

The packaged app does not always inherit the same shell `PATH` as your terminal.

SlideDrop now checks common Homebrew locations, including:

- `/opt/homebrew/bin`
- `/opt/homebrew/opt/poppler/bin`
- `/usr/local/bin`
- `/usr/local/opt/poppler/bin`

Verify:

```bash
which pdfinfo
which pdftoppm
brew install poppler
```

### LibreOffice is not found for PPTX conversion

Verify:

```bash
brew install --cask libreoffice
which soffice
```

SlideDrop also checks common macOS locations such as:

- `/Applications/LibreOffice.app/Contents/MacOS/soffice`
- `/opt/homebrew/bin/soffice`
- `/usr/local/bin/soffice`

### The merge PDF picker throws an AppleScript error

The app uses `osascript` for native folder and file pickers on macOS. If this fails:

- make sure the app has permission to show dialogs
- try launching the app directly from Terminal once
- rebuild with the latest `SlideDrop.spec` and `build.py`

### Finder actions do not open

The packaged app uses a backend endpoint that calls macOS `open` on the target path. If Finder actions fail, verify the file or folder still exists and try again from a fresh build.

## Output Locations

By default:

- converted slide image folders are created in `~/Downloads`
- merged PDFs are saved in `~/Downloads` unless you choose another folder

Custom output folders are supported through the native folder picker or manual path entry.

## Privacy

Files are processed locally.

Core conversion and merge workflows do not require uploading documents to a remote service. If you enable local Ollama extraction, inference still runs on your own machine.

## Notes For Contributors

When changing desktop packaging behavior, pay special attention to:

- hidden imports in both platform spec files
- path resolution through `_MEIPASS`
- `frontend_dist` inclusion
- native operation boundaries in `backend/platform_services.py`
- Homebrew path visibility on macOS and Program Files discovery on Windows
- the two-platform workflow in `.github/workflows/build-desktop.yml`

## License

MIT
