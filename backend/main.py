"""
SlideDrop Backend — FastAPI application.
Converts PPTX/PDF files into high-quality PNG images.
"""

import os
import shutil
import uuid
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
from utils.file_manager import (
    create_output_directory,
    create_temp_directory,
    cleanup_temp_directory,
    get_file_extension,
    is_supported_file,
)

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
        "http://127.0.0.1:3001"
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


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    job_id: str
    filename: str
    file_type: str
    page_count: int


class ConvertRequest(BaseModel):
    job_id: str
    output_folder: Optional[str] = None


class ConvertResponse(BaseModel):
    job_id: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    state: str  # "pending" | "converting" | "done" | "error"
    current_slide: int
    total_slides: int
    output_folder: Optional[str] = None
    error: Optional[str] = None


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

    # Store job info
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "filename": file.filename,
        "file_type": ext,
        "temp_dir": temp_dir,
        "saved_path": saved_path,
        "pdf_path": pdf_path,
        "page_count": page_count,
        "state": "pending",
        "current_slide": 0,
        "total_slides": page_count,
        "output_folder": None,
        "error": None,
    }

    return UploadResponse(
        job_id=job_id,
        filename=file.filename,
        file_type=ext,
        page_count=page_count,
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

            job["state"] = "done"

        except Exception as e:
            job["state"] = "error"
            job["error"] = str(e)

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
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
