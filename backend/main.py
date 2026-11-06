import os
import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import (
    APP_TITLE,
    APP_VERSION,
    BASE_DIR,
    HOST,
    PORT,
    MAX_UPLOAD_SIZE_BYTES,
)
from backend.job_manager import job_manager
from backend.ocr_service import check_ocr_tools_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pdf_ocr_pro")

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="High-performance searchable OCR and legal bookmarking system.",
)

# Enable CORS for flexible integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = BASE_DIR / "frontend"


# --- Frontend Endpoints ---
@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return FileResponse(index_file)


# --- System Health ---
@app.get("/health")
async def health_check():
    """System health and OCR tool availability."""
    ocr_tools = check_ocr_tools_status()
    return {
        "status": "online",
        "app": APP_TITLE,
        "version": APP_VERSION,
        "ocr_tools": ocr_tools,
    }


# --- Job Management Endpoints ---
@app.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job():
    """Create a new isolated job session."""
    job = await job_manager.get_or_create_job()
    return {
        "job_id": job.job_id,
        "message": "Job session created successfully.",
        "created_at": job.created_at,
    }


@app.post("/jobs/{job_id}/files")
async def add_files_to_job(
    job_id: str,
    files: List[UploadFile] = File(...),
    paths: Optional[str] = Form(None),
):
    """
    Add multiple PDFs to an existing or new job without losing earlier files.
    Accepts standard PDF uploads or folder uploads with relative paths.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    # Parse relative paths if provided (for folder upload)
    rel_paths: List[str] = []
    if paths:
        try:
            rel_paths = json.loads(paths)
        except Exception:
            rel_paths = []

    added_files = []
    rejected_files = []

    for index, upload_file in enumerate(files):
        filename = upload_file.filename or f"document_{index+1}.pdf"

        # Validate PDF extension
        if not filename.lower().endswith(".pdf"):
            rejected_files.append({"filename": filename, "reason": "Only PDF files are supported."})
            continue

        try:
            content = await upload_file.read()
            if len(content) > MAX_UPLOAD_SIZE_BYTES:
                rejected_files.append({
                    "filename": filename,
                    "reason": f"File exceeds maximum allowed size ({MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB).",
                })
                continue

            rel_path = rel_paths[index] if index < len(rel_paths) else filename
            file_item = await job_manager.add_file(
                job_id=job_id,
                filename=filename,
                file_bytes=content,
                relative_path=rel_path,
            )
            added_files.append(file_item.to_dict())

        except Exception as e:
            logger.error(f"Error saving uploaded file '{filename}': {e}")
            rejected_files.append({"filename": filename, "reason": str(e)})

    job = await job_manager.get_job(job_id)
    summary = job.get_summary() if job else {}

    return {
        "job_id": job_id,
        "added_count": len(added_files),
        "rejected_count": len(rejected_files),
        "rejected": rejected_files,
        "job_summary": summary,
    }


@app.post("/jobs/{job_id}/process")
async def start_job_processing(job_id: str):
    """Explicitly trigger or verify processing for a job."""
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    job_manager._ensure_worker_running(job)
    return {"job_id": job_id, "status": "processing"}


@app.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Return live status, progress bar %, duration, and per-file state."""
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    return job.get_summary()


@app.get("/jobs/{job_id}/files/{file_id}/download")
async def download_single_file(job_id: str, file_id: str):
    """Download an individual processed PDF with its original filename."""
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    file_item = job.files.get(file_id)
    if not file_item:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found in job.")

    if file_item.status != "completed" or not file_item.processed_path:
        raise HTTPException(
            status_code=400,
            detail=f"File '{file_item.original_filename}' is not completed yet (current status: {file_item.status}).",
        )

    file_path = Path(file_item.processed_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Processed file not found on disk.")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=file_item.original_filename,
    )


@app.get("/jobs/{job_id}/download-zip")
async def download_all_zip(job_id: str):
    """Package and download all successfully processed PDFs in one ZIP file."""
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    try:
        zip_path = await job_manager.generate_zip(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating ZIP for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ZIP package.")

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=zip_path.name,
    )


@app.post("/jobs/{job_id}/retry")
async def retry_failed_job_files(job_id: str):
    """Retry any failed PDFs in the job without re-processing completed ones."""
    try:
        count = await job_manager.retry_failed_files(job_id)
        return {"job_id": job_id, "retried_count": count, "message": f"Retrying {count} failed files."}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")


@app.post("/jobs/{job_id}/clear")
@app.delete("/jobs/{job_id}")
async def clear_job_data(job_id: str):
    """Safely clear all files and temporary data for a job."""
    cleared = await job_manager.clear_job(job_id)
    if not cleared:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {"job_id": job_id, "cleared": True, "message": "Job cleared successfully."}


# Mount static assets for frontend (CSS, JS, icons)
if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
