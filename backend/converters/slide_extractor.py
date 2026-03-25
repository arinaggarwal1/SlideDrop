"""
Slide text extraction using Qwen2.5-VL via Ollama.
Sends each slide image individually to the selected vision-language model
and compiles a detailed lecture transcript.

Ollama is started on-demand and stopped when extraction finishes.
"""

import asyncio
import base64
import io
import logging
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.environ.get("SLIDEDROP_OLLAMA_HOST", "127.0.0.1:11434")
OLLAMA_BASE = f"http://{OLLAMA_HOST}"
OLLAMA_URL = f"{OLLAMA_BASE}/api/generate"
MODEL_TIMEOUT_SECONDS = float(os.environ.get("SLIDEDROP_MODEL_TIMEOUT_SECONDS", "120"))
MODEL_MAX_TOKENS = int(os.environ.get("SLIDEDROP_MODEL_MAX_TOKENS", "1600"))
MAX_IMAGE_DIMENSION = int(os.environ.get("SLIDEDROP_MAX_IMAGE_DIMENSION", "1280"))
MODEL_CHOICES = {
    "3b": "qwen2.5vl:3b",
    "7b": "qwen2.5vl:7b",
}

DEFAULT_MODEL_CHOICE = (
    "3b"
    if platform.system() == "Darwin" and platform.machine() == "arm64"
    else "7b"
)

# Track the Ollama process so we can stop it after extraction
_ollama_process: Optional[subprocess.Popen] = None
_extraction_lock = threading.Lock()


def _find_ollama_bin() -> str:
    """Find the ollama binary."""
    found = shutil.which("ollama")
    if found:
        return found
    # Common Homebrew locations
    for p in ["/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"]:
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("Ollama is not installed. Install with: brew install ollama")


def _is_ollama_running() -> bool:
    """Check if Ollama API is reachable."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def _start_ollama() -> bool:
    """Start Ollama serve process on demand."""
    global _ollama_process

    if _is_ollama_running():
        logger.info("Ollama is already running")
        return False

    ollama_bin = _find_ollama_bin()
    logger.info(f"Starting Ollama: {ollama_bin} serve")
    _ollama_process = subprocess.Popen(
        [ollama_bin, "serve"],
        env={
            **os.environ,
            "OLLAMA_HOST": OLLAMA_HOST,
            "OLLAMA_NUM_PARALLEL": "1",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for it to be ready (up to 15 seconds)
    for _ in range(30):
        time.sleep(0.5)
        if _is_ollama_running():
            logger.info("Ollama is ready")
            return True

    raise RuntimeError("Ollama failed to start within 15 seconds")


def _stop_ollama():
    """Stop the Ollama process we started (if we started it)."""
    global _ollama_process
    if _ollama_process is not None:
        logger.info("Stopping Ollama")
        try:
            _ollama_process.terminate()
            _ollama_process.wait(timeout=5)
        except Exception:
            try:
                _ollama_process.kill()
            except Exception:
                pass
        _ollama_process = None


def normalize_model_choice(model_choice: Optional[str]) -> str:
    """Validate and normalize a requested model choice."""
    if not model_choice:
        return DEFAULT_MODEL_CHOICE

    normalized = model_choice.strip().lower()
    if normalized not in MODEL_CHOICES:
        allowed = ", ".join(sorted(MODEL_CHOICES))
        raise ValueError(f"Unsupported model choice '{model_choice}'. Allowed values: {allowed}")
    return normalized


def get_model_name(model_choice: Optional[str]) -> str:
    """Return the Ollama model name for a validated choice."""
    return MODEL_CHOICES[normalize_model_choice(model_choice)]


def list_slide_images(slide_dir: str) -> list[Path]:
    """Return slide images in numeric order for a converted deck."""
    return _get_sorted_slides(slide_dir)


def _ensure_model_available(model_name: str):
    """Check if the model is pulled, pull it if not."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            if any(model_name in m for m in models):
                logger.info(f"Model {model_name} is available")
                return

        logger.info(f"Pulling model {model_name}...")
        ollama_bin = _find_ollama_bin()
        result = subprocess.run(
            [ollama_bin, "pull", model_name],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout for pull
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to pull model: {result.stderr}")
        logger.info(f"Model {model_name} pulled successfully")
    except httpx.HTTPError as e:
        raise RuntimeError(f"Cannot reach Ollama API: {e}")


def _list_running_models() -> list[str]:
    """Return models currently loaded in the SlideDrop Ollama instance."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
        resp.raise_for_status()
        return [
            model.get("name", "")
            for model in resp.json().get("models", [])
            if model.get("name")
        ]
    except Exception:
        return []


def _clear_loaded_models():
    """Unload any models currently held by the SlideDrop Ollama instance."""
    ollama_bin = _find_ollama_bin()
    running_models = _list_running_models()

    for running_model in running_models:
        subprocess.run(
            [ollama_bin, "stop", running_model],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "OLLAMA_HOST": OLLAMA_HOST},
        )

    # Give Ollama a short moment to release memory before loading another model.
    if running_models:
        time.sleep(1)


EXTRACTION_PROMPT_TEMPLATE = """You are my lecture extraction engine.

You are processing ONE slide image only.
Slide number for this image: {slide_number}

CRITICAL RULES
1) Do NOT summarize, shorten, or simplify.
2) Do NOT add outside knowledge.
3) Preserve exact wording, symbols, and terminology from the slide.
4) Extract instructional content in extreme detail so this can be used by another AI that cannot view images.

