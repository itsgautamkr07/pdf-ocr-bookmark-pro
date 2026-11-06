import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any
import pymupdf as fitz

logger = logging.getLogger(__name__)

# Exact 13 standard bookmark positions (page numbers 1-based)
BOOKMARK_POSITIONS: List[Tuple[int, str]] = [
    (1, "CIF"),
    (2, "CHECK LIST"),
    (3, "INDEX"),
    (4, "MEMO OF PARTIES"),
    (5, "SYNOPSIS"),
    (7, "COMPLAINT UNDER SECTION 25(1)"),
    (12, "COMPLAINT EVIDENCE"),
    (16, "LIST OF DOCUMENTS & WITNESS"),
    (17, "SPA"),
    (18, "AUTO DEBIT FORM"),
    (19, "AUTO DEBIT RETURN MEMO"),
    (22, "NOTICE"),
    (23, "TRACKING REPORT"),
]

LAST_PAGE_BOOKMARK_TITLE = "VAKALATNAMA"


def generate_toc_entries(page_count: int) -> List[List[Any]]:
    """
    Build the exact TOC according to the specification:
    - PDF pages numbered starting at 1.
    - Add bookmark only if its page number exists in the PDF (page <= page_count).
    - Always add exactly ONE VAKALATNAMA bookmark pointing to the last page.
    - Do not add VAKALATNAMA twice.
    - Do not add bookmarks to pages that do not exist.
    """
    if page_count <= 0:
        return []

    toc: List[List[Any]] = []

    # 1. Add all standard bookmarks whose page <= page_count
    for page_num, title in BOOKMARK_POSITIONS:
        if page_num <= page_count:
            # PyMuPDF TOC entry: [hierarchy_level, title, page_number]
            toc.append([1, title, page_num])

    # 2. Add exactly ONE VAKALATNAMA pointing to page_count
    # Verify VAKALATNAMA is not already in toc (BOOKMARK_POSITIONS does not contain it)
    toc.append([1, LAST_PAGE_BOOKMARK_TITLE, page_count])

    return toc


def apply_bookmarks(input_pdf_path: str | Path, output_pdf_path: str | Path) -> Dict[str, Any]:
    """
    Reads input PDF, wipes existing TOC, applies exact bookmark template,
    and saves to output path with garbage=4 and deflate=True.
    """
    input_path = Path(input_pdf_path)
    output_path = Path(output_pdf_path)

    if not input_path.is_file():
        raise FileNotFoundError(f"Source PDF file not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = None
    try:
        doc = fitz.open(str(input_path))
        page_count = doc.page_count

        if page_count == 0:
            raise ValueError("PDF has 0 pages, cannot apply bookmarks.")

        toc = generate_toc_entries(page_count)

        # doc.set_toc replaces all existing bookmarks cleanly
        doc.set_toc(toc)

        # Save with optimization flags requested
        doc.save(str(output_path), garbage=4, deflate=True)

        logger.info(
            f"Successfully applied {len(toc)} bookmarks to '{output_path.name}' "
            f"({page_count} pages)."
        )

        return {
            "page_count": page_count,
            "bookmarks_applied": len(toc),
            "bookmarks": [{"level": item[0], "title": item[1], "page": item[2]} for item in toc],
        }

    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception as e:
                logger.warning(f"Error closing PyMuPDF document: {e}")


def verify_bookmarks(pdf_path: str | Path) -> Dict[str, Any]:
    """
    Verify bookmarks in a processed PDF against the required template rules:
    1. All bookmark pages <= page_count.
    2. Exactly one VAKALATNAMA bookmark pointing to the last page.
    3. No duplicate bookmarks for the same title on the same page.
    """
    path = Path(pdf_path)
    if not path.is_file():
        return {"valid": False, "error": f"File not found: {path}"}

    doc = None
    try:
        doc = fitz.open(str(path))
        page_count = doc.page_count
        toc = doc.get_toc()

        # Count VAKALATNAMA
        vakalatnama_entries = [entry for entry in toc if entry[1] == LAST_PAGE_BOOKMARK_TITLE]
        if len(vakalatnama_entries) != 1:
            return {
                "valid": False,
                "error": f"Expected exactly 1 '{LAST_PAGE_BOOKMARK_TITLE}' bookmark, found {len(vakalatnama_entries)}",
                "toc": toc,
            }

        vak_page = vakalatnama_entries[0][2]
        if vak_page != page_count:
            return {
                "valid": False,
                "error": f"'{LAST_PAGE_BOOKMARK_TITLE}' points to page {vak_page}, expected last page {page_count}",
                "toc": toc,
            }

        # Check all pages exist
        for entry in toc:
            p = entry[2]
            if p < 1 or p > page_count:
                return {
                    "valid": False,
                    "error": f"Bookmark '{entry[1]}' points to non-existent page {p} (doc has {page_count} pages)",
                    "toc": toc,
                }

        return {
            "valid": True,
            "page_count": page_count,
            "bookmark_count": len(toc),
            "toc": toc,
        }
    finally:
        if doc is not None:
            doc.close()
