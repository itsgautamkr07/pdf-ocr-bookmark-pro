import os
import sys
from pathlib import Path

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Storage directories
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
TEMP_DIR = BASE_DIR / "temp"
ZIPS_DIR = BASE_DIR / "zips"

for folder in [UPLOADS_DIR, PROCESSED_DIR, TEMP_DIR, ZIPS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Application Settings
APP_TITLE = "PDF OCR & AUTO BOOKMARK PRO"
APP_VERSION = "2.0.0"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# OCR Configuration
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "eng")
OCR_SKIP_TEXT = os.getenv("OCR_SKIP_TEXT", "true").lower() in ("true", "1", "yes")
OCR_OPTIMIZE = int(os.getenv("OCR_OPTIMIZE", "1"))
# CPU worker limit: allow user to configure, default to min(4, cpu_count)
CPU_COUNT = os.cpu_count() or 1
OCR_MAX_WORKERS = int(os.getenv("OCR_MAX_WORKERS", str(min(4, CPU_COUNT))))

# File limits
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Setup Windows system paths for Tesseract and Ghostscript
def configure_windows_paths():
    """Detect and inject Tesseract and Ghostscript binary directories on Windows."""
    if sys.platform != "win32":
        return

    additional_paths = []

    # Known Tesseract locations
    tesseract_candidates = [
        Path(r"C:\Program Files\Tesseract-OCR"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR",
    ]
    for candidate in tesseract_candidates:
        if candidate.is_dir() and (candidate / "tesseract.exe").exists():
            additional_paths.append(str(candidate))
            tessdata = candidate / "tessdata"
            if tessdata.is_dir() and "TESSDATA_PREFIX" not in os.environ:
                os.environ["TESSDATA_PREFIX"] = str(tessdata)
            break

    # Known Ghostscript locations
    gs_base = Path(r"C:\Program Files\gs")
    if gs_base.is_dir():
        for gs_ver in sorted(gs_base.glob("gs*"), reverse=True):
            gs_bin = gs_ver / "bin"
            if gs_bin.is_dir():
                additional_paths.append(str(gs_bin))
                break

    # Known QPDF locations
    qpdf_candidates = [
        Path(r"C:\Program Files\qpdf\bin"),
        Path(r"C:\Program Files (x86)\qpdf\bin"),
    ]
    for qpdf_cand in qpdf_candidates:
        if qpdf_cand.is_dir() and (qpdf_cand / "qpdf.exe").exists():
            additional_paths.append(str(qpdf_cand))
            break

    if additional_paths:
        current_path = os.environ.get("PATH", "")
        paths_to_add = [p for p in additional_paths if p not in current_path]
        if paths_to_add:
            os.environ["PATH"] = os.pathsep.join(paths_to_add) + os.pathsep + current_path

configure_windows_paths()
