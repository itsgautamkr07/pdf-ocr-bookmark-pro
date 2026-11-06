# PDF OCR & AUTO BOOKMARK PRO

A high-performance, beginner-friendly web application designed for legal and enterprise document workflows. Automatically converts scanned PDFs into searchable documents via OCR and embeds a standardized 14-section legal bookmark table of contents.

---

## 🌟 Key Capabilities

1. **Batch PDF Processing**: Upload multiple PDFs, select an entire folder structure, or drag & drop files.
2. **Add More Files Seamlessly (No Data Loss)**:
   - Add new PDFs to the queue while existing files are currently processing.
   - Add files after a previous batch has completed without resetting the job.
   - All uploaded documents are processed and compiled into a single combined ZIP download.
3. **High-Accuracy Searchable OCR**:
   - Powered by **OCRmyPDF** and **Tesseract OCR**.
   - Detects existing text to avoid redundant re-OCR (`skip_text=True`).
   - Preserves original page layout, resolution, and dimensions.
4. **Exact Standardized Legal Bookmark Template**:
   - Replaces any messy or inconsistent existing bookmarks with the exact standard 14 positions.
   - Always assigns **VAKALATNAMA** to the final page of each document.
5. **Accurate Real-Time Progress & Timing**:
   - Displays actual elapsed seconds per document. No fake progress animations.
   - Per-file error reporting: a corrupted PDF will never halt the rest of your batch.
6. **Safe Storage & Original Filenames**:
   - Retains original filenames for individual downloads and inside the final ZIP.
   - Deduplicates identical filenames automatically (`Document.pdf`, `Document (1).pdf`).

---

## 📑 Exact Bookmark Structure

Every processed PDF receives this standardized table of contents:

| Page | Bookmark Title | Description |
|:---:|:---|:---|
| 1 | `CIF` | Customer Information Form |
| 2 | `CHECK LIST` | Document checklist |
| 3 | `INDEX` | Legal index |
| 4 | `MEMO OF PARTIES` | Litigant details |
| 5 | `SYNOPSIS` | Case summary |
| 7 | `COMPLAINT UNDER SECTION 25(1)` | Primary complaint |
| 12 | `COMPLAINT EVIDENCE` | Evidentiary exhibits |
| 16 | `LIST OF DOCUMENTS & WITNESS` | Witnesses & list of docs |
| 17 | `SPA` | Special Power of Attorney |
| 18 | `AUTO DEBIT FORM` | Mandate authorization |
| 19 | `AUTO DEBIT RETURN MEMO` | Bank return advice |
| 22 | `NOTICE` | Demand notice |
| 23 | `TRACKING REPORT` | Postal dispatch & delivery proof |
| **Last Page** | **`VAKALATNAMA`** | **Mandatory counsel authorization on final page** |

*Rules:*
- Bookmarks for pages that do not exist (e.g. page 16 on a 10-page document) are automatically skipped.
- Exactly **one** `VAKALATNAMA` bookmark is always placed on the final page (`doc.page_count`).

---

## 📂 Project Directory Structure

```text
D:\PDF_OCR_BOOKMARK_PRO
│
├── backend/
│   ├── __init__.py
│   ├── config.py              # Windows tool auto-detection & environment config
│   ├── bookmark_service.py    # PyMuPDF bookmark engine & verification
│   ├── ocr_service.py         # OCRmyPDF wrapper & health monitor
│   ├── processor.py           # Per-file processing pipeline & timing
│   ├── job_manager.py         # Async job queue & multi-batch coordinator
│   └── main.py                # FastAPI REST API & static file server
│
├── frontend/
│   ├── index.html             # Clean responsive UI
│   ├── style.css              # Modern light theme CSS
│   └── script.js              # Vanilla JS with polling & error handling
│
├── tests/
│   ├── __init__.py
│   ├── test_bookmarks.py      # Verification of TOC rules & VAKALATNAMA
│   ├── test_ocr_and_processing.py # Scanned, searchable, & corrupted PDF tests
│   ├── test_jobs.py           # Multi-batch queuing & ZIP deduplication
│   └── test_api.py            # API endpoint integration tests
│
├── uploads/                   # Isolated raw uploads per job
├── processed/                 # Processed bookmarked PDFs
├── temp/                      # Intermediate temporary OCR files
├── zips/                      # Generated ZIP archives
│
├── requirements.txt           # Python package dependencies
├── Dockerfile                 # Container image for Docker/Render
├── .dockerignore
├── .gitignore
├── run_app.bat                # 1-Click Windows Batch launcher
├── start_server.ps1           # PowerShell launcher script
└── README.md
```

---

## 🚀 Local Windows Setup (Step-by-Step)

### Prerequisites

