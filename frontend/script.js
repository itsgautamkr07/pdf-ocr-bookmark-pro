// PDF OCR & AUTO BOOKMARK PRO - Client Script
// Uses same-origin requests strictly
const API_URL = window.location.origin;

let currentJobId = localStorage.getItem("pdf_ocr_job_id") || null;
let pollInterval = null;
let stagedFiles = [];
let stagedPaths = [];

// DOM Elements
const backendStatusBadge = document.getElementById("backend-status");
const backendStatusText = document.getElementById("backend-status-text");
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const folderInput = document.getElementById("folder-input");
const fileInputAddMore = document.getElementById("file-input-add-more");
const uploadFeedback = document.getElementById("upload-feedback");
const stagedCountText = document.getElementById("staged-count-text");
const stagedSizeText = document.getElementById("staged-size-text");
const btnUploadStaged = document.getElementById("btn-upload-staged");

const jobIdDisplay = document.getElementById("job-id-display");
const metricTotal = document.getElementById("metric-total");
const metricPending = document.getElementById("metric-pending");
const metricProcessing = document.getElementById("metric-processing");
const metricCompleted = document.getElementById("metric-completed");
const metricFailed = document.getElementById("metric-failed");
const failedCountBtn = document.getElementById("failed-count-btn");

const progressText = document.getElementById("progress-text");
const progressPercent = document.getElementById("progress-percent");
const progressBar = document.getElementById("progress-bar");
const filesTableBody = document.getElementById("files-table-body");

const btnRetry = document.getElementById("btn-retry");
const btnDownloadZip = document.getElementById("btn-download-zip");
const btnClear = document.getElementById("btn-clear");

const clearModal = document.getElementById("clear-modal");
const modalCancelBtn = document.getElementById("modal-cancel-btn");
const modalConfirmBtn = document.getElementById("modal-confirm-btn");

const toggleBookmarks = document.getElementById("toggle-bookmarks");
const bookmarkListWrapper = document.getElementById("bookmark-list-wrapper");
const toggleBookmarksIcon = document.getElementById("toggle-bookmarks-icon");
const toastContainer = document.getElementById("toast-container");

// --- Utility Functions ---
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4500);
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatDuration(seconds) {
  if (seconds === undefined || seconds === null) return "--";
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(1);
  return `${mins}m ${secs}s`;
}

// --- Health Check ---
async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_URL}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    backendStatusBadge.className = "status-badge status-online";
    if (data.ocr_tools && data.ocr_tools.tesseract_available) {
      backendStatusText.textContent = "Online • Tesseract Ready";
    } else {
      backendStatusText.textContent = "Online • OCR Engine Ready";
    }
  } catch (err) {
    backendStatusBadge.className = "status-badge status-offline";
    backendStatusText.textContent = "Server Disconnected";
  }
}

// --- Job Initialization & Session ---
async function ensureJobSession() {
  if (currentJobId) {
    try {
      const res = await fetch(`${API_URL}/jobs/${currentJobId}/status`);
      if (res.ok) {
        return currentJobId;
      }
    } catch (e) {
      // Job expired or unavailable, will create a fresh one below
    }
  }

  try {
    const res = await fetch(`${API_URL}/jobs`, { method: "POST" });
    if (!res.ok) throw new Error("Could not initialize job session.");
    const data = await res.json();
    currentJobId = data.job_id;
    localStorage.setItem("pdf_ocr_job_id", currentJobId);
    return currentJobId;
  } catch (err) {
    showToast("Error creating job session on server.", "error");
    throw err;
  }
}

// --- Drag & Drop Handling ---
["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
  dropZone.addEventListener(eventName, e => {
    e.preventDefault();
    e.stopPropagation();
  });
});

["dragenter", "dragover"].forEach(eventName => {
  dropZone.addEventListener(eventName, () => dropZone.classList.add("dragover"));
});

["dragleave", "drop"].forEach(eventName => {
  dropZone.addEventListener(eventName, () => dropZone.classList.remove("dragover"));
});

dropZone.addEventListener("drop", e => {
  const dt = e.dataTransfer;
  if (dt && dt.files && dt.files.length > 0) {
    handleSelectedFiles(Array.from(dt.files));
  }
});

fileInput.addEventListener("change", e => {
  if (e.target.files && e.target.files.length > 0) {
    handleSelectedFiles(Array.from(e.target.files));
  }
});

folderInput.addEventListener("change", e => {
  if (e.target.files && e.target.files.length > 0) {
    handleSelectedFiles(Array.from(e.target.files));
  }
});

fileInputAddMore.addEventListener("change", e => {
  if (e.target.files && e.target.files.length > 0) {
    // Add More Files triggers instant upload to current job
    uploadFilesImmediately(Array.from(e.target.files));
  }
});