IMAGE / GRAPH RULES
1) Extract ALL visible text using OCR.
2) If the slide has screenshots, diagrams, handwriting, or scanned content, transcribe every readable word.
3) For graphs/charts, describe:
   Type, Title, Axis labels, Units, Scale, Range, Trend direction, and the specific comparison/conclusion shown.
4) Do not write generic phrases like "the graph shows...". Be precise about visible values and patterns.

EQUATION RULES
For every equation:
1) Reproduce it exactly in plain text.
2) Define every variable and symbol shown.
3) State assumptions shown on the slide.
4) Walk through any step-by-step application shown on the slide.

OUTPUT FORMAT (MANDATORY STRUCTURE)
Use this exact structure:

Slide {slide_number}: [Exact Slide Title]

1) FULL RAW TEXT
All bullets, sub-bullets, footnotes, labels, and OCR text from images.

2) CONCEPTS INTRODUCED
Term:
Definition: (as shown or directly implied by the slide)
Context/Importance:

3) EQUATIONS (if any)
Exact equation:
Variable glossary:
Interpretation & Application:

4) FIGURES / GRAPHS / TABLES (if any)
Type:
Full visual description: (Values, patterns, and intended takeaway)

5) EXAMPLES / APPLICATIONS (if any)
Problem & Results: (Steps shown on the slide)

