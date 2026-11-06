import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import ocrmypdf
from backend.config import (
    OCR_LANGUAGE,
    OCR_SKIP_TEXT,
    OCR_OPTIMIZE,
    OCR_MAX_WORKERS,
    configure_windows_paths,
)

logger = logging.getLogger(__name__)

# Ensure Windows binaries are visible in PATH
configure_windows_paths()


def perform_ocr(
    input_pdf_path: str | Path,
    output_pdf_path: str | Path,
    language: Optional[str] = None,
    skip_text: Optional[bool] = None,
    optimize: Optional[int] = None,
    max_workers: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run OCRmyPDF on input_pdf_path and write searchable PDF to output_pdf_path.

    Settings:
    - language: default 'eng'
    - skip_text: if True, detects existing text and skips re-OCR on those pages
    - optimize: PDF optimization level (1 = fast and clean)
    - max_workers: CPU cores/processes to use
    """
    input_path = Path(input_pdf_path)
    output_path = Path(output_pdf_path)

    if not input_path.is_file():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    lang = language or OCR_LANGUAGE
    do_skip_text = skip_text if skip_text is not None else OCR_SKIP_TEXT
    opt = optimize if optimize is not None else OCR_OPTIMIZE
    workers = max_workers if max_workers is not None else OCR_MAX_WORKERS

    start_time = time.perf_counter()
    logger.info(f"Starting OCR on '{input_path.name}' (lang={lang}, workers={workers})")

    # Common OCRmyPDF execution arguments
    ocr_kwargs: Dict[str, Any] = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "language": lang,
        "skip_text": do_skip_text,
        "optimize": opt,
        "jobs": workers,
        "progress_bar": False,
        "output_type": "pdf",
        "invalidate_digital_signatures": True,
    }

    try:
        # Run OCRmyPDF
        exit_code = ocrmypdf.ocr(**ocr_kwargs)
        elapsed = time.perf_counter() - start_time

        logger.info(
            f"Completed OCR on '{input_path.name}' in {elapsed:.2f}s with exit_code {exit_code}"
        )

        return {
            "success": True,
            "elapsed_seconds": round(elapsed, 2),
            "output_path": str(output_path),
            "exit_code": exit_code,
        }

    except ocrmypdf.exceptions.PriorOcrFoundError:
        # File already contains text/OCR. If skip_text wasn't enough or flagged, retry with force or accept original.
        logger.warning(
            f"Prior OCR found in '{input_path.name}'. Re-running with redo_ocr=False / skip_text=True."
        )
        try:
            ocr_kwargs["redo_ocr"] = False
            ocr_kwargs["skip_text"] = True
            exit_code = ocrmypdf.ocr(**ocr_kwargs)
            elapsed = time.perf_counter() - start_time
            return {
                "success": True,
                "elapsed_seconds": round(elapsed, 2),
                "output_path": str(output_path),
                "exit_code": exit_code,
            }
        except Exception as retry_err:
            logger.error(f"Failed handling prior OCR for '{input_path.name}': {retry_err}")
            raise

    except ocrmypdf.exceptions.EncryptedPdfError:
        raise ValueError(f"PDF is password-protected or encrypted: '{input_path.name}'")

    except ocrmypdf.exceptions.InputFileError as e:
        raise ValueError(f"Corrupted or invalid PDF file: '{input_path.name}'. {e}")

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error(f"OCR failed for '{input_path.name}' after {elapsed:.2f}s: {e}")
        raise RuntimeError(f"OCR failed: {str(e)}") from e


def check_ocr_tools_status() -> Dict[str, Any]:
    """Check availability of Tesseract and Ghostscript for system health check."""
    status = {
        "tesseract_available": False,
        "tesseract_version": None,
        "ghostscript_available": False,
        "ghostscript_version": None,
    }

    # Check Tesseract
    try:
        import subprocess

        res = subprocess.run(
            ["tesseract", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            status["tesseract_available"] = True
            first_line = (res.stdout or res.stderr).splitlines()[0]
            status["tesseract_version"] = first_line.strip()
    except Exception as e:
        logger.debug(f"Tesseract check failed: {e}")

    # Check Ghostscript
    for gs_cmd in ["gswin64c", "gs"]:
        try:
            res = subprocess.run(
                [gs_cmd, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                status["ghostscript_available"] = True
                status["ghostscript_version"] = (res.stdout or "").strip()
                break
        except Exception:
            continue

    return status