function handleSelectedFiles(filesList) {
  const validPdfs = [];
  const validPaths = [];
  let rejectedCount = 0;

  filesList.forEach(file => {
    if (file.name.toLowerCase().endsWith(".pdf")) {
      validPdfs.push(file);
      validPaths.push(file.webkitRelativePath || file.name);
    } else {
      rejectedCount++;
    }
  });

  if (rejectedCount > 0) {
    showToast(`${rejectedCount} unsupported non-PDF file(s) ignored.`, "error");
  }

  if (validPdfs.length === 0) return;

  stagedFiles = validPdfs;
  stagedPaths = validPaths;

  const totalSize = stagedFiles.reduce((acc, f) => acc + f.size, 0);
  stagedCountText.textContent = `${stagedFiles.length} PDF file(s) selected`;
  stagedSizeText.textContent = formatBytes(totalSize);
  uploadFeedback.classList.remove("hidden");
}

btnUploadStaged.addEventListener("click", () => {
  if (stagedFiles.length > 0) {
    uploadFilesImmediately(stagedFiles, stagedPaths);
    stagedFiles = [];
    stagedPaths = [];
    uploadFeedback.classList.add("hidden");
    fileInput.value = "";
    folderInput.value = "";
  }
});

// --- Uploading Files (Supports Concurrent Batches) ---
async function uploadFilesImmediately(filesList, relativePaths = []) {
  try {
    const jobId = await ensureJobSession();
    jobIdDisplay.textContent = `Job: ${jobId.substring(0, 8)}...`;
    jobIdDisplay.className = "badge badge-info";

    const formData = new FormData();
    filesList.forEach((file, index) => {
      formData.append("files", file);
    });

    if (relativePaths.length > 0) {
      formData.append("paths", JSON.stringify(relativePaths));
    }

    showToast(`Uploading ${filesList.length} file(s) to processing queue...`, "info");

    const res = await fetch(`${API_URL}/jobs/${jobId}/files`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Upload failed.");
    }

    const data = await res.json();
    showToast(`Successfully added ${data.added_count} PDF(s) to queue!`, "success");

    // Start polling status
    startStatusPolling();
    refreshJobStatus();
  } catch (err) {
    showToast(`Upload failed: ${err.message}`, "error");
  }
}

// --- Status Polling ---
function startStatusPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(refreshJobStatus, 1500);
}

function stopStatusPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

async function refreshJobStatus() {
  if (!currentJobId) return;

  try {
    const res = await fetch(`${API_URL}/jobs/${currentJobId}/status`);
    if (!res.ok) {
      if (res.status === 404) {
        stopStatusPolling();
        localStorage.removeItem("pdf_ocr_job_id");
        currentJobId = null;
        jobIdDisplay.textContent = "No active job";
        jobIdDisplay.className = "badge badge-neutral";
      }
      return;
    }

    const data = await res.json();
    renderDashboard(data);

    // Stop polling if nothing is pending or processing
    if (data.pending_files === 0 && data.processing_files === 0 && data.total_files > 0) {
      stopStatusPolling();
    }
  } catch (e) {
    console.debug("Status polling error:", e);
  }
}

