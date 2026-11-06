import os
import io
import time
import zipfile
import asyncio
import pytest
from pathlib import Path
import pymupdf as fitz
from backend.job_manager import JobManager
from backend.bookmark_service import verify_bookmarks

def make_pdf_bytes(title: str = "Test Doc", pages: int = 2) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"{title} - Page {i+1}")
    b = doc.write()
    doc.close()
    return b

@pytest.mark.asyncio
async def test_multiple_pdfs_one_upload():
    """Test 5: Multiple PDFs in one upload."""
    mgr = JobManager()
    job = await mgr.get_or_create_job("job_multi_1")

    # Add 3 PDFs
    for i in range(3):
        content = make_pdf_bytes(f"BatchDoc_{i+1}")
        await mgr.add_file(job.job_id, f"BatchDoc_{i+1}.pdf", content)

    # Wait for queue to finish
    await job.queue.join()
    if job.worker_task:
        await job.worker_task

    summary = job.get_summary()
    assert summary["total_files"] == 3
    assert summary["completed_files"] == 3
    assert summary["failed_files"] == 0
    assert summary["overall_progress"] == 100

@pytest.mark.asyncio
async def test_add_more_files_while_processing():
    """Test 6: Adding more PDFs while the first batch is processing."""
    mgr = JobManager()
    job = await mgr.get_or_create_job("job_concurrency")

    # Upload first batch of 2 PDFs
    for i in range(2):
        content = make_pdf_bytes(f"InitialDoc_{i+1}")
        await mgr.add_file(job.job_id, f"InitialDoc_{i+1}.pdf", content)

    # Immediately add 2 more files while the first batch is in queue/processing
    for i in range(2):
        content = make_pdf_bytes(f"AddedDoc_{i+1}")
        await mgr.add_file(job.job_id, f"AddedDoc_{i+1}.pdf", content)

    # Total should be 4 files registered in the same job
    assert len(job.files) == 4

    # Wait for all 4 to complete
    await job.queue.join()
    if job.worker_task:
        await job.worker_task

    summary = job.get_summary()
    assert summary["total_files"] == 4
    assert summary["completed_files"] == 4
    assert summary["failed_files"] == 0

    # Ensure all original filenames are preserved in job
    filenames = [f["original_filename"] for f in summary["files"]]
    assert "InitialDoc_1.pdf" in filenames
    assert "InitialDoc_2.pdf" in filenames
    assert "AddedDoc_1.pdf" in filenames
    assert "AddedDoc_2.pdf" in filenames

@pytest.mark.asyncio
async def test_add_more_files_after_completion():
    """Test 7: Adding PDFs after an earlier batch has completed."""
    mgr = JobManager()
    job = await mgr.get_or_create_job("job_sequential")

    # First batch: 1 PDF
    c1 = make_pdf_bytes("DocBatchOne")
    await mgr.add_file(job.job_id, "DocBatchOne.pdf", c1)

    await job.queue.join()
    if job.worker_task:
        await job.worker_task

    summary1 = job.get_summary()
    assert summary1["total_files"] == 1
    assert summary1["completed_files"] == 1
    assert summary1["status"] == "completed"

    # Now add second batch: 2 more PDFs to the SAME job
    c2 = make_pdf_bytes("DocBatchTwo_A")
    c3 = make_pdf_bytes("DocBatchTwo_B")
    await mgr.add_file(job.job_id, "DocBatchTwo_A.pdf", c2)
    await mgr.add_file(job.job_id, "DocBatchTwo_B.pdf", c3)

    # First file should still be completed and present!
    assert "DocBatchOne.pdf" in [f.original_filename for f in job.files.values()]
    assert len(job.files) == 3

    # Wait for new batch to finish
    await job.queue.join()
    if job.worker_task:
        await job.worker_task

    summary2 = job.get_summary()
    assert summary2["total_files"] == 3
    assert summary2["completed_files"] == 3
    assert summary2["status"] == "completed"

@pytest.mark.asyncio
async def test_duplicate_filenames():
    """Test 8: Two files with the same filename."""
    mgr = JobManager()
    job = await mgr.get_or_create_job("job_dup")

    content1 = make_pdf_bytes("Content from first file", pages=2)
    content2 = make_pdf_bytes("Content from second distinct file", pages=3)

    # Both uploaded with exact same filename
    item1 = await mgr.add_file(job.job_id, "Agreement.pdf", content1)
    item2 = await mgr.add_file(job.job_id, "Agreement.pdf", content2)

    assert item1.file_id != item2.file_id
    assert len(job.files) == 2

    await job.queue.join()
    if job.worker_task:
        await job.worker_task

    # Both must succeed without collision
    assert item1.status == "completed"
    assert item2.status == "completed"
    assert Path(item1.processed_path).exists()
    assert Path(item2.processed_path).exists()
    assert item1.processed_path != item2.processed_path

    # Test 11: ZIP containing all successfully processed PDFs
    zip_path = await mgr.generate_zip(job.job_id)
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        # Both must be present in ZIP (one deduplicated like 'Agreement (1).pdf')
        assert len(names) == 2
        assert "Agreement.pdf" in names
        assert "Agreement (1).pdf" in names

@pytest.mark.asyncio
async def test_original_filenames_retained():
    """Test 13: Verify that output filenames retain the original names."""
    mgr = JobManager()
    job = await mgr.get_or_create_job("job_orig_names")

    test_name = "Legal Notice - Section 138 (Cheque Bounce).pdf"
    content = make_pdf_bytes("Cheque notice content")

    item = await mgr.add_file(job.job_id, test_name, content)
    await job.queue.join()
    if job.worker_task:
        await job.worker_task

    assert item.status == "completed"
    assert item.original_filename == test_name
    assert Path(item.processed_path).name == test_name

    # Download ZIP should retain test_name
    zip_path = await mgr.generate_zip(job.job_id)
    with zipfile.ZipFile(zip_path, "r") as z:
        assert test_name in z.namelist()