1. **Python 3.10 or 3.11**:
   - Download from [python.org](https://www.python.org/downloads/).
   - **Crucial**: During installation, check the box: `"Add Python to PATH"`.

2. **Tesseract OCR**:
   - Download the Windows installer from [UB Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
   - Default install path: `C:\Program Files\Tesseract-OCR` (the application auto-detects this path).

3. **Ghostscript**:
   - Download the 64-bit Windows installer from [Ghostscript Releases](https://ghostscript.com/releases/gsdn.html).
   - Default install path: `C:\Program Files\gs\gs...` (auto-detected).

---

### Starting the Application

#### Option A: Double-Click Launcher (Easiest)
Navigate to `D:\PDF_OCR_BOOKMARK_PRO` and double-click **`run_app.bat`**.

The launcher will:
1. Verify Python and activate `.venv`.
2. Check and install any missing dependencies.
3. Verify Tesseract and Ghostscript.
4. Launch the web server and open your default browser to `http://localhost:8000`.

#### Option B: PowerShell Command
Open PowerShell and run:
```powershell
cd D:\PDF_OCR_BOOKMARK_PRO
.\start_server.ps1
```

---

### How to Stop & Restart the Server

- **To Stop**: Click into the command prompt / PowerShell window running the server and press `Ctrl + C`.
- **To Restart**: Simply run `run_app.bat` or `.\start_server.ps1` again.

---

## 🧪 Running Automated Tests

A comprehensive test suite of 20 automated tests covers all operational requirements:

```powershell
cd D:\PDF_OCR_BOOKMARK_PRO
.\.venv\Scripts\pytest tests -v
```

Tests executed include:
- `test_one_scanned_pdf`: Raster image OCR validation.
- `test_one_searchable_pdf`: Text-layer preservation and fast OCR.
- `test_pdf_fewer_than_23_pages`: Short document handling.
- `test_pdf_at_least_23_pages`: Full template coverage.
- `test_exactly_one_vakalatnama`: Guarantees exactly 1 VAKALATNAMA on final page across 1, 7, 22, 23, and 30 page PDFs.
- `test_add_more_files_while_processing`: Concurrency validation.
- `test_add_more_files_after_completion`: Multi-batch persistence.
- `test_duplicate_filenames`: Deduplication without overwriting.
- `test_corrupted_pdf_handling`: Graceful error recovery.
- `test_original_filenames_retained`: Filename preservation.

---

## 🐳 Docker Deployment

To build and run the application in a local Docker container:

```bash
# 1. Build the Docker image
docker build -t pdf-ocr-bookmark-pro .

# 2. Run the container
docker run -p 8000:8000 pdf-ocr-bookmark-pro
```

Access the app at `http://localhost:8000`.

---

## ☁️ Free Cloud Deployment (Render.com Guide)

You can deploy the Docker container to [Render](https://render.com) using their Web Service.

### Step 1: Push Code to GitHub
1. Create a new repository on [GitHub](https://github.com) (e.g. `pdf-ocr-bookmark-pro`).
2. Run these commands from `D:\PDF_OCR_BOOKMARK_PRO`:
   ```powershell
   git init
   git add .
   git commit -m "Initial commit of PDF OCR & AUTO BOOKMARK PRO"
   git branch -M main
   git remote add origin https://github.com/<your-username>/pdf-ocr-bookmark-pro.git
   git push -u origin main
   ```

### Step 2: Create Web Service on Render
1. Sign in to [Render](https://render.com) and click **"New +" -> "Web Service"**.
2. Connect your GitHub repository.
3. Select **Docker** as the Runtime (Render reads the `Dockerfile`).
4. Choose the **Free** instance tier.
5. Under **Environment Variables**, set:
   - `OCR_MAX_WORKERS` = `1` (Critical for free-tier memory limit).
   - `OCR_SKIP_TEXT` = `true`

### Step 3: Important Free-Tier Realities & Limitations
Be aware of these constraints when using free hosting tiers:

| Limitation | Impact | Solution / Best Practice |
|:---|:---|:---|
| **512 MB RAM Limit** | OCR on large 300+ DPI scans can exceed 512 MB and cause an Out-Of-Memory (OOM) crash. | Set `OCR_MAX_WORKERS=1` in environment variables to prevent parallel memory spikes. |
| **Inactivity Spin-Down** | Free instances sleep after 15 minutes of inactivity. | The first visit may take 50 seconds to spin up. Subsequent requests run normally. |
| **Ephemeral Storage** | Disks on free instances are wiped whenever the container restarts or sleeps. | **Always download your individual PDFs or ZIP file immediately after processing finishes.** |
| **100s Request Timeout** | Long HTTP requests can time out on free proxies. | Our application uses background workers and status polling, preventing HTTP connection dropouts. |

#### Alternative Hosting for Heavy Legal Workloads
If you regularly process batches of hundreds of large legal scans:
- **Dedicated VPS** (DigitalOcean / Hetzner / Linode: \$4 - \$6/mo): 1-2 GB RAM with dedicated disk ensures fast OCR and zero timeout/sleep delays.
- **Local Network Execution**: Running locally on your Windows PC via `run_app.bat` has zero resource limits, utilizes your full CPU speed, and keeps sensitive legal documents 100% private on your own hardware.
