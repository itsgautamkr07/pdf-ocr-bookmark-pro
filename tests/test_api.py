import io
import pytest
from httpx import AsyncClient, ASGITransport
import pymupdf as fitz
from backend.main import app

def make_sample_pdf(text: str = "FastAPI Test PDF", pages: int = 1) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"{text} page {i+1}")
    b = doc.write()
    doc.close()
    return b

@pytest.mark.asyncio
async def test_health_check_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert "ocr_tools" in data

@pytest.mark.asyncio
async def test_create_job_and_upload_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create job
        res_job = await client.post("/jobs")
        assert res_job.status_code == 201
        job_data = res_job.json()
        job_id = job_data["job_id"]
        assert job_id is not None

        # Upload a valid PDF and an invalid text file
        pdf_bytes = make_sample_pdf("Invoice 101")
        files = [
            ("files", ("invoice.pdf", io.BytesIO(pdf_bytes), "application/pdf")),
            ("files", ("notes.txt", io.BytesIO(b"not a pdf"), "text/plain")),
        ]

        res_upload = await client.post(f"/jobs/{job_id}/files", files=files)
        assert res_upload.status_code == 200
        up_data = res_upload.json()
        assert up_data["added_count"] == 1
        assert up_data["rejected_count"] == 1
        assert up_data["rejected"][0]["filename"] == "notes.txt"

        # Check status
        res_status = await client.get(f"/jobs/{job_id}/status")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["total_files"] == 1

@pytest.mark.asyncio
async def test_download_endpoints_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create job
        res_job = await client.post("/jobs")
        job_id = res_job.json()["job_id"]

        pdf_bytes = make_sample_pdf("Contract Document", pages=2)
        files = [
            ("files", ("contract.pdf", io.BytesIO(pdf_bytes), "application/pdf")),
        ]
        await client.post(f"/jobs/{job_id}/files", files=files)

        # Wait for processing to complete
        import asyncio
        for _ in range(30):
            res = await client.get(f"/jobs/{job_id}/status")
            s = res.json()
            if s["completed_files"] == 1:
                break
            await asyncio.sleep(0.5)

        # Download individual file
        file_id = s["files"][0]["file_id"]
        dl_res = await client.get(f"/jobs/{job_id}/files/{file_id}/download")
        assert dl_res.status_code == 200
        assert "application/pdf" in dl_res.headers["content-type"]
        assert 'filename="contract.pdf"' in dl_res.headers.get("content-disposition", "")

        # Download ZIP
        zip_res = await client.get(f"/jobs/{job_id}/download-zip")
        assert zip_res.status_code == 200
        assert "application/zip" in zip_res.headers["content-type"]
        assert len(zip_res.content) > 0

        # Clear job
        clear_res = await client.post(f"/jobs/{job_id}/clear")
        assert clear_res.status_code == 200
        assert clear_res.json()["cleared"] is True

        # Verify job is cleared
        res_after = await client.get(f"/jobs/{job_id}/status")
        assert res_after.status_code == 404
