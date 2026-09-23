/**
 * JurisGuide Client Application Logic
 *
 * Implements accessible, keyboard-friendly two-step workflow:
 * Step 1: Ingest document & detect category (Gemini Call 1)
 * Step 2: Confirm or manually override category -> Extract & Analyze (Gemini Call 2 + Code Rules)
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const tabFileBtn = document.getElementById("tab-file-btn");
  const tabTextBtn = document.getElementById("tab-text-btn");
  const tabFile = document.getElementById("tab-file");
  const tabText = document.getElementById("tab-text");
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const selectedFileName = document.getElementById("selected-file-name");
  const pastedText = document.getElementById("pasted-text");
  const btnClassify = document.getElementById("btn-classify");
  const inputError = document.getElementById("input-error");

  const inputSection = document.getElementById("input-section");
  const loadingSpinner = document.getElementById("loading-spinner");
  const loadingText = document.getElementById("loading-text");
  const confirmationSection = document.getElementById("confirmation-section");
  const resultsSection = document.getElementById("results-section");

  const confirmFilename = document.getElementById("confirm-filename");
  const confirmDetectedLabel = document.getElementById("confirm-detected-label");
  const confirmConfidence = document.getElementById("confirm-confidence");
  const confirmReason = document.getElementById("confirm-reason");
  const categoryOverride = document.getElementById("category-override");
  const btnCancelConfirm = document.getElementById("btn-cancel-confirm");
  const btnConfirmAnalyze = document.getElementById("btn-confirm-analyze");

  const reportRiskBadge = document.getElementById("report-risk-badge");
  const reportDocTitle = document.getElementById("report-doc-title");
  const statHigh = document.getElementById("stat-high");
  const statMed = document.getElementById("stat-med");
  const statMissing = document.getElementById("stat-missing");
  const reportSummaryText = document.getElementById("report-summary-text");
  const risksList = document.getElementById("risks-list");
  const missingSection = document.getElementById("missing-section");
  const missingList = document.getElementById("missing-list");
  const checklistItems = document.getElementById("checklist-items");
  const btnCopyChecklist = document.getElementById("btn-copy-checklist");
  const btnReset = document.getElementById("btn-reset");

  // State
  let activeTab = "file";
  let selectedFile = null;
  let currentSessionId = null;

  // -------------------------------------------------------------
  // Tabs Navigation (Accessible)
  // -------------------------------------------------------------
  tabFileBtn.addEventListener("click", () => switchTab("file"));
  tabTextBtn.addEventListener("click", () => switchTab("text"));

  function switchTab(tab) {
    activeTab = tab;
    clearError();
    if (tab === "file") {
      tabFileBtn.classList.add("active");
      tabFileBtn.setAttribute("aria-selected", "true");
      tabTextBtn.classList.remove("active");
      tabTextBtn.setAttribute("aria-selected", "false");

      tabFile.removeAttribute("hidden");
      tabFile.classList.add("active");
      tabText.setAttribute("hidden", "true");
      tabText.classList.remove("active");
    } else {
      tabTextBtn.classList.add("active");
      tabTextBtn.setAttribute("aria-selected", "true");
      tabFileBtn.classList.remove("active");
      tabFileBtn.setAttribute("aria-selected", "false");

      tabText.removeAttribute("hidden");
      tabText.classList.add("active");
      tabFile.setAttribute("hidden", "true");
      tabFile.classList.remove("active");
    }
  }

  // -------------------------------------------------------------
  // Drag & Drop / File Input
  // -------------------------------------------------------------
  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  });

  function handleSelectedFile(file) {
    selectedFile = file;
    clearError();
    selectedFileName.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  }

  function showError(msg) {
    inputError.textContent = msg;
    inputError.removeAttribute("hidden");
  }

  function clearError() {
    inputError.textContent = "";
    inputError.setAttribute("hidden", "true");
  }

  // -------------------------------------------------------------
  // Step 1: Detect Document Type
  // -------------------------------------------------------------
  btnClassify.addEventListener("click", async () => {
    clearError();
    const formData = new FormData();

    if (activeTab === "file") {
      if (!selectedFile) {
        showError("Please select a contract file to upload.");
        return;
      }
      formData.append("file", selectedFile);
    } else {
      const text = pastedText.value.trim();
      if (!text || text.length < 20) {
        showError("Please paste at least 20 characters of contract text.");
        return;
      }
      formData.append("text_content", text);
    }

    // Show loading state
    inputSection.setAttribute("hidden", "true");
    loadingSpinner.removeAttribute("hidden");
    loadingText.textContent = "Classifying document type with Gemini...";

    try {
      const response = await fetch("/api/classify", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || "Failed to classify document.");
      }

      // Populate Step 2 Confirmation screen
      currentSessionId = data.session_id;
      confirmFilename.textContent = data.filename;
      confirmDetectedLabel.textContent = formatCategoryLabel(data.detected_type);
      confirmConfidence.textContent = `${Math.round(data.confidence * 100)}%`;
      confirmReason.textContent = data.summary_reason || "Based on contract text markers.";
      categoryOverride.value = data.detected_type;

      loadingSpinner.setAttribute("hidden", "true");
      confirmationSection.removeAttribute("hidden");
    } catch (err) {
      loadingSpinner.setAttribute("hidden", "true");
      inputSection.removeAttribute("hidden");
      showError(err.message || "An error occurred during classification.");
    }
  });

  btnCancelConfirm.addEventListener("click", () => {
    confirmationSection.setAttribute("hidden", "true");
    inputSection.removeAttribute("hidden");
  });

  // -------------------------------------------------------------
  // Step 2: Confirm Category & Run Risk Analysis
  // -------------------------------------------------------------
  btnConfirmAnalyze.addEventListener("click", async () => {
    const confirmedType = categoryOverride.value;
    confirmationSection.setAttribute("hidden", "true");
    loadingSpinner.removeAttribute("hidden");
    loadingText.textContent = "Extracting clauses and applying deterministic risk rules...";

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          confirmed_type: confirmedType,
        }),
      });

      const report = await response.json();
      if (!response.ok) {
        throw new Error(report.message || "Analysis failed.");
      }

      renderReport(report);
      loadingSpinner.setAttribute("hidden", "true");
      resultsSection.removeAttribute("hidden");
    } catch (err) {
      loadingSpinner.setAttribute("hidden", "true");
      confirmationSection.removeAttribute("hidden");
      alert(err.message || "Failed to analyze document.");
    }
  });

  // -------------------------------------------------------------
  // Render Analysis Report
  // -------------------------------------------------------------
  function renderReport(report) {
    // Posture Badge
    reportRiskBadge.textContent = `${report.overall_risk_level} RISK`;
    reportRiskBadge.className = `badge-posture badge-posture-${report.overall_risk_level.toLowerCase()}`;
    reportDocTitle.textContent = `Document: ${report.document_title} (${formatCategoryLabel(report.document_type)})`;

    // Stats
    statHigh.textContent = report.stats.high_risks || 0;
    statMed.textContent = report.stats.medium_risks || 0;
    statMissing.textContent = report.stats.missing_clauses || 0;

    // Plain Language Summary
    reportSummaryText.textContent = report.summary;

    // Identified Risks List
    risksList.innerHTML = "";
    if (report.risk_items.length === 0) {
      risksList.innerHTML = "<p class='text-muted'>No major risk thresholds breached under current configuration.</p>";
    } else {
      report.risk_items.forEach((risk) => {
        const item = document.createElement("article");
        item.className = `risk-card severity-${risk.severity.toLowerCase()}`;
        item.innerHTML = `
          <div class="risk-card-header">
            <h4 class="risk-card-title">${escapeHtml(risk.title)}</h4>
            <span class="risk-badge badge-${risk.severity.toLowerCase()}" role="status">${risk.severity} RISK</span>
          </div>
          <p class="risk-explanation">${escapeHtml(risk.explanation)}</p>
          <div class="risk-recom">
            <strong>Recommendation:</strong> ${escapeHtml(risk.recommendation)}
          </div>
          ${
            risk.raw_text
              ? `
              <details class="raw-text-details">
                <summary class="raw-text-summary">📄 View verbatim clause text from contract</summary>
                <pre class="raw-text-block">${escapeHtml(risk.raw_text)}</pre>
              </details>
            `
              : ""
          }
        `;
        risksList.appendChild(item);
      });
    }

    // Missing Clauses List
    missingList.innerHTML = "";
    if (report.missing_clauses.length === 0) {
      missingSection.setAttribute("hidden", "true");
    } else {
      missingSection.removeAttribute("hidden");
      report.missing_clauses.forEach((missing) => {
        const item = document.createElement("article");
        item.className = "missing-card";
        item.innerHTML = `
          <h4 class="missing-title">Absent: ${escapeHtml(missing.clause_name)}</h4>
          <p class="missing-desc">${escapeHtml(missing.explanation)}</p>
          <div class="risk-recom">
            <strong>Recommendation:</strong> ${escapeHtml(missing.recommendation)}
          </div>
        `;
        missingList.appendChild(item);
      });
    }

    // Actionable Checklist
    checklistItems.innerHTML = "";
    report.checklist.forEach((q, idx) => {
      const li = document.createElement("li");
      li.className = "checklist-item";
      li.innerHTML = `
        <input type="checkbox" id="check-${idx}" class="checklist-item-check" aria-label="Mark question as resolved">
        <div>
          <div class="checklist-item-target">${escapeHtml(q.category)}</div>
          <label for="check-${idx}" class="checklist-item-text">${escapeHtml(q.question)}</label>
        </div>
      `;
      checklistItems.appendChild(li);
    });

    // Copy Questions Button
    btnCopyChecklist.onclick = () => {
      const questionsText = report.checklist
        .map((q, i) => `${i + 1}. [${q.category}] ${q.question}`)
        .join("\n\n");
      navigator.clipboard.writeText(questionsText).then(() => {
        btnCopyChecklist.textContent = "Copied!";
        setTimeout(() => {
          btnCopyChecklist.textContent = "Copy Questions";
        }, 2000);
      });
    };
  }

  // Reset Button
  btnReset.addEventListener("click", () => {
    selectedFile = null;
    currentSessionId = null;
    fileInput.value = "";
    selectedFileName.textContent = "";
    pastedText.value = "";
    resultsSection.setAttribute("hidden", "true");
    confirmationSection.setAttribute("hidden", "true");
    inputSection.removeAttribute("hidden");
  });

  function formatCategoryLabel(cat) {
    const map = {
      employment_offer: "Employment Offer Letter",
      rental_agreement: "Rental / Lease Agreement",
      freelance_contract: "Freelance / Service Contract",
      other: "General Legal Document",
    };
    return map[cat] || "Contract";
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
