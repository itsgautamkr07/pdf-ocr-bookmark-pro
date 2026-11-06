import os
import pytest
from pathlib import Path
import pymupdf as fitz
from backend.bookmark_service import apply_bookmarks, verify_bookmarks, generate_toc_entries, BOOKMARK_POSITIONS, LAST_PAGE_BOOKMARK_TITLE

@pytest.fixture
def temp_pdf_dir(tmp_path):
    d = tmp_path / "bm_test"
    d.mkdir(parents=True, exist_ok=True)
    return d

def create_sample_pdf(path: Path, pages: int = 1, text: str = "Sample Page", existing_toc = None):
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 50), f"{text} - Page {i+1}")
    if existing_toc:
        doc.set_toc(existing_toc)
    doc.save(str(path))
    doc.close()
    return path

# Test 3: A PDF with fewer than 23 pages
def test_pdf_fewer_than_23_pages(temp_pdf_dir):
    input_pdf = temp_pdf_dir / "short_doc.pdf"
    output_pdf = temp_pdf_dir / "short_doc_out.pdf"
    create_sample_pdf(input_pdf, pages=5)

    res = apply_bookmarks(input_pdf, output_pdf)
    assert res["page_count"] == 5

    # Should have CIF (1), CHECK LIST (2), INDEX (3), MEMO OF PARTIES (4), SYNOPSIS (5)
    # Plus VAKALATNAMA on last page (5)
    assert res["bookmarks_applied"] == 6

    ver = verify_bookmarks(output_pdf)
    assert ver["valid"] is True
    assert ver["page_count"] == 5

    # Check toc contents
    doc = fitz.open(str(output_pdf))
    toc = doc.get_toc()
    doc.close()

    titles = [entry[1] for entry in toc]
    pages = [entry[2] for entry in toc]

    assert titles == ["CIF", "CHECK LIST", "INDEX", "MEMO OF PARTIES", "SYNOPSIS", "VAKALATNAMA"]
    assert pages == [1, 2, 3, 4, 5, 5]

    # Verify no bookmark points beyond page 5
    for p in pages:
        assert p <= 5

# Test 4: A PDF with at least 23 pages
def test_pdf_at_least_23_pages(temp_pdf_dir):
    input_pdf = temp_pdf_dir / "long_doc.pdf"
    output_pdf = temp_pdf_dir / "long_doc_out.pdf"
    create_sample_pdf(input_pdf, pages=25)

    res = apply_bookmarks(input_pdf, output_pdf)
    assert res["page_count"] == 25

    # All 13 bookmarks + VAKALATNAMA on page 25 = 14 bookmarks
    assert res["bookmarks_applied"] == 14

    ver = verify_bookmarks(output_pdf)
    assert ver["valid"] is True

    doc = fitz.open(str(output_pdf))
    toc = doc.get_toc()
    doc.close()

    titles = [entry[1] for entry in toc]
    assert titles[-1] == "VAKALATNAMA"
    assert toc[-1][2] == 25

    # Exactly 14 bookmarks
    assert len(toc) == 14

# Test 10: A PDF with existing bookmarks
def test_pdf_with_existing_bookmarks(temp_pdf_dir):
    input_pdf = temp_pdf_dir / "existing_bm.pdf"
    output_pdf = temp_pdf_dir / "existing_bm_out.pdf"

    # Create PDF with old random bookmarks
    old_toc = [
        [1, "Old Title 1", 1],
        [1, "Old Title 2", 2],
        [1, "Duplicate Vakalatnama", 2],
    ]
    create_sample_pdf(input_pdf, pages=10, existing_toc=old_toc)

    # Check initial doc has old toc
    doc_before = fitz.open(str(input_pdf))
    assert len(doc_before.get_toc()) == 3
    doc_before.close()

    # Apply standard bookmarks
    res = apply_bookmarks(input_pdf, output_pdf)

    # Check that old bookmarks were replaced
    doc_after = fitz.open(str(output_pdf))
    new_toc = doc_after.get_toc()
    doc_after.close()

    new_titles = [entry[1] for entry in new_toc]
    assert "Old Title 1" not in new_titles
    assert "Old Title 2" not in new_titles
    assert "Duplicate Vakalatnama" not in new_titles

    # Verify standard template is present
    assert "CIF" in new_titles
    assert "VAKALATNAMA" in new_titles

# Test 12: Verify that exactly one VAKALATNAMA bookmark exists in each output
@pytest.mark.parametrize("page_count", [1, 7, 22, 23, 30])
def test_exactly_one_vakalatnama(temp_pdf_dir, page_count):
    input_pdf = temp_pdf_dir / f"test_{page_count}pg.pdf"
    output_pdf = temp_pdf_dir / f"test_{page_count}pg_out.pdf"
    create_sample_pdf(input_pdf, pages=page_count)

    apply_bookmarks(input_pdf, output_pdf)

    ver = verify_bookmarks(output_pdf)
    assert ver["valid"] is True

    doc = fitz.open(str(output_pdf))
    toc = doc.get_toc()
    doc.close()

    vakalatnama_list = [entry for entry in toc if entry[1] == "VAKALATNAMA"]
    assert len(vakalatnama_list) == 1, f"Expected exactly 1 VAKALATNAMA, got {len(vakalatnama_list)}"
    assert vakalatnama_list[0][2] == page_count, f"VAKALATNAMA page is {vakalatnama_list[0][2]}, expected {page_count}"
