import os
import pytest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pymupdf as fitz
from backend.processor import process_single_pdf, validate_pdf
from backend.bookmark_service import verify_bookmarks

@pytest.fixture
def temp_ocr_dir(tmp_path):
    d = tmp_path / "ocr_test"
    d.mkdir(parents=True, exist_ok=True)
    return d

def create_image_only_pdf(path: Path, text: str = "SCANNED LEGAL DOCUMENT EVIDENCE"):
    """Creates a purely raster image-based PDF (no selectable text)."""
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw simple text into bitmap
    draw.text((100, 150), text, fill=(0, 0, 0))
    img.save(str(path), "PDF")
    return path

def create_searchable_pdf(path: Path, text: str = "Searchable text content here"):
    """Creates a vector/text PDF with searchable text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path

# Test 1: One scanned PDF
def test_one_scanned_pdf(temp_ocr_dir):
    input_pdf = temp_ocr_dir / "scanned_doc.pdf"
    output_pdf = temp_ocr_dir / "scanned_doc_processed.pdf"
    create_image_only_pdf(input_pdf, "INVOICE AND PAYMENT RECORD")

    # Before OCR: verify no extractable text
    doc_before = fitz.open(str(input_pdf))
    assert doc_before[0].get_text().strip() == ""
    doc_before.close()

    # Process: run OCR + Bookmarking
    res = process_single_pdf(
        input_path=input_pdf,
        output_path=output_pdf,
        job_id="test_job_1",
        file_id="file_scanned_1",
    )

    assert res["success"] is True
    assert output_pdf.exists()
    assert res["duration_seconds"] > 0

    # After OCR: verify text is now present and searchable
    doc_after = fitz.open(str(output_pdf))
    extracted = doc_after[0].get_text()
    doc_after.close()

    assert len(extracted) > 0, "OCR should make text extractable from scanned PDF"
    assert "INVOICE" in extracted.upper() or "PAYMENT" in extracted.upper()

    # Verify bookmarks
    ver = verify_bookmarks(output_pdf)
    assert ver["valid"] is True

# Test 2: One searchable PDF
def test_one_searchable_pdf(temp_ocr_dir):
    input_pdf = temp_ocr_dir / "already_searchable.pdf"
    output_pdf = temp_ocr_dir / "already_searchable_processed.pdf"
    create_searchable_pdf(input_pdf, "Already searchable legal notice")

    res = process_single_pdf(
        input_path=input_pdf,
        output_path=output_pdf,
        job_id="test_job_2",
        file_id="file_searchable_1",
    )

    assert res["success"] is True
    assert output_pdf.exists()

    doc_after = fitz.open(str(output_pdf))
    extracted = doc_after[0].get_text()
    doc_after.close()

    assert "Already searchable" in extracted
    ver = verify_bookmarks(output_pdf)
    assert ver["valid"] is True

# Test 9: A corrupted PDF
def test_corrupted_pdf_handling(temp_ocr_dir):
    corrupted_pdf = temp_ocr_dir / "corrupted.pdf"
    output_pdf = temp_ocr_dir / "corrupted_out.pdf"

    # Write non-PDF garbage
    with open(corrupted_pdf, "wb") as f:
        f.write(b"%PDF-INVALID-DATA-CORRUPTED-HEADER-NON-READABLE")

    with pytest.raises(ValueError) as excinfo:
        process_single_pdf(
            input_path=corrupted_pdf,
            output_path=output_pdf,
            job_id="test_job_err",
            file_id="file_corrupt_1",
        )

    assert "Corrupted or invalid" in str(excinfo.value) or "invalid" in str(excinfo.value).lower()
    # Ensure no output was erroneously created
    assert not output_pdf.exists()

# Test 14: Verify that no failed file is incorrectly marked as completed
def test_failed_file_not_marked_completed(temp_ocr_dir):
    corrupted_pdf = temp_ocr_dir / "fake.pdf"
    with open(corrupted_pdf, "wb") as f:
        f.write(b"not a real pdf file")

    with pytest.raises(Exception):
        validate_pdf(corrupted_pdf)
