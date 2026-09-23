"""
SlideDrop Backend — FastAPI application.
Converts PPTX/PDF files into high-quality PNG images.
"""

import os
import sys
import asyncio
import shutil
import subprocess
import time
import uuid
import threading
import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from pypdf import PdfReader, PdfWriter

from converters.pptx_to_pdf import (
    convert_pptx_to_pdf,
    LibreOfficeNotFoundError,
    ConversionError as PptxConversionError,
)
from converters.pdf_to_images import (
    convert_pdf_to_images,
    get_pdf_page_count,
    PopplerNotFoundError,
    PDFConversionError,
)
from converters.slide_extractor import (
    DEFAULT_MODEL_CHOICE,
    get_model_name,
    list_slide_images,
    normalize_model_choice,
    OLLAMA_BASE,
    OLLAMA_HOST,
    run_extraction,
)
from prompt_builder import PromptBuilderError, generate_custom_prompt
from utils.file_manager import (
    create_output_directory,
    create_temp_directory,
    cleanup_temp_directory,
    get_downloads_folder,
    get_file_extension,
    is_supported_file,
)
from platform_services import desktop_platform

# ---------------------------------------------------------------------------
# Frontend static directory detection (bundled and local)
# ---------------------------------------------------------------------------

IS_BUNDLED = bool(getattr(sys, "frozen", False))
APP_MODE_ENV = "SLIDEDROP_APP_MODE"
APP_MODE = os.getenv(APP_MODE_ENV, "development").strip().lower()
if APP_MODE not in {"development", "production"}:
    APP_MODE = "development"
SERVE_STATIC_FRONTEND = IS_BUNDLED or APP_MODE == "production"


def _resolve_frontend_dir() -> Optional[Path]:
    """Find a static frontend directory that contains index.html."""
    candidates: list[Path] = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        meipass_path = Path(meipass)
        candidates.append(meipass_path / "frontend_dist")
        candidates.append(meipass_path.parent / "Resources" / "frontend_dist")

    exe_path = Path(sys.executable).resolve()
    candidates.append(exe_path.parent.parent / "Resources" / "frontend_dist")

    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    candidates.append(project_root / "frontend_dist")
    candidates.append(project_root / "frontend" / "out")
    candidates.append(Path.cwd() / "frontend_dist")
    candidates.append(Path.cwd() / "frontend" / "out")

    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate
    return None


_FRONTEND_DIR = _resolve_frontend_dir()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="SlideDrop API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

# Stores info about uploaded files:  job_id -> {...}
jobs: dict[str, dict] = {}
app_logger = logging.getLogger("uvicorn.error")


