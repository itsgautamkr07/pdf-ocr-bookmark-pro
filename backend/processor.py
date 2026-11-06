import time
import logging
from pathlib import Path
from typing import Dict, Any, Callable, Optional
import pymupdf as fitz
from backend.ocr_service import perform_ocr
from backend.bookmark_service import apply_bookmarks
from backend.config import TEMP_DIR, PROCESSED_DIR

logger = logging.getLogger(__name__)


def validate_pdf(pdf_path: Path) -> int:
    """
    Validate that the file is a readable, non-empty PDF.
    Returns page count or raises ValueError.
    """
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise ValueError("File is empty or does not exist.")

    doc = None
    try:
        doc = fitz.open(str(pdf_path))
        if doc.is_encrypted:
            raise ValueError("PDF is encrypted or password-protected.")
        page_count = doc.page_count
        if page_count == 0:
            raise ValueError("PDF has 0 pages.")
        return page_count
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Corrupted or invalid PDF format: {str(e)}") from e
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


def process_single_pdf(
    input_path: Path,
    output_path: Path,
    job_id: str,
    file_id: str,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> Dict[str, Any]:
    """
    Full processing pipeline for one PDF:
    1. Validation
    2. OCR (searchable PDF generation)
    3. Exact bookmarking template
    4. Save to processed output destination

    Tracks exact start/end time and duration.
    """
    start_time = time.perf_counter()
    temp_ocr_path = TEMP_DIR / job_id / f"{file_id}_ocr_intermediate.pdf"
    temp_ocr_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Validation
        if progress_callback:
            progress_callback("validating", 10)
        page_count = validate_pdf(input_path)

        # Step 2: OCR with OCRmyPDF
        if progress_callback:
            progress_callback("ocr", 30)
        ocr_res = perform_ocr(
            input_pdf_path=input_path,
            output_pdf_path=temp_ocr_path,
        )

        if not temp_ocr_path.exists():
            raise RuntimeError("OCR failed to generate output PDF.")

        # Step 3: Bookmarking
        if progress_callback:
            progress_callback("bookmarking", 80)
        bm_res = apply_bookmarks(
            input_pdf_path=temp_ocr_path,
            output_pdf_path=output_path,
        )

        # Step 4: Final checks
        if not output_path.exists():
            raise RuntimeError("Failed to generate final bookmarked PDF.")

        duration = round(time.perf_counter() - start_time, 2)
        if progress_callback:
            progress_callback("completed", 100)

        logger.info(
            f"Successfully processed '{input_path.name}' in {duration}s "
            f"({page_count} pages, {bm_res['bookmarks_applied']} bookmarks)."
        )

        return {
            "success": True,
            "duration_seconds": duration,
            "page_count": page_count,
            "bookmarks_applied": bm_res["bookmarks_applied"],
            "output_path": str(output_path),
            "output_size": output_path.stat().st_size,
        }

    except Exception as e:
        duration = round(time.perf_counter() - start_time, 2)
        logger.error(f"Processing failed for '{input_path.name}' after {duration}s: {e}")
        raise

    finally:
        # Clean up intermediate temporary file
        if temp_ocr_path.exists():
            try:
                temp_ocr_path.unlink()
            except Exception as clean_err:
                logger.warning(f"Could not remove temp file {temp_ocr_path}: {clean_err}")
