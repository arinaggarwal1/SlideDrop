# SlideDrop

**Convert PowerPoint and PDF slides into high-quality PNG images.**

SlideDrop is a local desktop tool with a polished web UI. Upload a `.pptx` or `.pdf` file, and every slide/page is exported as a 300 DPI PNG image to your Downloads folder.

![SlideDrop](https://img.shields.io/badge/SlideDrop-Slide%20Converter-6366f1?style=for-the-badge)

---

## Features

- 📄 **PPTX & PDF support** — accepts PowerPoint and PDF files
- 🖼️ **300 DPI rendering** — crystal-clear images, even for small text
- 📁 **Auto-organized output** — creates a named folder in your Downloads
- 🌗 **Dark mode** — system-aware theme with manual toggle
- ⚡ **Real-time progress** — live progress bar during conversion
- 🔒 **Fully local** — files never leave your machine

---

## Prerequisites

| Dependency | Install Command (macOS) |
|---|---|
| **Python 3.11+** | `brew install python@3.11` |
| **Node.js 18+** | `brew install node` |
| **LibreOffice** | `brew install --cask libreoffice` |
| **Poppler** | `brew install poppler` |

> **LibreOffice** is required for PPTX → PDF conversion.  
> **Poppler** is required for PDF → PNG rendering.

---

## Quick Start

### 1. Clone and navigate

```bash
cd SlideDrop
```

### 2. Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Run the app

```bash
python run_app.py
```

This will:
- Start the backend on `http://localhost:8000`
- Start the frontend on `http://localhost:3000`
- Open your browser to `http://localhost:3000`

---

## Manual Start (Alternative)

**Terminal 1 — Backend:**

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000).

---

## How It Works

1. **Upload** a `.pptx` or `.pdf` file via drag-and-drop or file picker
2. If PPTX: automatically converts to PDF using LibreOffice headless
3. Each PDF page is rendered to PNG at 300 DPI using pdf2image (Poppler)
4. Images are saved as `slide_1.png`, `slide_2.png`, etc.
5. Output folder: `~/Downloads/<filename>_slides/`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload a file, returns job ID + page count |
| `POST` | `/convert` | Start conversion for a job |
| `GET` | `/status?job_id=...` | Get conversion progress |
| `GET` | `/health` | Health check |

---

## Project Structure

```
SlideDrop/
├── run_app.py                  # Launch script
├── README.md
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── requirements.txt
│   ├── converters/
│   │   ├── pptx_to_pdf.py      # PPTX → PDF (LibreOffice)
│   │   └── pdf_to_images.py    # PDF → PNG (pdf2image)
│   └── utils/
│       └── file_manager.py     # Downloads folder & file utilities
└── frontend/
    ├── app/
    │   ├── layout.tsx           # Root layout with theme provider
    │   ├── page.tsx             # Main page (upload/process/done)
    │   └── globals.css          # Theme & animations
    └── components/
        ├── UploadZone.tsx       # Drag-and-drop upload area
        ├── ProcessingView.tsx   # Progress bar + status
        ├── FinishedView.tsx     # Success + open folder
        ├── ThemeProvider.tsx    # Dark/light mode provider
        └── ThemeToggle.tsx      # Theme toggle button
```

---

## License

MIT