@app.on_event("startup")
async def _log_runtime_mode():
    """Log mode + static-frontend resolution for easier desktop debugging."""
    if SERVE_STATIC_FRONTEND and not _FRONTEND_DIR:
        app_logger.warning(
            "Static frontend was requested (mode=%s, bundled=%s) but no frontend_dist was found.",
            APP_MODE,
            IS_BUNDLED,
        )
    else:
        app_logger.info(
            "SlideDrop mode=%s bundled=%s serve_static=%s frontend_dir=%s",
            APP_MODE,
            IS_BUNDLED,
            SERVE_STATIC_FRONTEND,
            str(_FRONTEND_DIR) if _FRONTEND_DIR else "None",
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    job_id: str
    filename: str
    file_type: str
    page_count: int
    source_count: int = 1
    merged: bool = False


class ConvertRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    job_id: str
    output_folder: Optional[str] = None
    extract_text: bool = False
    parallelism: int = 4
    model_choice: Optional[str] = None


class PdfRangeRequest(BaseModel):
    job_id: str
    page_range: str  # e.g. "20-40" or "12"
    output_folder: Optional[str] = None


class PdfTextRequest(BaseModel):
    job_id: str
    output_folder: Optional[str] = None


class SelectFolderResponse(BaseModel):
    path: Optional[str] = None


class SelectFilesResponse(BaseModel):
    paths: list[str] = []


class InspectPdfFilesRequest(BaseModel):
    paths: list[str]


class InspectPdfFileResponse(BaseModel):
    path: str
    filename: str
    page_count: int


class InspectPdfFilesResponse(BaseModel):
    files: list[InspectPdfFileResponse]


class OpenLocationRequest(BaseModel):
    path: str


class ActionResponse(BaseModel):
    ok: bool


class SavedFileResponse(BaseModel):
    ok: bool
    output_path: str
    output_folder: str
    filename: str


class ConvertResponse(BaseModel):
    job_id: str
    message: str


class PromptBuilderGenerateRequest(BaseModel):
    use_case: str


class PromptBuilderResponse(BaseModel):
    prompt: str


class MergePdfItemRequest(BaseModel):
    path: str
    page_range: Optional[str] = None


class MergePdfsRequest(BaseModel):
    files: list[MergePdfItemRequest]
    output_folder: Optional[str] = None
    output_name: Optional[str] = None


class MergePdfsResponse(BaseModel):
    ok: bool
    output_path: str
    output_folder: str
    filename: str
    page_count: int
    source_count: int


class StatusResponse(BaseModel):
    job_id: str
    state: str  # "pending" | "converting" | "done" | "extracting" | "complete" | "error"
    current_slide: int
    total_slides: int
    output_folder: Optional[str] = None
    error: Optional[str] = None
    extraction_state: Optional[str] = None  # "extracting" | "complete" | "error"
    extraction_current: int = 0
    extraction_total: int = 0
    extraction_active_jobs: int = 0
    extraction_file: Optional[str] = None
    extraction_stage: Optional[str] = None
    debug_log: list[str] = []


class OllamaDebugResponse(BaseModel):
    ollama_base: str
    ollama_path: Optional[str] = None
    api_reachable: bool
    installed_models: list[str]
    running_models: list[str]
    default_model_choice: str
    notes: list[str]


def _append_debug(job: dict, message: str):
    """Append a timestamped debug message to a job."""
    timestamp = time.strftime("%H:%M:%S")
    debug_log = job.setdefault("debug_log", [])
    formatted = f"[{timestamp}] {message}"
    debug_log.append(formatted)
    if len(debug_log) > 25:
        del debug_log[:-25]
    app_logger.info("job %s %s", job.get("job_id", "unknown"), formatted)


def _create_upload_job(
    *,
    filename: str,
    file_type: str,
    temp_dir: str,
    saved_path: str,
    pdf_path: str,
    page_count: int,
    source_count: int = 1,
    merged: bool = False,
) -> UploadResponse:
    """Create and store a new upload job."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "filename": filename,
        "file_type": file_type,
        "temp_dir": temp_dir,
        "saved_path": saved_path,
        "pdf_path": pdf_path,
        "page_count": page_count,
        "state": "pending",
        "current_slide": 0,
        "total_slides": page_count,
        "output_folder": None,
        "error": None,
        "source_count": source_count,
        "merged": merged,
    }
    return UploadResponse(
        job_id=job_id,
        filename=filename,
        file_type=file_type,
        page_count=page_count,
        source_count=source_count,
        merged=merged,
    )


def _choose_folder() -> Optional[str]:
    """Open the current platform's native folder picker."""
    return desktop_platform.choose_folder()


def _choose_pdf_files() -> list[str]:
    """Open the current platform's native multi-select PDF picker."""
    return desktop_platform.choose_pdf_files()


def _merge_pdf_sources(sources: list[tuple[str, str]], temp_dir: str) -> UploadResponse:
    """Merge local PDF sources and create a single upload job."""
    if len(sources) < 2:
        raise HTTPException(status_code=400, detail="Select at least two PDF files to merge.")

    merged_filename = f"{Path(sources[0][0]).stem}_merged.pdf"
    merged_path = os.path.join(temp_dir, merged_filename)
    writer = PdfWriter()
    total_pages = 0

    try:
        for _, saved_path in sources:
            reader = PdfReader(saved_path)
            total_pages += len(reader.pages)
            for page in reader.pages:
                writer.add_page(page)

        with open(merged_path, "wb") as handle:
            writer.write(handle)
    except Exception as e:
        cleanup_temp_directory(temp_dir)
        raise HTTPException(status_code=500, detail=f"Failed to merge PDFs: {e}")

    return _create_upload_job(
        filename=merged_filename,
        file_type=".pdf",
        temp_dir=temp_dir,
        saved_path=merged_path,
        pdf_path=merged_path,
        page_count=total_pages,
        source_count=len(sources),
        merged=True,
    )


def _parse_page_range(page_range: str, total_pages: int) -> tuple[int, int]:
    """Parse and validate a 1-indexed page range string."""
    normalized = page_range.strip().replace(" ", "")
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", normalized)
    if not match:
        raise ValueError("Invalid page range format. Use '20-40' or '20'.")

    start = int(match.group(1))
    end = int(match.group(2) or match.group(1))

    if start < 1 or end < 1:
        raise ValueError("Page numbers must be >= 1.")
    if start > end:
        raise ValueError("Start page must be less than or equal to end page.")
    if end > total_pages:
        raise ValueError(f"Page range exceeds document length ({total_pages} pages).")

    return start, end


def _resolve_pdf_page_range(page_range: str, reader: PdfReader) -> tuple[int, int]:
    """Resolve a PDF range using embedded page labels when available, else physical pages."""
    total_pages = len(reader.pages)
    start, end = _parse_page_range(page_range, max(total_pages, 10**9))

    page_labels = getattr(reader, "page_labels", None) or []
    if page_labels:
        label_to_index: dict[str, int] = {}
        for index, label in enumerate(page_labels):
            normalized_label = str(label).strip()
            if normalized_label.isdigit() and normalized_label not in label_to_index:
                label_to_index[normalized_label] = index

        start_label = str(start)
        end_label = str(end)
        if start_label in label_to_index and end_label in label_to_index:
            start_index = label_to_index[start_label]
            end_index = label_to_index[end_label]
            expected_labels = [str(value) for value in range(start, end + 1)]
            actual_labels = [str(label).strip() for label in page_labels[start_index : end_index + 1]]

            if (
                start_index <= end_index
                and len(actual_labels) == len(expected_labels)
                and actual_labels == expected_labels
            ):
                return start_index, end_index

    if end > total_pages:
        raise ValueError(f"Page range exceeds document length ({total_pages} pages).")

    return start - 1, end - 1


def _parse_page_selection(page_range: Optional[str], total_pages: int) -> list[int]:
    """Parse page selections like '1-3,5,8-10' into zero-based indices."""
    if total_pages < 1:
        raise ValueError("PDF has no pages to merge.")

    normalized = (page_range or "").strip().lower().replace(" ", "")
    if not normalized or normalized == "all":
        return list(range(total_pages))

    indices: list[int] = []
    for segment in normalized.split(","):
        if not segment:
            raise ValueError("Invalid page selection format.")

        match = re.fullmatch(r"(\d+)(?:-(\d+))?", segment)
        if not match:
            raise ValueError(
                "Invalid page selection. Use formats like '1-3,5,8-10'."
            )

        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))

        if start < 1 or end < 1:
            raise ValueError("Page numbers must be greater than or equal to 1.")
        if start > end:
            raise ValueError("Each page range must start before it ends.")
        if end > total_pages:
            raise ValueError(
                f"Page selection exceeds document length ({total_pages} pages)."
            )

        indices.extend(range(start - 1, end))

    return indices


