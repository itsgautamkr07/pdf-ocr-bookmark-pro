import os
import time
import uuid
import shutil
import asyncio
import zipfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from backend.config import UPLOADS_DIR, PROCESSED_DIR, TEMP_DIR, ZIPS_DIR
from backend.processor import process_single_pdf

logger = logging.getLogger(__name__)


@dataclass
class FileItem:
    file_id: str
    original_filename: str
    relative_path: str
    size_bytes: int
    input_path: str
    processed_path: Optional[str] = None
    status: str = "pending"  # "pending", "processing", "completed", "failed"
    stage: str = "queued"    # "queued", "validating", "ocr", "bookmarking", "completed", "failed"
    progress: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    page_count: Optional[int] = None
    bookmarks_applied: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # If currently processing, compute live elapsed time for frontend
        if self.status == "processing" and self.start_time:
            d["duration_seconds"] = round(time.time() - self.start_time, 2)
        return d


class Job:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.created_at = time.time()
        self.updated_at = time.time()
        self.status = "idle"  # "idle", "processing", "completed", "partially_completed", "failed"
        self.files: Dict[str, FileItem] = {}
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self.lock = asyncio.Lock()

        # Job specific directories
        self.upload_dir = UPLOADS_DIR / job_id
        self.processed_dir = PROCESSED_DIR / job_id
        self.temp_dir = TEMP_DIR / job_id
        self.zip_dir = ZIPS_DIR / job_id

        for d in [self.upload_dir, self.processed_dir, self.temp_dir, self.zip_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.files)
        pending = sum(1 for f in self.files.values() if f.status == "pending")
        processing = sum(1 for f in self.files.values() if f.status == "processing")
        completed = sum(1 for f in self.files.values() if f.status == "completed")
        failed = sum(1 for f in self.files.values() if f.status == "failed")

        # Determine overall job status
        if processing > 0:
            effective_status = "processing"
        elif pending > 0:
            effective_status = "queued"
        elif total == 0:
            effective_status = "idle"
        elif failed > 0 and completed > 0:
            effective_status = "partially_completed"
        elif failed > 0 and completed == 0:
            effective_status = "failed"
        elif completed == total:
            effective_status = "completed"
        else:
            effective_status = self.status

        # Calculate overall progress
        if total == 0:
            overall_progress = 0
        else:
            done_count = completed + failed
            overall_progress = int((done_count / total) * 100)

        # Total processing time across completed/failed files
        total_duration = sum(f.duration_seconds for f in self.files.values())

        return {
            "job_id": self.job_id,
            "status": effective_status,
            "total_files": total,
            "pending_files": pending,
            "processing_files": processing,
            "completed_files": completed,
            "failed_files": failed,
            "overall_progress": overall_progress,
            "total_duration_seconds": round(total_duration, 2),
            "files": [f.to_dict() for f in self.files.values()],
        }


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_job(self, job_id: Optional[str] = None) -> Job:
        async with self._lock:
            if not job_id:
                job_id = str(uuid.uuid4())

            if job_id not in self._jobs:
                self._jobs[job_id] = Job(job_id)
                logger.info(f"Created new job session: {job_id}")

            return self._jobs[job_id]

    async def get_job(self, job_id: str) -> Optional[Job]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def add_file(
        self,
        job_id: str,
        filename: str,
        file_bytes: bytes,
        relative_path: Optional[str] = None,
    ) -> FileItem:
        """
        Add a PDF to an existing or new job without touching previously uploaded files.
        File is safely saved to its own isolated subfolder.
        """
        job = await self.get_or_create_job(job_id)

        file_id = str(uuid.uuid4())
        safe_filename = Path(filename).name
        # Keep relative path if provided for folder uploads
        rel_path = relative_path.strip("/\\") if relative_path else safe_filename

        # Write to uploads/{job_id}/{file_id}/{safe_filename}
        file_upload_dir = job.upload_dir / file_id
        file_upload_dir.mkdir(parents=True, exist_ok=True)
        input_file_path = file_upload_dir / safe_filename

        with open(input_file_path, "wb") as f:
            f.write(file_bytes)

        file_item = FileItem(
            file_id=file_id,
            original_filename=safe_filename,
            relative_path=rel_path,
            size_bytes=len(file_bytes),
            input_path=str(input_file_path),
            status="pending",
            stage="queued",
            progress=0,
        )

        async with job.lock:
            job.files[file_id] = file_item
            job.updated_at = time.time()
            await job.queue.put(file_id)

        # Trigger worker if not already running
        self._ensure_worker_running(job)

        return file_item

    def _ensure_worker_running(self, job: Job):
        """Starts background worker task if it's not active."""
        if job.worker_task is None or job.worker_task.done():
            job.worker_task = asyncio.create_task(self._job_worker(job))
            logger.info(f"Launched worker task for job {job.job_id}")

    async def _job_worker(self, job: Job):
        """
        Background worker that drains job.queue.
        Seamlessly continues when more files are added!
        """
        job.status = "processing"
        logger.info(f"Worker started processing queue for job {job.job_id}")

        while True:
            try:
                # Wait for up to 1 second for a new item. If empty, exit loop.
                file_id = await asyncio.wait_for(job.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # Check if queue is still empty
                if job.queue.empty():
                    break
                continue

            file_item = job.files.get(file_id)
            if not file_item:
                job.queue.task_done()
                continue

            # Process this file
            file_item.status = "processing"
            file_item.stage = "validating"
            file_item.progress = 10
            file_item.start_time = time.time()

            # Output path: processed/{job_id}/{file_id}/{safe_filename}
            output_file_dir = job.processed_dir / file_id
            output_file_dir.mkdir(parents=True, exist_ok=True)
            output_file_path = output_file_dir / file_item.original_filename

            def progress_callback(stage: str, percent: int):
                file_item.stage = stage
                file_item.progress = percent

            try:
                # Run CPU/Disk intensive OCR and bookmarking in thread pool
                result = await asyncio.to_thread(
                    process_single_pdf,
                    input_path=Path(file_item.input_path),
                    output_path=output_file_path,
                    job_id=job.job_id,
                    file_id=file_id,
                    progress_callback=progress_callback,
                )

                file_item.end_time = time.time()
                file_item.duration_seconds = result["duration_seconds"]
                file_item.processed_path = str(output_file_path)
                file_item.page_count = result.get("page_count")
                file_item.bookmarks_applied = result.get("bookmarks_applied")
                file_item.status = "completed"
                file_item.stage = "completed"
                file_item.progress = 100
                file_item.error_message = None

                logger.info(
                    f"Job {job.job_id}: Successfully processed {file_item.original_filename} "
                    f"in {file_item.duration_seconds}s"
                )

            except Exception as e:
                file_item.end_time = time.time()
                elapsed = file_item.end_time - (file_item.start_time or file_item.end_time)
                file_item.duration_seconds = round(max(0.01, elapsed), 2)
                file_item.status = "failed"
                file_item.stage = "failed"
                file_item.error_message = str(e)
                logger.error(
                    f"Job {job.job_id}: Failed processing {file_item.original_filename} "
                    f"after {file_item.duration_seconds}s: {e}"
                )

            finally:
                job.queue.task_done()
                job.updated_at = time.time()

        # Update final job state
        has_failed = any(f.status == "failed" for f in job.files.values())
        has_completed = any(f.status == "completed" for f in job.files.values())

        if has_failed and has_completed:
            job.status = "partially_completed"
        elif has_failed and not has_completed:
            job.status = "failed"
        elif has_completed:
            job.status = "completed"
        else:
            job.status = "idle"

        logger.info(f"Worker finished processing for job {job.job_id}. Status: {job.status}")

    async def retry_failed_files(self, job_id: str) -> int:
        """
        Re-enqueue any failed files in this job.
        Completed files remain intact!
        """
        job = await self.get_job(job_id)
        if not job:
            raise KeyError(f"Job {job_id} not found.")

        retried_count = 0
        async with job.lock:
            for file_item in job.files.values():
                if file_item.status == "failed":
                    file_item.status = "pending"
                    file_item.stage = "queued"
                    file_item.progress = 0
                    file_item.error_message = None
                    file_item.start_time = None
                    file_item.end_time = None
                    file_item.duration_seconds = 0.0
                    await job.queue.put(file_item.file_id)
                    retried_count += 1

        if retried_count > 0:
            self._ensure_worker_running(job)

        return retried_count

    async def generate_zip(self, job_id: str) -> Path:
        """
        Creates a single ZIP file containing ALL successfully processed PDFs in this job.
        Preserves folder structures when uploaded as folder, or disambiguates duplicate filenames.
        """
        job = await self.get_job(job_id)
        if not job:
            raise KeyError(f"Job {job_id} not found.")

        completed_files = [f for f in job.files.values() if f.status == "completed" and f.processed_path]
        if not completed_files:
            raise ValueError("No successfully completed files to package into ZIP.")

        zip_filename = f"PDF_OCR_BOOKMARKED_{job_id[:8]}.zip"
        zip_path = job.zip_dir / zip_filename

        # Remove previous zip if exists
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass

        # Track archive filenames to avoid collisions
        seen_arc_names: Dict[str, int] = {}

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for item in completed_files:
                file_on_disk = Path(item.processed_path)
                if not file_on_disk.is_file():
                    continue

                # Use relative path if distinct, else filename
                base_name = item.relative_path if item.relative_path else item.original_filename
                p = Path(base_name)
                stem = p.stem
                suffix = p.suffix
                parent_dir = str(p.parent) if p.parent != Path(".") else ""

                clean_name = f"{parent_dir}/{p.name}".strip("/") if parent_dir else p.name

                if clean_name in seen_arc_names:
                    seen_arc_names[clean_name] += 1
                    dedup_name = f"{stem} ({seen_arc_names[clean_name]}){suffix}"
                    arc_name = f"{parent_dir}/{dedup_name}".strip("/") if parent_dir else dedup_name
                else:
                    seen_arc_names[clean_name] = 0
                    arc_name = clean_name

                zipf.write(file_on_disk, arcname=arc_name)

        return zip_path

    async def clear_job(self, job_id: str) -> bool:
        """Safely clear job data and directories."""
        job = await self.get_job(job_id)
        if not job:
            return False

        # Cancel worker if running
        if job.worker_task and not job.worker_task.done():
            job.worker_task.cancel()

        # Delete job directories
        for d in [job.upload_dir, job.processed_dir, job.temp_dir, job.zip_dir]:
            if d.exists():
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Error removing {d}: {e}")

        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]

        return True


# Global singleton instance
job_manager = JobManager()