// --- Render Dashboard & File Table ---
function renderDashboard(data) {
  // Counters
  metricTotal.textContent = data.total_files;
  metricPending.textContent = data.pending_files;
  metricProcessing.textContent = data.processing_files;
  metricCompleted.textContent = data.completed_files;
  metricFailed.textContent = data.failed_files;
  failedCountBtn.textContent = data.failed_files;

  // Buttons states
  btnRetry.disabled = data.failed_files === 0;
  btnDownloadZip.disabled = data.completed_files === 0;
  btnClear.disabled = data.total_files === 0;

  // Progress Bar
  const percent = data.overall_progress || 0;
  progressBar.style.width = `${percent}%`;
  progressPercent.textContent = `${percent}%`;

  if (data.status === "processing") {
    progressText.textContent = `Processing documents (${data.completed_files + data.failed_files} of ${data.total_files} done)`;
  } else if (data.status === "completed") {
    progressText.textContent = `All ${data.total_files} documents successfully processed!`;
  } else if (data.status === "partially_completed") {
    progressText.textContent = `Completed with ${data.failed_files} failed file(s).`;
  } else if (data.status === "failed") {
    progressText.textContent = `Processing completed with errors.`;
  } else if (data.total_files > 0 && data.pending_files > 0) {
    progressText.textContent = `${data.pending_files} documents queued.`;
  } else {
    progressText.textContent = "Ready for files";
  }

  // Render Table Rows
  if (!data.files || data.files.length === 0) {
    filesTableBody.innerHTML = `
      <tr class="empty-row">
        <td colspan="5">
          <div class="empty-state">
            <p>No documents uploaded yet. Add PDF files to begin processing.</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  let html = "";
  data.files.forEach(file => {
    let statusBadge = "";
    if (file.status === "pending") {
      statusBadge = `<span class="badge badge-pending">Pending</span>`;
    } else if (file.status === "processing") {
      const stageText = file.stage === "ocr" ? "Running OCR..." : file.stage === "bookmarking" ? "Bookmarking..." : "Processing...";
      statusBadge = `<span class="badge badge-processing">${stageText}</span>`;
    } else if (file.status === "completed") {
      statusBadge = `<span class="badge badge-completed">✓ Completed</span>`;
    } else if (file.status === "failed") {
      const errorMsg = (file.error_message || "Unknown error").replace(/"/g, "&quot;");
      statusBadge = `<span class="badge badge-failed" title="${errorMsg}">✕ Failed: ${escapeHtml(file.error_message || "Error")}</span>`;
    }

    const durationDisplay = formatDuration(file.duration_seconds);
    const sizeDisplay = formatBytes(file.size_bytes);

    let actionBtn = "";
    if (file.status === "completed") {
      actionBtn = `
        <a href="${API_URL}/jobs/${data.job_id}/files/${file.file_id}/download"
           class="btn btn-primary btn-sm"
           download="${escapeHtml(file.original_filename)}">
          Download
        </a>
      `;
    } else if (file.status === "processing") {
      actionBtn = `<span class="text-muted" style="font-size:0.8rem;">Working...</span>`;
    } else if (file.status === "failed") {
      actionBtn = `<span class="text-danger" style="font-size:0.8rem;">Check error</span>`;
    } else {
      actionBtn = `<span class="text-muted" style="font-size:0.8rem;">In queue</span>`;
    }

    html += `
      <tr>
        <td>
          <strong>${escapeHtml(file.original_filename)}</strong>
          ${file.relative_path && file.relative_path !== file.original_filename ? `<br><small class="text-muted">${escapeHtml(file.relative_path)}</small>` : ""}
        </td>
        <td>${sizeDisplay}</td>
        <td>${statusBadge}</td>
        <td>${durationDisplay}</td>
        <td class="text-right">${actionBtn}</td>
      </tr>
    `;
  });

  filesTableBody.innerHTML = html;
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// --- Actions: Retry, Download ZIP, Clear ---
btnRetry.addEventListener("click", async () => {
  if (!currentJobId) return;
  try {
    btnRetry.disabled = true;
    showToast("Retrying failed files...", "info");
    const res = await fetch(`${API_URL}/jobs/${currentJobId}/retry`, { method: "POST" });
    if (!res.ok) throw new Error("Retry request failed.");
    const data = await res.json();
    showToast(data.message, "success");
    startStatusPolling();
    refreshJobStatus();
  } catch (err) {
    showToast(`Retry failed: ${err.message}`, "error");
  } finally {
    btnRetry.disabled = false;
  }
});

btnDownloadZip.addEventListener("click", () => {
  if (!currentJobId) return;
  window.location.href = `${API_URL}/jobs/${currentJobId}/download-zip`;
  showToast("Preparing ZIP archive download...", "info");
});

// Clear Job Confirmation Modal
btnClear.addEventListener("click", () => {
  clearModal.classList.remove("hidden");
});

modalCancelBtn.addEventListener("click", () => {
  clearModal.classList.add("hidden");
});

modalConfirmBtn.addEventListener("click", async () => {
  clearModal.classList.add("hidden");
  if (!currentJobId) return;

  try {
    showToast("Clearing current job data...", "info");
    const res = await fetch(`${API_URL}/jobs/${currentJobId}/clear`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to clear job.");

    stopStatusPolling();
    localStorage.removeItem("pdf_ocr_job_id");
    currentJobId = null;

    jobIdDisplay.textContent = "No active job";
    jobIdDisplay.className = "badge badge-neutral";
    renderDashboard({
      total_files: 0,
      pending_files: 0,
      processing_files: 0,
      completed_files: 0,
      failed_files: 0,
      overall_progress: 0,
      files: []
    });

    showToast("Job cleared successfully.", "success");
  } catch (err) {
    showToast(`Clear failed: ${err.message}`, "error");
  }
});

// Bookmark Toggle
toggleBookmarks.addEventListener("click", () => {
  const isHidden = bookmarkListWrapper.classList.toggle("hidden");
  toggleBookmarksIcon.textContent = isHidden ? "▼" : "▲";
});

// --- Initialization on page load ---
document.addEventListener("DOMContentLoaded", async () => {
  await checkBackendHealth();
  if (currentJobId) {
    refreshJobStatus();
    startStatusPolling();
  }
});