def _build_output_file_path(output_folder: Optional[str], output_name: str) -> Path:
    """Resolve an output file path and avoid filename collisions."""
    base_dir = Path(output_folder).expanduser().resolve() if output_folder else get_downloads_folder()
    base_dir.mkdir(parents=True, exist_ok=True)

    destination = base_dir / Path(output_name).name
    if not destination.exists():
        return destination

    stem = destination.stem
    suffix = destination.suffix
    counter = 1
    while True:
        candidate = base_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _build_output_pdf_path(output_folder: Optional[str], output_name: Optional[str]) -> Path:
    """Resolve a merged PDF output path and avoid collisions."""
    candidate_name = Path((output_name or "").strip() or "merged_document.pdf").name
    if not candidate_name.lower().endswith(".pdf"):
        candidate_name = f"{candidate_name}.pdf"
    return _build_output_file_path(output_folder, candidate_name)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a PPTX or PDF file and get metadata back."""

    if not file.filename or not is_supported_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and PowerPoint (.pptx) files are supported.",
        )

    # Save uploaded file to a temp directory
    temp_dir = create_temp_directory()
    saved_path = os.path.join(temp_dir, file.filename)

    try:
        with open(saved_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        cleanup_temp_directory(temp_dir)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Determine page count
    ext = get_file_extension(file.filename)
    page_count = 0
    pdf_path = saved_path

    try:
        if ext == ".pptx":
            # Convert to PDF first to get page count
            pdf_path = convert_pptx_to_pdf(saved_path, temp_dir)
            page_count = get_pdf_page_count(pdf_path)
        else:
            page_count = get_pdf_page_count(saved_path)
    except LibreOfficeNotFoundError as e:
        cleanup_temp_directory(temp_dir)
        raise HTTPException(status_code=422, detail=str(e))
    except PopplerNotFoundError as e:
        cleanup_temp_directory(temp_dir)
        raise HTTPException(status_code=422, detail=str(e))
    except (PptxConversionError, PDFConversionError) as e:
        cleanup_temp_directory(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))

    return _create_upload_job(
        filename=file.filename,
        file_type=ext,
        temp_dir=temp_dir,
        saved_path=saved_path,
        pdf_path=pdf_path,
        page_count=page_count,
    )


@app.post("/upload-merge", response_model=UploadResponse)
async def upload_and_merge_pdfs(files: list[UploadFile] = File(...)):
    """Upload multiple PDFs, merge them, and register a single conversion job."""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Select at least two PDF files to merge.")

    invalid_names = [
        file.filename or "Unnamed file"
        for file in files
        if not file.filename or get_file_extension(file.filename) != ".pdf"
    ]
    if invalid_names:
        raise HTTPException(
            status_code=400,
            detail="Only PDF files can be merged together.",
        )

    temp_dir = create_temp_directory()
    saved_paths: list[tuple[str, str]] = []

    try:
        for index, file in enumerate(files, start=1):
            filename = Path(file.filename or f"document_{index}.pdf").name
            saved_path = os.path.join(temp_dir, f"{index:03d}_{filename}")
            with open(saved_path, "wb") as handle:
                handle.write(await file.read())
            saved_paths.append((filename, saved_path))
    except Exception as e:
        cleanup_temp_directory(temp_dir)
        raise HTTPException(status_code=500, detail=f"Failed to prepare PDFs for merging: {e}")

    return _merge_pdf_sources(saved_paths, temp_dir)


@app.post("/dialog/select-folder", response_model=SelectFolderResponse)
async def select_folder_dialog():
    """Open a native folder picker for choosing an output directory."""
    try:
        return SelectFolderResponse(path=_choose_folder())
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/prompt-builder/generate", response_model=PromptBuilderResponse)
async def prompt_builder_generate(req: PromptBuilderGenerateRequest):
    """Generate a rigor-preserving extraction prompt for a custom use case."""
    try:
        prompt_text = await generate_custom_prompt(req.use_case)
        return PromptBuilderResponse(prompt=prompt_text)
    except PromptBuilderError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code, "message": e.message},
        )


@app.post("/dialog/select-pdfs", response_model=SelectFilesResponse)
async def select_pdf_files_dialog():
    """Open a native multi-file picker for PDF merge selection."""
    try:
        return SelectFilesResponse(paths=_choose_pdf_files())
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pdfs/inspect", response_model=InspectPdfFilesResponse)
async def inspect_pdf_files(req: InspectPdfFilesRequest):
    """Validate PDF paths and return filenames + page counts for merge setup."""
    if not req.paths:
        return InspectPdfFilesResponse(files=[])

    inspected: list[InspectPdfFileResponse] = []
    for raw_path in req.paths:
        source_path = Path(raw_path).expanduser().resolve()
        if source_path.suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF files can be merged.")
        if not source_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {source_path}")

        try:
            page_count = len(PdfReader(str(source_path)).pages)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to read PDF '{source_path.name}': {e}",
            )

        inspected.append(
            InspectPdfFileResponse(
                path=str(source_path),
                filename=source_path.name,
                page_count=page_count,
            )
        )

    return InspectPdfFilesResponse(files=inspected)


@app.post("/dialog/select-and-merge-pdfs", response_model=UploadResponse)
async def select_and_merge_pdfs_dialog():
    """Open a native PDF picker, merge the selected files, and create a job."""
    selected_paths = _choose_pdf_files()
    if not selected_paths:
        raise HTTPException(status_code=400, detail="No PDF files were selected.")

    temp_dir = create_temp_directory()
    saved_paths: list[tuple[str, str]] = []

    try:
        for index, raw_path in enumerate(selected_paths, start=1):
            source_path = Path(raw_path).expanduser().resolve()
            if source_path.suffix.lower() != ".pdf":
                cleanup_temp_directory(temp_dir)
                raise HTTPException(status_code=400, detail="Only PDF files can be merged together.")
            if not source_path.exists():
                cleanup_temp_directory(temp_dir)
                raise HTTPException(status_code=404, detail=f"File not found: {source_path}")

            saved_path = os.path.join(temp_dir, f"{index:03d}_{source_path.name}")
            shutil.copy2(source_path, saved_path)
            saved_paths.append((source_path.name, saved_path))
    except HTTPException:
        raise
    except Exception as e:
        cleanup_temp_directory(temp_dir)
        raise HTTPException(status_code=500, detail=f"Failed to prepare PDFs for merging: {e}")

    return _merge_pdf_sources(saved_paths, temp_dir)


@app.post("/merge-pdfs", response_model=MergePdfsResponse)
async def merge_pdfs(req: MergePdfsRequest):
    """Merge selected PDF files into one output file using the requested order/ranges."""
    if not req.files:
        raise HTTPException(status_code=400, detail="Add at least one PDF to merge.")

    destination = _build_output_pdf_path(req.output_folder, req.output_name)
    writer = PdfWriter()
    total_pages = 0

    try:
        for item in req.files:
            source_path = Path(item.path).expanduser().resolve()
            if source_path.suffix.lower() != ".pdf":
                raise HTTPException(status_code=400, detail="Only PDF files can be merged.")
            if not source_path.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {source_path}")

            reader = PdfReader(str(source_path))
            page_indices = _parse_page_selection(item.page_range, len(reader.pages))
            for index in page_indices:
                writer.add_page(reader.pages[index])
                total_pages += 1

        if total_pages == 0:
            raise HTTPException(status_code=400, detail="Select at least one page to merge.")

        with open(destination, "wb") as handle:
            writer.write(handle)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to merge PDFs: {e}")

    return MergePdfsResponse(
        ok=True,
        output_path=str(destination),
        output_folder=str(destination.parent),
        filename=destination.name,
        page_count=total_pages,
        source_count=len(req.files),
    )


@app.post("/open-location", response_model=ActionResponse)
async def open_location(req: OpenLocationRequest):
    """Reveal a file or open a folder in the platform file manager."""
    target = Path(req.path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="The selected location no longer exists.")

    try:
        desktop_platform.reveal_path(target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open location: {e}")

    return ActionResponse(ok=True)


@app.post("/extract-pdf-range", response_model=SavedFileResponse)
async def extract_pdf_range(req: PdfRangeRequest):
    """Extract a page range from an uploaded file and save it as a PDF."""
    job = jobs.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    pdf_path = job.get("pdf_path")
    saved_path = job.get("saved_path")
    filename = job.get("filename", "document")
    file_type = job.get("file_type", "").lower()
    total_pages = job.get("page_count", 0)

    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(
            status_code=400,
            detail="Source PDF is no longer available. Please upload the file again.",
        )

    try:
        if file_type == ".pptx":
            start_page, end_page = _parse_page_range(req.page_range, total_pages)
            if not saved_path or not os.path.exists(saved_path):
                raise HTTPException(
                    status_code=400,
                    detail="Source presentation is no longer available. Please upload the file again.",
                )

            out_name = f"{Path(filename).stem}_pages_{start_page}-{end_page}.pdf"
            output_path = _build_output_file_path(req.output_folder, out_name)
            generated_path = Path(
                convert_pptx_to_pdf(
                    saved_path,
                    str(output_path.parent),
                    page_range=f"{start_page}-{end_page}",
                    output_basename=output_path.stem,
                )
            )
            if generated_path != output_path:
                generated_path.replace(output_path)
        else:
            reader = PdfReader(pdf_path)
            start_index, end_index = _resolve_pdf_page_range(req.page_range, reader)
            out_name = f"{Path(filename).stem}_pages_{req.page_range.strip().replace(' ', '')}.pdf"
            output_path = _build_output_file_path(req.output_folder, out_name)
            writer = PdfWriter()
            for i in range(start_index, end_index + 1):
                writer.add_page(reader.pages[i])

            with open(output_path, "wb") as f:
                writer.write(f)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract pages: {e}")

    return SavedFileResponse(
        ok=True,
        output_path=str(output_path),
        output_folder=str(output_path.parent),
        filename=out_name,
    )


@app.post("/extract-pdf-text", response_model=SavedFileResponse)
async def extract_pdf_text(req: PdfTextRequest):
    """Extract embedded (non-OCR) text from an uploaded PDF and save it as a TXT file."""
    job = jobs.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    pdf_path = job.get("pdf_path")
    filename = job.get("filename", "document")

    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(
            status_code=400,
            detail="Source PDF is no longer available. Please upload the file again.",
        )

    out_name = f"{Path(filename).stem}_text.txt"
    output_path = _build_output_file_path(req.output_folder, out_name)

    try:
        reader = PdfReader(pdf_path)
        chunks: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            chunks.append(f"===== Page {index} =====")
            chunks.append(text if text else "[No embedded text found on this page]")
            chunks.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(chunks).strip() + "\n")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract PDF text: {e}")

    return SavedFileResponse(
        ok=True,
        output_path=str(output_path),
        output_folder=str(output_path.parent),
        filename=out_name,
    )


@app.post("/convert", response_model=ConvertResponse)
async def start_conversion(req: ConvertRequest):
    """Start the conversion process for a previously uploaded file."""

    job = jobs.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job["state"] not in ("pending", "error"):
        raise HTTPException(
            status_code=400,
            detail=f"Job is already in state: {job['state']}",
        )

    # Create output directory
    output_dir = create_output_directory(job["filename"], req.output_folder)
    job["output_folder"] = str(output_dir)
    job["state"] = "converting"
    job["current_slide"] = 0
    job["error"] = None
    job["extract_text"] = req.extract_text
    job["parallelism"] = max(1, min(8, req.parallelism))
    try:
        job["model_choice"] = normalize_model_choice(req.model_choice)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    job["extraction_state"] = None
    job["extraction_current"] = 0
    job["extraction_total"] = 0
    job["extraction_active_jobs"] = 0
    job["extraction_file"] = None
    job["extraction_stage"] = None
    job["debug_log"] = []
    _append_debug(job, f"Starting conversion for {job['filename']}")

    # Run conversion in background thread
    def _convert():
        try:
            pdf_path = job["pdf_path"]

            def on_progress(current: int, total: int):
                job["current_slide"] = current
                job["total_slides"] = total

            convert_pdf_to_images(
                pdf_path=pdf_path,
                output_dir=str(output_dir),
                dpi=300,
                on_progress=on_progress,
            )
            _append_debug(job, f"Rendered slides to {output_dir}")

            if job["extract_text"]:
                job["state"] = "extracting"
                _start_extraction(job, str(output_dir))
            else:
                job["state"] = "done"
                _append_debug(job, "Conversion complete without AI extraction")

        except Exception as e:
            job["state"] = "error"
            job["error"] = str(e)
            _append_debug(job, f"Conversion failed: {e}")

        finally:
            # Cleanup temp files
            cleanup_temp_directory(job["temp_dir"])

    thread = threading.Thread(target=_convert, daemon=True)
    thread.start()

    return ConvertResponse(
        job_id=req.job_id,
        message="Conversion started.",
    )


@app.get("/status", response_model=StatusResponse)
async def get_status(job_id: str):
    """Get the current conversion progress."""

    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return StatusResponse(
        job_id=job_id,
        state=job["state"],
        current_slide=job["current_slide"],
        total_slides=job["total_slides"],
        output_folder=job["output_folder"],
        error=job["error"],
        extraction_state=job.get("extraction_state"),
        extraction_current=job.get("extraction_current", 0),
        extraction_total=job.get("extraction_total", 0),
        extraction_active_jobs=job.get("extraction_active_jobs", 0),
        extraction_file=job.get("extraction_file"),
        extraction_stage=job.get("extraction_stage"),
        debug_log=job.get("debug_log", []),
    )


# ---------------------------------------------------------------------------
# Extraction pipeline
# ---------------------------------------------------------------------------

def _start_extraction(job: dict, output_dir: str):
    """Launch the async extraction pipeline in a new thread."""
    extraction_path = os.path.join(output_dir, "lecture_extraction.txt")
    job["extraction_state"] = "extracting"
    job["extraction_stage"] = "queued"
    job["extraction_total"] = len(list_slide_images(output_dir))
    _append_debug(
        job,
        f"Queued extraction with {get_model_name(job.get('model_choice', DEFAULT_MODEL_CHOICE))}",
    )
    _append_debug(job, f"Using Ollama base {OLLAMA_BASE}")
    if job["extraction_total"] == 0:
        _append_debug(job, "No slide PNG files found yet in output directory")

    def on_progress(completed: int, total: int, active: int):
        job["extraction_current"] = completed
        job["extraction_total"] = total
        job["extraction_active_jobs"] = active

    def on_status(stage: str, message: str):
        job["extraction_stage"] = stage
        _append_debug(job, message)

    def _run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result_path = loop.run_until_complete(
                run_extraction(
                    slide_dir=output_dir,
                    output_path=extraction_path,
                    parallelism=job.get("parallelism", 4),
                    model_choice=job.get("model_choice", DEFAULT_MODEL_CHOICE),
                    on_progress=on_progress,
                    on_status=on_status,
                )
            )
            loop.close()
            job["extraction_file"] = result_path
            job["extraction_state"] = "complete"
            job["state"] = "complete"
            job["extraction_stage"] = "complete"
            _append_debug(job, f"Extraction complete. Wrote {result_path}")
        except Exception as e:
            job["extraction_state"] = "error"
            job["state"] = "error"
            job["extraction_stage"] = "error"
            job["error"] = f"Extraction failed: {e}"
            _append_debug(job, job["error"])

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/debug/ollama", response_model=OllamaDebugResponse)
async def debug_ollama():
    """Return a quick local-debug snapshot of the Ollama environment."""
    ollama_path = shutil.which("ollama")
    notes: list[str] = []

    try:
        import httpx

        resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=2)
        api_reachable = resp.status_code == 200
        installed_models = [
            model.get("name", "")
            for model in resp.json().get("models", [])
            if model.get("name")
        ] if api_reachable else []
    except Exception as e:
        api_reachable = False
        installed_models = []
        notes.append(f"Ollama API check failed: {e}")

    running_models: list[str] = []
    if ollama_path:
        try:
            result = subprocess.run(
                [ollama_path, "ps"],
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, "OLLAMA_HOST": OLLAMA_HOST},
            )
            if result.returncode == 0:
                lines = [line for line in result.stdout.splitlines() if line.strip()]
                running_models = lines[1:] if len(lines) > 1 else []
            else:
                notes.append(result.stderr.strip() or "ollama ps failed")
        except Exception as e:
            notes.append(f"ollama ps failed: {e}")
    else:
        notes.append("Ollama binary not found in PATH")

    if not api_reachable:
        notes.append(f"The SlideDrop Ollama API is not currently responding at {OLLAMA_BASE}.")
    if api_reachable and not installed_models:
        notes.append("Ollama is reachable but no models were reported by /api/tags.")

    return OllamaDebugResponse(
        ollama_base=OLLAMA_BASE,
        ollama_path=ollama_path,
        api_reachable=api_reachable,
        installed_models=installed_models,
        running_models=running_models,
        default_model_choice=DEFAULT_MODEL_CHOICE,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Serve static frontend when available
# ---------------------------------------------------------------------------

if SERVE_STATIC_FRONTEND and _FRONTEND_DIR and _FRONTEND_DIR.exists():
    # Serve Next.js static assets (_next/*)
    _next_dir = _FRONTEND_DIR / "_next"
    if _next_dir.exists():
        app.mount("/_next", StaticFiles(directory=str(_next_dir)), name="next_assets")

    # Serve other static files from the frontend root (favicon, images, etc.)
    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        """Catch-all: serve static files or fall back to index.html for SPA routing."""
        file_path = _FRONTEND_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Fall back to index.html for client-side routing
        index = _FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"detail": "Not found"}
