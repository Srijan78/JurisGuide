/**
 * JurisGuide — Client Application Logic
 *
 * Two-step workflow:
 * Step 1: Ingest document, detect category (Gemini Call 1)
 * Step 2: Confirm or override category, extract and analyze (Gemini Call 2 + deterministic rules)
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM — Input
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

  // DOM — Sections
  const inputSection = document.getElementById("input-section");
  const loadingSpinner = document.getElementById("loading-spinner");
  const loadingText = document.getElementById("loading-text");
  const confirmationSection = document.getElementById("confirmation-section");
  const resultsSection = document.getElementById("results-section");

  // DOM — Confirmation
  const confirmFilename = document.getElementById("confirm-filename");
  const confirmDetectedLabel = document.getElementById("confirm-detected-label");
  const confirmConfidence = document.getElementById("confirm-confidence");
  const confirmReason = document.getElementById("confirm-reason");
  const categoryOverride = document.getElementById("category-override");
  const btnCancelConfirm = document.getElementById("btn-cancel-confirm");
  const btnConfirmAnalyze = document.getElementById("btn-confirm-analyze");

  // DOM — Results
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

  // DOM — Non-Legal (Outcome B)
  const nonLegalSection = document.getElementById("non-legal-section");
  const legalResultsContainer = document.getElementById("legal-results-container");
  const nonLegalDocTitle = document.getElementById("non-legal-doc-title");
  const nonLegalMessage = document.getElementById("non-legal-message");
  const btnNonLegalReset = document.getElementById("btn-non-legal-reset");

  // DOM — Progress
  const progressSegments = document.querySelectorAll(".progress-segment");
  const progressLabels = document.querySelectorAll(".progress-label");

  // State
  let activeTab = "file";
  let selectedFile = null;
  let currentSessionId = null;

  // ----- Loading & Section Visibility Helpers -----
  function showLoading(text) {
    if (loadingSpinner) {
      loadingSpinner.removeAttribute("hidden");
      loadingSpinner.style.display = "flex";
    }
    if (loadingText) {
      loadingText.textContent = text || "Processing document...";
    }
  }

  function hideLoading() {
    if (loadingSpinner) {
      loadingSpinner.setAttribute("hidden", "true");
      loadingSpinner.style.display = "none";
    }
  }

  function showSection(activeSec) {
    const allSections = [inputSection, confirmationSection, resultsSection];
    allSections.forEach((sec) => {
      if (!sec) return;
      if (sec === activeSec) {
        sec.removeAttribute("hidden");
        sec.style.display = "";
      } else {
        sec.setAttribute("hidden", "true");
        sec.style.display = "none";
      }
    });
  }

  // ----- Timeout-enabled fetch helper -----
  async function fetchWithTimeout(resource, options = {}, timeoutMs = 60000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(resource, {
        ...options,
        signal: controller.signal,
      });
    } catch (err) {
      if (err.name === "AbortError") {
        throw new Error("Request timed out. The server took longer than expected to process your document. Please try again.");
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  // ----- Progress indicator -----
  function setProgress(step) {
    progressSegments.forEach((seg) => {
      const s = parseInt(seg.dataset.step);
      seg.classList.toggle("active", s === step);
      seg.classList.toggle("completed", s < step);
    });
    progressLabels.forEach((lbl) => {
      const s = parseInt(lbl.dataset.step);
      lbl.classList.toggle("active", s === step);
      lbl.classList.toggle("completed", s < step);
    });
  }

  // Initialize visibility cleanly
  hideLoading();
  showSection(inputSection);
  setProgress(1);

  // ----- Tab navigation -----
  const tabs = [tabFileBtn, tabTextBtn];

  tabFileBtn.addEventListener("click", () => switchTab("file"));
  tabTextBtn.addEventListener("click", () => switchTab("text"));

  tabs.forEach((tabBtn, index) => {
    tabBtn.addEventListener("keydown", (e) => {
      let targetIndex = null;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        targetIndex = (index + 1) % tabs.length;
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        targetIndex = (index - 1 + tabs.length) % tabs.length;
      } else if (e.key === "Home") {
        e.preventDefault();
        targetIndex = 0;
      } else if (e.key === "End") {
        e.preventDefault();
        targetIndex = tabs.length - 1;
      }

      if (targetIndex !== null) {
        const targetBtn = tabs[targetIndex];
        const tabType = targetBtn === tabFileBtn ? "file" : "text";
        switchTab(tabType);
        targetBtn.focus();
      }
    });
  });

  function switchTab(tab) {
    activeTab = tab;
    clearError();
    if (tab === "file") {
      tabFileBtn.setAttribute("aria-selected", "true");
      tabFileBtn.setAttribute("tabindex", "0");
      tabTextBtn.setAttribute("aria-selected", "false");
      tabTextBtn.setAttribute("tabindex", "-1");
      tabFile.removeAttribute("hidden");
      tabFile.style.display = "";
      tabFile.classList.add("active");
      tabText.setAttribute("hidden", "true");
      tabText.style.display = "none";
      tabText.classList.remove("active");
    } else {
      tabTextBtn.setAttribute("aria-selected", "true");
      tabTextBtn.setAttribute("tabindex", "0");
      tabFileBtn.setAttribute("aria-selected", "false");
      tabFileBtn.setAttribute("tabindex", "-1");
      tabText.removeAttribute("hidden");
      tabText.style.display = "";
      tabText.classList.add("active");
      tabFile.setAttribute("hidden", "true");
      tabFile.style.display = "none";
      tabFile.classList.remove("active");
    }
  }

  // ----- Drag and drop / file input -----
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
    selectedFileName.textContent = `${file.name}  (${(file.size / 1024).toFixed(1)} KB)`;
  }

  function showError(msg) {
    inputError.textContent = msg;
    inputError.removeAttribute("hidden");
    inputError.style.display = "block";
  }

  function clearError() {
    inputError.textContent = "";
    inputError.setAttribute("hidden", "true");
    inputError.style.display = "none";
  }

  // ----- Step 1: Detect document type -----
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

    // Hide input section and show spinner
    showSection(null);
    showLoading("Classifying document structure...");
    setProgress(2);

    try {
      const response = await fetchWithTimeout("/api/classify", {
        method: "POST",
        body: formData,
      }, 45000);

      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || "Failed to classify document.");
      }

      currentSessionId = data.session_id;
      confirmFilename.textContent = data.filename;
      confirmDetectedLabel.textContent = formatCategoryLabel(data.detected_type);
      confirmConfidence.textContent = `${Math.round(data.confidence * 100)}%`;
      confirmReason.textContent = data.summary_reason || "Based on document content.";
      categoryOverride.value = data.detected_type;

      hideLoading();
      showSection(confirmationSection);
      setProgress(3);
    } catch (err) {
      hideLoading();
      showSection(inputSection);
      setProgress(1);
      showError(err.message || "An error occurred during classification.");
    }
  });

  btnCancelConfirm.addEventListener("click", () => {
    hideLoading();
    showSection(inputSection);
    setProgress(1);
  });

  // ----- Step 2: Confirm and run analysis -----
  btnConfirmAnalyze.addEventListener("click", async () => {
    const confirmedType = categoryOverride.value;
    showSection(null);
    showLoading("Extracting clauses and applying deterministic risk rules...");

    try {
      const response = await fetchWithTimeout("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          confirmed_type: confirmedType,
        }),
      }, 75000);

      const report = await response.json();
      if (!response.ok) {
        throw new Error(report.message || "Analysis failed.");
      }

      renderReport(report);
      hideLoading();
      showSection(resultsSection);
      setProgress(4);
    } catch (err) {
      hideLoading();
      showSection(confirmationSection);
      setProgress(3);
      alert(err.message || "Failed to analyze document.");
    }
  });

  // ----- Render report -----
  function renderReport(report) {
    try {
      const isNonLegal = (report.overall_risk_level === "NON_LEGAL") ||
        (!report.risk_items?.length && report.summary && report.summary.includes("doesn't appear to contain legal"));

      if (isNonLegal) {
        // OUTCOME B: Not a legal document state
        if (legalResultsContainer) {
          legalResultsContainer.setAttribute("hidden", "true");
          legalResultsContainer.style.display = "none";
        }
        if (nonLegalSection) {
          nonLegalSection.removeAttribute("hidden");
          nonLegalSection.style.display = "block";
        }
        if (nonLegalDocTitle) {
          nonLegalDocTitle.textContent = `${report.document_title || "Uploaded Document"}`;
        }
        if (nonLegalMessage) {
          nonLegalMessage.textContent = report.summary || "This document doesn't appear to contain legal or contractual content. JurisGuide is designed to analyze contracts and agreements — try uploading an employment offer, rental agreement, or freelance contract instead.";
        }
        return;
      }

      // OUTCOME A or standard contracts: show legal results container, hide non-legal section
      if (nonLegalSection) {
        nonLegalSection.setAttribute("hidden", "true");
        nonLegalSection.style.display = "none";
      }
      if (legalResultsContainer) {
        legalResultsContainer.removeAttribute("hidden");
        legalResultsContainer.style.display = "block";
      }

      // Risk badge
      const riskLevel = report.overall_risk_level || "general";
      reportRiskBadge.textContent = `${riskLevel} risk`;
      reportRiskBadge.className = `badge-posture badge-posture-${riskLevel.toLowerCase()}`;
      reportDocTitle.textContent = `${report.document_title || "Document"} — ${formatCategoryLabel(report.document_type)}`;

      // Stats
      statHigh.textContent = (report.stats && report.stats.high_risks) || 0;
      statMed.textContent = (report.stats && report.stats.medium_risks) || 0;
      statMissing.textContent = (report.stats && report.stats.missing_clauses) || 0;

      // Summary
      reportSummaryText.textContent = report.summary || "Analysis complete.";

      // Risk items
      risksList.innerHTML = "";
      if (!report.risk_items || report.risk_items.length === 0) {
        risksList.innerHTML = "<p style='color: var(--slate); font-size: 0.9rem;'>No major risk thresholds breached under current configuration.</p>";
      } else {
        report.risk_items.forEach((risk) => {
          const item = document.createElement("article");
          item.className = `risk-card severity-${risk.severity.toLowerCase()}`;
          item.innerHTML = `
            <div class="risk-card-header">
              <h4 class="risk-card-title">${escapeHtml(risk.title)}</h4>
              <span class="risk-badge badge-${risk.severity.toLowerCase()}" role="status">${risk.severity} risk</span>
            </div>
            <p class="risk-explanation">${escapeHtml(risk.explanation)}</p>
            <div class="risk-recom">
              <strong>Recommendation:</strong> ${escapeHtml(risk.recommendation)}
            </div>
            ${
              risk.raw_text
                ? `
                <details class="raw-text-details">
                  <summary class="raw-text-summary">View verbatim clause text from contract</summary>
                  <pre class="raw-text-block">${escapeHtml(risk.raw_text)}</pre>
                </details>
              `
                : ""
            }
          `;
          risksList.appendChild(item);
        });
      }

      // Missing clauses
      missingList.innerHTML = "";
      if (!report.missing_clauses || report.missing_clauses.length === 0) {
        missingSection.setAttribute("hidden", "true");
        missingSection.style.display = "none";
      } else {
        missingSection.removeAttribute("hidden");
        missingSection.style.display = "";
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

      // Checklist
      checklistItems.innerHTML = "";
      if (report.checklist && report.checklist.length > 0) {
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
      }

      // Copy button
      btnCopyChecklist.onclick = () => {
        if (!report.checklist) return;
        const questionsText = report.checklist
          .map((q, i) => `${i + 1}. [${q.category}] ${q.question}`)
          .join("\n\n");
        navigator.clipboard.writeText(questionsText).then(() => {
          btnCopyChecklist.textContent = "Copied";
          setTimeout(() => {
            btnCopyChecklist.textContent = "Copy questions";
          }, 2000);
        });
      };
    } catch (renderErr) {
      console.error("Error during report rendering:", renderErr);
    }
  }

  // ----- Reset -----
  function resetApp() {
    selectedFile = null;
    currentSessionId = null;
    fileInput.value = "";
    selectedFileName.textContent = "";
    pastedText.value = "";
    if (nonLegalSection) {
      nonLegalSection.setAttribute("hidden", "true");
      nonLegalSection.style.display = "none";
    }
    if (legalResultsContainer) {
      legalResultsContainer.removeAttribute("hidden");
      legalResultsContainer.style.display = "block";
    }
    hideLoading();
    showSection(inputSection);
    setProgress(1);
  }

  btnReset.addEventListener("click", resetApp);
  if (btnNonLegalReset) {
    btnNonLegalReset.addEventListener("click", resetApp);
  }

  function formatCategoryLabel(cat) {
    const map = {
      employment_offer: "Employment offer",
      rental_agreement: "Rental / lease agreement",
      freelance_contract: "Freelance / service contract",
      other: "General legal document",
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