If a section is absent, write "Not present" for that section."""


def _get_sorted_slides(slide_dir: str) -> list[Path]:
    """Scan a directory for slide images and return them in numeric order."""
    slide_path = Path(slide_dir)
    slide_files = list(slide_path.glob("slide_*.png"))

    def sort_key(p: Path) -> int:
        match = re.search(r"slide_(\d+)", p.stem)
        return int(match.group(1)) if match else 0

    slide_files.sort(key=sort_key)
    return slide_files


def _encode_image(image_path: Path) -> str:
    """Read and downscale an image file, then return its base64-encoded PNG."""
    try:
        with Image.open(image_path) as img:
            # RGB avoids palette/mode incompatibilities in some model runtimes.
            img = img.convert("RGB")
            if max(img.width, img.height) > MAX_IMAGE_DIMENSION:
                img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        # Fallback to raw file bytes if PIL processing fails for any reason.
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


async def _extract_single_slide(
    image_path: Path,
    slide_number: int,
    client: httpx.AsyncClient,
    model_name: str,
) -> str:
    """
    Send a single slide to the Ollama vision model and return the response text.
    Retries once on failure; returns a placeholder if both attempts fail.
    """
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(slide_number=slide_number)
    image_b64 = _encode_image(image_path)

    payload = {
        "model": model_name,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": MODEL_MAX_TOKENS,
        },
    }

    for attempt in range(2):
        try:
            logger.info(f"Slide {slide_number}: sending to model (attempt {attempt + 1})")
            start = time.perf_counter()
            response = await client.post(
                OLLAMA_URL,
                json=payload,
                timeout=MODEL_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            text = data.get("response", "")
            elapsed = time.perf_counter() - start
            logger.info(f"Slide {slide_number}: got {len(text)} chars in {elapsed:.1f}s")
            return text
        except Exception as e:
            logger.warning(f"Slide {slide_number}: attempt {attempt + 1} failed: {e}")
            if attempt == 0:
                await asyncio.sleep(2)
                continue
            return f"Slide {slide_number}\nExtraction failed after retry.\nError: {e}"

    return f"Slide {slide_number}\nExtraction failed.\n"


async def run_extraction(
    slide_dir: str,
    output_path: str,
    parallelism: int = 4,
    model_choice: Optional[str] = None,
    on_progress: Optional[Callable[[int, int, int], None]] = None,
    on_status: Optional[Callable[[str, str], None]] = None,
) -> str:
    """
    Run the extraction pipeline on all slides in a directory.

    Args:
        slide_dir: Directory containing slide_NNN.png files.
        output_path: Path to write the lecture_extraction.txt file.
        parallelism: Max concurrent model requests (1-8).
        model_choice: Selected Qwen2.5-VL size ("3b" or "7b").
        on_progress: Callback(current_completed, total, active_jobs).
        on_status: Callback(stage, message) for detailed debug reporting.

    Returns:
        Path to the output transcript file.
    """
    # Start Ollama on demand
    model_name = get_model_name(model_choice)

    # Prevent overlapping extraction runs from contending for Ollama.
    acquired_slot = _extraction_lock.acquire(blocking=False)
    if not acquired_slot:
        if on_status:
            on_status(
                "waiting_for_slot",
                "Another extraction is already using Ollama. Waiting for available slot.",
            )
        _extraction_lock.acquire()

    if on_status:
        on_status("initializing", f"Preparing extraction with {model_name}")

    started_ollama_here = False
    try:
        if on_status:
            on_status("starting_ollama", "Checking Ollama service")
        started_ollama_here = _start_ollama()
        if on_status:
            on_status("clearing_models", "Clearing previously loaded models")
        _clear_loaded_models()
        if on_status:
            on_status("checking_model", f"Ensuring {model_name} is available")
        _ensure_model_available(model_name)
    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        raise

    try:
        return await _do_extraction(
            slide_dir,
            output_path,
            parallelism,
            model_name,
            on_progress,
            on_status,
        )
    finally:
        # Stop Ollama only when this run started it.
        if started_ollama_here:
            _stop_ollama()
        _extraction_lock.release()


async def _do_extraction(
    slide_dir: str,
    output_path: str,
    parallelism: int,
    model_name: str,
    on_progress: Optional[Callable[[int, int, int], None]],
    on_status: Optional[Callable[[str, str], None]],
) -> str:
    """Internal extraction logic."""
    slides = _get_sorted_slides(slide_dir)
    total = len(slides)
    logger.info(f"Found {total} slides in {slide_dir}")
    if on_status:
        on_status("scanning_slides", f"Found {total} slide image(s)")

    if total == 0:
        Path(output_path).write_text("No slides found for extraction.\n")
        return output_path

    # Results dict keyed by slide number for order preservation
    results: dict[int, str] = {}
    completed = 0
    active = 0
    semaphore = asyncio.Semaphore(parallelism)
    lock = asyncio.Lock()

    # Report initial progress
    if on_progress:
        on_progress(0, total, 0)

    async def process_slide(image_path: Path, slide_num: int):
        nonlocal completed, active
        async with semaphore:
            async with lock:
                active += 1
                if on_progress:
                    on_progress(completed, total, active)
                if on_status:
                    on_status(
                        "running_model",
                        f"Sending slide {slide_num} to {model_name} ({active} active job(s))",
                    )

            try:
                async with httpx.AsyncClient() as client:
                    slide_start = time.perf_counter()
                    task = asyncio.create_task(
                        _extract_single_slide(
                            image_path,
                            slide_num,
                            client,
                            model_name,
                        )
                    )

                    # Heartbeat so the UI log shows forward motion on slow slides.
                    while not task.done():
                        done, _ = await asyncio.wait({task}, timeout=15)
                        if done:
                            break
                        if on_status:
                            elapsed = int(time.perf_counter() - slide_start)
                            on_status(
                                "running_model",
                                f"Slide {slide_num} still processing with {model_name} ({elapsed}s elapsed)",
                            )

                    text = await task
                results[slide_num] = text
            except Exception as e:
                logger.error(f"Slide {slide_num}: unexpected error: {e}")
                results[slide_num] = f"Slide {slide_num}\nExtraction failed.\nError: {e}"

            async with lock:
                active -= 1
                completed += 1
                if on_progress:
                    on_progress(completed, total, active)
                if on_status:
                    on_status(
                        "progress",
                        f"Completed slide {slide_num}. {completed}/{total} processed",
                    )

    # Launch all tasks (semaphore limits concurrency)
    tasks = []
    for slide_path in slides:
        match = re.search(r"slide_(\d+)", slide_path.stem)
        slide_num = int(match.group(1)) if match else 0
        tasks.append(asyncio.create_task(process_slide(slide_path, slide_num)))

    await asyncio.gather(*tasks)

    # Write transcript in slide order
    out = Path(output_path)
    with open(out, "w", encoding="utf-8") as f:
        for slide_path in slides:
            match = re.search(r"slide_(\d+)", slide_path.stem)
            slide_num = int(match.group(1)) if match else 0
            text = results.get(slide_num, f"Slide {slide_num}\nExtraction failed.\n")
            f.write(text.strip())
            f.write("\n\n" + "=" * 80 + "\n\n")

    logger.info(f"Transcript written to {out}")
    return str(out)
