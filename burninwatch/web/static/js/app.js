/**
 * BurninWatch – Component Screening Anomaly Detection
 * Interactive Liquid Glassmorphism UI Controller
 * Features:
 * - Ambient Liquid Glass theming (Light/Dark instant toggle)
 * - 60fps reactive Chart.js visualization suite
 * - Dual-component overlay comparison with cohort envelope
 * - Interactive live dashboard screening threshold tuner
 * - Full client-side state preservation across navigation
 */

// Application Global State
const AppState = {
  currentTab: "dashboard",
  theme: "dark",
  datasetInfo: null,
  dashboardData: null,
  activeComponentId: null,
  activeComponentData: null,
  comparisonComponentId: null,
  comparisonComponentData: null,
  activeChannel: "resistance",
  charts: {},
  settings: {
    threshold_suspicious: 60.0,
    threshold_high: 80.0
  },
  thresholdDebounceTimer: null
};

// ==========================================================================
// Theme Management
// ==========================================================================
function initTheme() {
  const savedTheme = localStorage.getItem("burninwatch_theme") || "dark";
  setTheme(savedTheme);
}

function setTheme(theme) {
  AppState.theme = theme;
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("burninwatch_theme", theme);

  const icon = document.getElementById("theme-toggle-icon");
  if (icon) {
    if (theme === "dark") {
      icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-sun"><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.93 4.93 1.41 1.41" /><path d="m17.66 17.66 1.41 1.41" /><path d="M2 12h2" /><path d="M20 12h2" /><path d="m6.34 17.66-1.41 1.41" /><path d="m19.07 4.93-1.41 1.41" /></svg>`;
    } else {
      icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-moon"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" /></svg>`;
    }
  }

  // Dynamically update Chart.js theme palettes
  updateAllChartsTheme();
}

function toggleTheme() {
  const newTheme = AppState.theme === "dark" ? "light" : "dark";
  setTheme(newTheme);
  showToast(`Switched to ${newTheme.toUpperCase()} theme`, "info");
}

function getThemeColors() {
  const isDark = AppState.theme === "dark";
  return {
    textColor: isDark ? "#cbd5e1" : "#475569",
    gridColor: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(226, 232, 240, 0.8)",
    normalColor: isDark ? "#34d399" : "#10b981",
    suspColor: isDark ? "#fbbf24" : "#f59e0b",
    highColor: isDark ? "#f43f5e" : "#ef4444",
    blueColor: isDark ? "#38bdf8" : "#0284c7",
    purpleColor: isDark ? "#a78bfa" : "#8b5cf6"
  };
}

function updateAllChartsTheme() {
  const colors = getThemeColors();
  Object.values(AppState.charts).forEach(chart => {
    if (!chart) return;
    if (chart.options.scales) {
      Object.values(chart.options.scales).forEach(scale => {
        if (scale.ticks) scale.ticks.color = colors.textColor;
        if (scale.grid) scale.grid.color = colors.gridColor;
        if (scale.title) scale.title.color = colors.textColor;
      });
    }
    if (chart.options.plugins && chart.options.plugins.legend) {
      if (chart.options.plugins.legend.labels) {
        chart.options.plugins.legend.labels.color = colors.textColor;
      }
    }
    chart.update();
  });
}

// ==========================================================================
// Navigation & Tab Switching
// ==========================================================================
function switchTab(tabId) {
  AppState.currentTab = tabId;

  // Update nav pills
  document.querySelectorAll(".nav-pill-btn").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
  });

  // Update view sections
  document.querySelectorAll(".view-section").forEach(sec => {
    sec.classList.toggle("active", sec.id === `view-${tabId}`);
  });

  // Trigger contextual tab refreshes
  if (tabId === "dashboard") {
    loadDashboard();
  } else if (tabId === "results") {
    loadScreeningResults();
  } else if (tabId === "features") {
    loadFeaturesTable();
  } else if (tabId === "component") {
    if (AppState.activeComponentId) {
      loadComponentAnalysis(AppState.activeComponentId);
    } else {
      fetchFirstComponent();
    }
  } else if (tabId === "comparison") {
    loadModelComparison();
  } else if (tabId === "reports") {
    loadPastRunsList();
  } else if (tabId === "settings") {
    loadSettings();
  }
}

// ==========================================================================
// Toast Notifications
// ==========================================================================
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `glass-toast toast-${type}`;
  
  let iconSvg;
  if (type === "success") {
    iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-check-circle-2 icon-emerald"><circle cx="12" cy="12" r="10" /><path d="m9 12 2 2 4-4" /></svg>`;
  } else if (type === "error") {
    iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-alert-octagon icon-rose"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>`;
  } else if (type === "warning") {
    iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-alert-triangle icon-amber"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>`;
  } else {
    iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-info icon-blue"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" /></svg>`;
  }

  toast.innerHTML = `<span style="display:inline-flex; align-items:center; flex-shrink:0;">${iconSvg}</span> <span>${message}</span>`;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ==========================================================================
// File Upload & Dataset Management
// ==========================================================================
async function checkDatasetStatus() {
  try {
    const res = await fetch("/api/dataset-info");
    const data = await res.json();
    AppState.datasetInfo = data;

    const statusPill = document.getElementById("header-status-text");
    const statusDot = document.getElementById("header-status-dot");

    if (data.has_dataset) {
      statusPill.textContent = `${data.file_info.filename} (${data.file_info.total_records} rows)`;
      statusDot.classList.add("active");
      document.getElementById("upload-file-info-card").style.display = "block";
      renderFileInfo(data.file_info);

      if (data.is_screened) {
        loadDashboard();
      } else if (data.is_audited) {
        switchTab("models");
      }
    } else {
      statusPill.textContent = "No Dataset Loaded";
      statusDot.classList.remove("active");
      document.getElementById("upload-file-info-card").style.display = "none";
    }
  } catch (err) {
    console.error("Status check failed", err);
  }
}

function renderFileInfo(info) {
  document.getElementById("fi-filename").textContent = info.filename;
  document.getElementById("fi-size").textContent = `${info.size_kb} KB`;
  document.getElementById("fi-records").textContent = info.total_records;
  document.getElementById("fi-time").textContent = info.upload_timestamp;
  document.getElementById("fi-hash").textContent = info.sha256.substring(0, 16) + "...";
}

async function handleFileUpload(file) {
  if (!file) return;
  resetComponentDropdowns();
  const formData = new FormData();
  formData.append("file", file);

  showToast(`Uploading ${file.name}...`, "info");
  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    showToast("File uploaded successfully. Confirm column mapping.", "success");
    checkDatasetStatus();
    openMappingModal(data.raw_columns, data.mapping);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function loadSampleBenchmark() {
  resetComponentDropdowns();
  showToast("Loading industry HTOL benchmark dataset...", "info");
  try {
    const res = await fetch("/api/load-sample", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Sample load failed");

    showToast("Benchmark dataset loaded. Running automated audit & screening...", "success");
    await checkDatasetStatus();
    
    // Automatically execute audit and ML screening for frictionless first experience
    await runDataAudit();
    await runAnomalyModels();
    switchTab("dashboard");
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Column Mapping Modal
function openMappingModal(rawCols, autoMapping) {
  const modal = document.getElementById("mapping-modal");
  const container = document.getElementById("mapping-fields-container");
  container.innerHTML = "";

  const canonicalDefs = [
    { key: "component_id", label: "Component ID (DUT)", req: true },
    { key: "batch_id", label: "Batch / Lot ID", req: false },
    { key: "test_id", label: "Test Condition / Chamber", req: false },
    { key: "timestamp", label: "Timestamp / Elapsed Hours", req: true },
    { key: "temperature", label: "Temperature (°C)", req: false },
    { key: "voltage", label: "Voltage (V)", req: false },
    { key: "current", label: "Current (mA)", req: false },
    { key: "resistance", label: "Resistance (mΩ / Ω)", req: false },
    { key: "leakage_current", label: "Leakage Current (µA)", req: false },
    { key: "power_consumption", label: "Power Consumption (mW)", req: false }
  ];

  canonicalDefs.forEach(item => {
    const row = document.createElement("div");
    row.className = "form-group";
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.justifyContent = "space-between";
    row.style.gap = "14px";

    const label = document.createElement("label");
    label.className = "form-label";
    label.style.minWidth = "220px";
    label.innerHTML = `${item.label} ${item.req ? '<span style="color:var(--accent-rose)">*</span>' : ''}`;

    const select = document.createElement("select");
    select.className = "glass-select";
    select.setAttribute("data-canon", item.key);

    const noneOpt = document.createElement("option");
    noneOpt.value = "";
    noneOpt.textContent = "-- Unmapped / Exclude --";
    select.appendChild(noneOpt);

    rawCols.forEach(rc => {
      const opt = document.createElement("option");
      opt.value = rc;
      opt.textContent = rc;
      if (autoMapping[item.key] === rc) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });

    row.appendChild(label);
    row.appendChild(select);
    container.appendChild(row);
  });

  modal.classList.add("open");
}

function closeMappingModal() {
  document.getElementById("mapping-modal").classList.remove("open");
}

async function submitMapping() {
  const selects = document.querySelectorAll("#mapping-fields-container select");
  const mapping = {};
  selects.forEach(sel => {
    const canon = sel.getAttribute("data-canon");
    mapping[canon] = sel.value || null;
  });

  try {
    const res = await fetch("/api/apply-mapping", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mapping })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    closeMappingModal();
    showToast("Column mapping confirmed. Proceeding to Data Quality Audit.", "success");
    await runDataAudit();
    switchTab("quality");
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================================================
// Data Quality & Preprocessing
// ==========================================================================
async function runDataAudit() {
  showToast("Executing data validation & quality audit...", "info");
  try {
    const res = await fetch("/api/run-audit", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    renderAuditSummary(data.audit_summary, data.warnings);
    showToast("Data Quality Audit completed.", "success");
    return data;
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderAuditSummary(summary, warnings) {
  document.getElementById("qa-total-records").textContent = `${summary.clean_rows} / ${summary.initial_rows}`;
  document.getElementById("qa-components").textContent = summary.total_components;
  document.getElementById("qa-batches").textContent = summary.total_batches;
  document.getElementById("qa-channels").textContent = summary.measurement_count;
  document.getElementById("qa-grade").textContent = summary.quality_grade;

  document.getElementById("qa-min-obs").textContent = summary.obs_per_component.min;
  document.getElementById("qa-max-obs").textContent = summary.obs_per_component.max;
  document.getElementById("qa-mean-obs").textContent = summary.obs_per_component.mean;
  document.getElementById("qa-dt-mean").textContent = `${summary.sampling_intervals.mean_dt_hours} h`;
  document.getElementById("qa-dt-regular").textContent = summary.sampling_intervals.is_regular_sampling ? "Yes (Uniform)" : "Irregular (Time Normalised)";

  // Warnings
  const warnContainer = document.getElementById("qa-warnings-container");
  warnContainer.innerHTML = "";
  if (warnings && warnings.length > 0) {
    warnings.forEach(w => {
      const banner = document.createElement("div");
      banner.className = "glass-banner banner-warning";
      banner.style.marginBottom = "8px";
      banner.innerHTML = `<span style="display:inline-flex; align-items:center; flex-shrink:0;"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-alert-triangle icon-amber"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg></span> <span>${w}</span>`;
      warnContainer.appendChild(banner);
    });
  } else {
    warnContainer.innerHTML = `<div class="glass-banner banner-info"><span style="display:inline-flex; align-items:center; flex-shrink:0;"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-check-circle-2 icon-emerald"><circle cx="12" cy="12" r="10" /><path d="m9 12 2 2 4-4" /></svg></span> <span>Dataset is mathematically healthy and ready for unsupervised anomaly detection.</span></div>`;
  }
}

// ==========================================================================
// Feature Engineering View
// ==========================================================================
async function loadFeaturesTable() {
  try {
    const res = await fetch("/api/features?page=1&page_size=30");
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    const thead = document.getElementById("features-table-head");
    const tbody = document.getElementById("features-table-body");
    thead.innerHTML = "";
    tbody.innerHTML = "";

    if (!data.records || data.records.length === 0) return;

    // Build headers
    const cols = ["component_id", "batch_id", "n_observations"];
    const allKeys = Object.keys(data.records[0]);
    const degradationCols = allKeys.filter(k => 
      !cols.includes(k) && 
      (k.endsWith("_slope") || k.endsWith("_cv") || k.endsWith("_pct_change") || k.endsWith("_instability_mean") || k.endsWith("_cumulative_drift"))
    ).slice(0, 6);

    const displayCols = [...cols, ...degradationCols];
    const headerRow = document.createElement("tr");
    displayCols.forEach(c => {
      const th = document.createElement("th");
      th.textContent = c.replace(/_/g, " ").toUpperCase();
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    // Build rows
    data.records.forEach(r => {
      const tr = document.createElement("tr");
      tr.addEventListener("click", () => {
        AppState.activeComponentId = r.component_id;
        switchTab("component");
      });
      displayCols.forEach(c => {
        const td = document.createElement("td");
        const val = r[c];
        td.textContent = typeof val === "number" ? (Number.isInteger(val) ? val : val.toFixed(4)) : (val || "—");
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Features load failed", err);
  }
}

// ==========================================================================
// Unsupervised Anomaly Detection Execution
// ==========================================================================
async function runAnomalyModels() {
  const btn = document.getElementById("btn-run-screening");
  if (btn) btn.disabled = true;
  showToast("Training and scoring unsupervised models (Isolation Forest, LOF, OCSVM, PCA)...", "info");

  // Read model parameters from controls
  const contamination = parseFloat(document.getElementById("param-contamination")?.value || 0.08);
  const n_trees = parseInt(document.getElementById("param-if-trees")?.value || 150);
  const lof_k = parseInt(document.getElementById("param-lof-k")?.value || 20);
  const ocsvm_nu = parseFloat(document.getElementById("param-ocsvm-nu")?.value || contamination);
  const pca_k = parseInt(document.getElementById("param-pca-k")?.value || 3);

  const payload = {
    algorithms: ["isolation_forest", "lof", "one_class_svm", "pca_reconstruction"],
    params: {
      contamination: contamination,
      if_n_estimators: n_trees,
      lof_n_neighbors: lof_k,
      ocsvm_nu: ocsvm_nu,
      pca_components: pca_k
    }
  };

  try {
    const res = await fetch("/api/run-models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    showToast(`Screening complete! Identified ${data.high_anomaly_count} High Anomaly and ${data.suspicious_count} Suspicious components.`, "success");
    await loadDashboard();
    switchTab("dashboard");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ==========================================================================
// Dashboard View & Visualizations
// ==========================================================================
async function loadDashboard() {
  try {
    const res = await fetch("/api/dashboard");
    const data = await res.json();
    if (!data.is_ready) {
      document.getElementById("dashboard-empty-state").style.display = "block";
      document.getElementById("dashboard-content").style.display = "none";
      return;
    }

    document.getElementById("dashboard-empty-state").style.display = "none";
    document.getElementById("dashboard-content").style.display = "block";
    AppState.dashboardData = data;

    // Render KPIs
    const kpis = data.kpis;
    document.getElementById("kpi-total").textContent = kpis.total_screened;
    document.getElementById("kpi-normal").textContent = kpis.normal_count;
    document.getElementById("kpi-suspicious").textContent = kpis.suspicious_count;
    document.getElementById("kpi-high").textContent = kpis.high_anomaly_count;
    document.getElementById("kpi-hidden").textContent = kpis.hidden_degradation_risks;
    document.getElementById("kpi-static-fail").textContent = kpis.static_limit_failures;

    renderCategoryDoughnut(data.category_counts);
    renderScoreDistribution(data.score_distribution);
    renderBatchBreakdown(data.batch_breakdown);
    renderDegradationScatter(data.scatter_data);
    renderTopFlaggedTable(data.top_flagged);
  } catch (err) {
    console.error("Dashboard load failed", err);
  }
}

function renderCategoryDoughnut(cats) {
  const ctx = document.getElementById("chart-category-doughnut")?.getContext("2d");
  if (!ctx) return;
  const colors = getThemeColors();

  if (AppState.charts.category) AppState.charts.category.destroy();

  AppState.charts.category = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Normal", "Suspicious", "High Anomaly"],
      datasets: [{
        data: [cats["Normal"] || 0, cats["Suspicious"] || 0, cats["High Anomaly"] || 0],
        backgroundColor: [colors.normalColor, colors.suspColor, colors.highColor],
        borderWidth: 2,
        borderColor: AppState.theme === "dark" ? "#070a13" : "#ffffff"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: colors.textColor, font: { size: 12, weight: 600 } }
        }
      },
      cutout: "70%"
    }
  });
}

function renderScoreDistribution(dist) {
  const ctx = document.getElementById("chart-score-dist")?.getContext("2d");
  if (!ctx) return;
  const colors = getThemeColors();

  if (AppState.charts.scores) AppState.charts.scores.destroy();

  AppState.charts.scores = new Chart(ctx, {
    type: "bar",
    data: {
      labels: dist.bins,
      datasets: [{
        label: "Component Count",
        data: dist.counts,
        backgroundColor: colors.blueColor,
        borderRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          ticks: { color: colors.textColor },
          grid: { color: colors.gridColor }
        },
        y: {
          ticks: { color: colors.textColor, stepSize: 1 },
          grid: { color: colors.gridColor }
        }
      }
    }
  });
}

function renderBatchBreakdown(batches) {
  const ctx = document.getElementById("chart-batch-breakdown")?.getContext("2d");
  if (!ctx) return;
  const colors = getThemeColors();

  if (AppState.charts.batch) AppState.charts.batch.destroy();

  AppState.charts.batch = new Chart(ctx, {
    type: "bar",
    data: {
      labels: batches.map(b => b.batch_id),
      datasets: [
        { label: "Normal", data: batches.map(b => b.normal), backgroundColor: colors.normalColor, borderRadius: 6 },
        { label: "Suspicious", data: batches.map(b => b.suspicious), backgroundColor: colors.suspColor, borderRadius: 6 },
        { label: "High Anomaly", data: batches.map(b => b.high), backgroundColor: colors.highColor, borderRadius: 6 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { stacked: true, ticks: { color: colors.textColor }, grid: { color: colors.gridColor } },
        y: { stacked: true, ticks: { color: colors.textColor }, grid: { color: colors.gridColor } }
      },
      plugins: {
        legend: { position: "bottom", labels: { color: colors.textColor } }
      }
    }
  });
}

function renderDegradationScatter(scatter) {
  const ctx = document.getElementById("chart-degradation-scatter")?.getContext("2d");
  if (!ctx) return;
  const colors = getThemeColors();

  if (AppState.charts.scatter) AppState.charts.scatter.destroy();

  const normalPts = scatter.points.filter(p => p.category === "Normal").map(p => ({ x: p.slope, y: p.instability, comp: p.component_id }));
  const suspPts = scatter.points.filter(p => p.category === "Suspicious").map(p => ({ x: p.slope, y: p.instability, comp: p.component_id }));
  const highPts = scatter.points.filter(p => p.category === "High Anomaly").map(p => ({ x: p.slope, y: p.instability, comp: p.component_id }));

  AppState.charts.scatter = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        { label: "Normal", data: normalPts, backgroundColor: colors.normalColor, pointRadius: 5 },
        { label: "Suspicious", data: suspPts, backgroundColor: colors.suspColor, pointRadius: 7, pointHoverRadius: 10 },
        { label: "High Anomaly", data: highPts, backgroundColor: colors.highColor, pointRadius: 8, pointHoverRadius: 11 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: colors.textColor } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.raw.comp}: Slope=${ctx.raw.x.toFixed(4)}, Instability=${ctx.raw.y.toFixed(4)}`
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: `${scatter.parameter.toUpperCase()} Degradation Slope (Δ/h)`, color: colors.textColor },
          ticks: { color: colors.textColor },
          grid: { color: colors.gridColor }
        },
        y: {
          title: { display: true, text: "Measurement Instability (Rolling Std)", color: colors.textColor },
          ticks: { color: colors.textColor },
          grid: { color: colors.gridColor }
        }
      }
    }
  });
}

function renderTopFlaggedTable(flagged) {
  const tbody = document.getElementById("top-flagged-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (!flagged || flagged.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 20px;">No suspicious or high-anomaly components detected.</td></tr>`;
    return;
  }

  flagged.forEach(f => {
    const tr = document.createElement("tr");
    tr.addEventListener("click", () => {
      AppState.activeComponentId = f.component_id;
      switchTab("component");
    });

    const catBadge = f.screening_category === "High Anomaly" ? 
      `<span class="glass-badge badge-high">High Anomaly</span>` : 
      `<span class="glass-badge badge-suspicious">Suspicious</span>`;

    const limitBadge = f.exceeds_static_limits ? 
      `<span class="glass-badge badge-static-fail">Exceeds Limits</span>` : 
      `<span class="glass-badge badge-normal">Passes Limits</span>`;

    const hiddenBadge = f.is_hidden_degradation_risk ? 
      `<span class="glass-badge badge-hidden-risk" title="Passes static limits but flagged by trajectory ML">Hidden Risk</span>` : "";

    tr.innerHTML = `
      <td><strong>${f.component_id}</strong></td>
      <td>${f.batch_id}</td>
      <td>${catBadge}</td>
      <td><strong>${f.composite_anomaly_score.toFixed(1)}</strong> / 100</td>
      <td>${limitBadge} ${hiddenBadge}</td>
      <td>
        <button class="btn-glass btn-secondary" style="padding: 4px 10px; font-size: 11px; display:inline-flex; align-items:center; gap:4px;">
          Inspect
          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chevron-right">
            <path d="m9 18 6-6-6-6" />
          </svg>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// Live Threshold Adjustment Handler
function handleThresholdSliderChange() {
  const susp = parseFloat(document.getElementById("dash-slider-susp").value);
  const high = parseFloat(document.getElementById("dash-slider-high").value);

  document.getElementById("dash-val-susp").textContent = susp;
  document.getElementById("dash-val-high").textContent = high;

  clearTimeout(AppState.thresholdDebounceTimer);
  AppState.thresholdDebounceTimer = setTimeout(async () => {
    try {
      await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          threshold_suspicious: susp,
          threshold_high: high
        })
      });
      loadDashboard();
      if (AppState.currentTab === "results") loadScreeningResults();
    } catch (err) {
      console.error("Live threshold update failed", err);
    }
  }, 300);
}

// ==========================================================================
// Screening Results View & Filtering
// ==========================================================================
async function loadScreeningResults() {
  const catFilter = document.getElementById("filter-category")?.value || "All";
  const batchFilter = document.getElementById("filter-batch")?.value || "All";
  const hiddenOnly = document.getElementById("filter-hidden-only")?.checked || false;
  const minScore = parseFloat(document.getElementById("filter-min-score")?.value || 0.0);
  const search = document.getElementById("filter-search")?.value || "";

  const queryParams = new URLSearchParams({
    category: catFilter,
    batch: batchFilter,
    hidden_only: hiddenOnly,
    min_score: minScore,
    search: search
  });

  try {
    const res = await fetch(`/api/screening-results?${queryParams.toString()}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    renderScreeningResultsTable(data.results);
    populateBatchFilterOptions(data.results);
  } catch (err) {
    console.error("Screening results load failed", err);
  }
}

function populateBatchFilterOptions(results) {
  const sel = document.getElementById("filter-batch");
  if (!sel || sel.children.length > 1) return;
  const batches = [...new Set(results.map(r => r.batch_id))];
  batches.forEach(b => {
    const opt = document.createElement("option");
    opt.value = b;
    opt.textContent = b;
    sel.appendChild(opt);
  });
}

function renderScreeningResultsTable(results) {
  const tbody = document.getElementById("screening-results-table-body");
  const countSpan = document.getElementById("screening-results-count");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (countSpan) countSpan.textContent = `${results.length} Components`;

  if (!results || results.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px;">No components matching active filter criteria.</td></tr>`;
    return;
  }

  results.forEach(r => {
    const tr = document.createElement("tr");
    tr.addEventListener("click", () => {
      AppState.activeComponentId = r.component_id;
      switchTab("component");
    });

    const catBadge = r.screening_category === "High Anomaly" ? 
      `<span class="glass-badge badge-high">High Anomaly</span>` : 
      r.screening_category === "Suspicious" ? 
      `<span class="glass-badge badge-suspicious">Suspicious</span>` : 
      `<span class="glass-badge badge-normal">Normal</span>`;

    const limitBadge = r.exceeds_static_limits ? 
      `<span class="glass-badge badge-static-fail">Exceeds Limits</span>` : 
      `<span class="glass-badge badge-normal">Within Limits</span>`;

    const hiddenBadge = r.is_hidden_degradation_risk ? 
      `<span class="glass-badge badge-hidden-risk">Hidden Risk</span>` : "";

    tr.innerHTML = `
      <td><strong>${r.component_id}</strong></td>
      <td>${r.batch_id}</td>
      <td>${catBadge}</td>
      <td><strong>${r.composite_anomaly_score.toFixed(1)}</strong></td>
      <td>${limitBadge} ${hiddenBadge}</td>
      <td><span style="font-size:12px; color:var(--text-secondary)">${r.screening_verdict}</span></td>
      <td>
        <button class="btn-glass btn-secondary" style="padding: 4px 10px; font-size: 11px; display:inline-flex; align-items:center; gap:4px;">
          Deep Dive
          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chevron-right">
            <path d="m9 18 6-6-6-6" />
          </svg>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// ==========================================================================
// Component Deep-Dive Analysis & Dual-Component Comparison
// ==========================================================================
async function loadComponentAnalysis(compId) {
  if (!compId) return;
  AppState.activeComponentId = compId;

  try {
    const res = await fetch(`/api/component/${compId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    AppState.activeComponentData = data;
    await populateComponentDropdowns();

    document.getElementById("cd-component-id").textContent = data.component_id;
    document.getElementById("cd-batch").textContent = data.batch_id;
    document.getElementById("cd-condition").textContent = data.test_id;
    document.getElementById("cd-score").textContent = `${data.screening.composite_anomaly_score.toFixed(1)} / 100`;

    const catBadge = document.getElementById("cd-cat-badge");
    catBadge.textContent = data.screening.screening_category;
    catBadge.className = `glass-badge ${data.screening.screening_category === 'High Anomaly' ? 'badge-high' : data.screening.screening_category === 'Suspicious' ? 'badge-suspicious' : 'badge-normal'}`;

    const limitBadge = document.getElementById("cd-limit-badge");
    limitBadge.textContent = data.screening.exceeds_static_limits ? "Exceeds Static Limits" : "Passes Static Limits";
    limitBadge.className = `glass-badge ${data.screening.exceeds_static_limits ? 'badge-static-fail' : 'badge-normal'}`;

    const hiddenBanner = document.getElementById("cd-hidden-risk-banner");
    if (data.screening.is_hidden_degradation_risk) {
      hiddenBanner.style.display = "flex";
    } else {
      hiddenBanner.style.display = "none";
    }

    // Render Explainability Reasons
    const expContainer = document.getElementById("cd-explanations-list");
    expContainer.innerHTML = "";
    if (data.explanation && data.explanation.primary_explanations) {
      data.explanation.primary_explanations.forEach(r => {
        const li = document.createElement("li");
        li.style.marginBottom = "8px";
        li.style.color = "var(--text-primary)";
        li.innerHTML = r;
        expContainer.appendChild(li);
      });
    }

    // Render Deviations Table
    const devTable = document.getElementById("cd-deviations-table-body");
    devTable.innerHTML = "";
    if (data.explanation && data.explanation.top_deviations) {
      data.explanation.top_deviations.forEach(d => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${d.parameter.toUpperCase()}</strong></td>
          <td>${d.metric}</td>
          <td>${d.value}</td>
          <td>${d.cohort_mean}</td>
          <td>${d.z_score ? `${d.z_score > 0 ? '+' : ''}${d.z_score}σ` : `${d.ratio_to_median}x`}</td>
          <td><span class="glass-badge ${d.significance === 'HIGH' ? 'badge-high' : 'badge-suspicious'}">${d.significance}</span></td>
        `;
        devTable.appendChild(tr);
      });
    }

    // Populate channel switcher buttons
    renderChannelSwitcher(data.available_channels, data.curves);

    // If a comparison component is selected, load it too
    if (AppState.comparisonComponentId) {
      await loadComparisonComponent(AppState.comparisonComponentId);
    } else {
      document.getElementById("compare-summary-row").style.display = "none";
      renderComponentCurveChart(data.curves, AppState.activeChannel);
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function loadComparisonComponent(cmpId) {
  if (!cmpId) {
    AppState.comparisonComponentId = null;
    AppState.comparisonComponentData = null;
    document.getElementById("compare-summary-row").style.display = "none";
    if (AppState.activeComponentData) {
      renderComponentCurveChart(AppState.activeComponentData.curves, AppState.activeChannel);
    }
    return;
  }

  AppState.comparisonComponentId = cmpId;
  try {
    const res = await fetch(`/api/component/${cmpId}`);
    const cmpData = await res.json();
    if (!res.ok) throw new Error(cmpData.detail);

    AppState.comparisonComponentData = cmpData;

    // Render side-by-side comparison summary
    const compRow = document.getElementById("compare-summary-row");
    compRow.style.display = "block";
    document.getElementById("cmp-primary-name").textContent = AppState.activeComponentId;
    document.getElementById("cmp-secondary-name").textContent = cmpId;

    const primaryFeats = AppState.activeComponentData.features;
    const cmpFeats = cmpData.features;
    const ch = AppState.activeChannel;

    const pInit = primaryFeats[`${ch}_init`] ?? 0;
    const cInit = cmpFeats[`${ch}_init`] ?? 0;
    const pFinal = primaryFeats[`${ch}_final`] ?? 0;
    const cFinal = cmpFeats[`${ch}_final`] ?? 0;
    const pSlope = primaryFeats[`${ch}_slope`] ?? 0;
    const cSlope = cmpFeats[`${ch}_slope`] ?? 0;
    const pInstab = primaryFeats[`${ch}_instability_mean`] ?? 0;
    const cInstab = cmpFeats[`${ch}_instability_mean`] ?? 0;

    const grid = document.getElementById("cmp-metrics-grid");
    grid.innerHTML = `
      <div style="background:var(--glass-surface); padding:8px 12px; border-radius:10px;">
        <div style="color:var(--text-muted); font-size:11px;">Initial ${ch.toUpperCase()}</div>
        <div><strong>${pInit.toFixed(2)}</strong> vs <strong>${cInit.toFixed(2)}</strong></div>
      </div>
      <div style="background:var(--glass-surface); padding:8px 12px; border-radius:10px;">
        <div style="color:var(--text-muted); font-size:11px;">Final ${ch.toUpperCase()}</div>
        <div><strong>${pFinal.toFixed(2)}</strong> vs <strong>${cFinal.toFixed(2)}</strong></div>
      </div>
      <div style="background:var(--glass-surface); padding:8px 12px; border-radius:10px;">
        <div style="color:var(--text-muted); font-size:11px;">Degradation Slope</div>
        <div><strong style="color:var(--accent-rose);">${pSlope.toFixed(4)}/h</strong> vs <strong style="color:var(--accent-emerald);">${cSlope.toFixed(4)}/h</strong></div>
      </div>
      <div style="background:var(--glass-surface); padding:8px 12px; border-radius:10px;">
        <div style="color:var(--text-muted); font-size:11px;">Measurement Instability</div>
        <div><strong>${pInstab.toFixed(4)}</strong> vs <strong>${cInstab.toFixed(4)}</strong></div>
      </div>
    `;

    renderComponentCurveChart(AppState.activeComponentData.curves, AppState.activeChannel, cmpData.curves);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function resetComponentDropdowns() {
  const selPrimary = document.getElementById("component-selector-dropdown");
  const selCompare = document.getElementById("component-compare-dropdown");
  if (selPrimary) selPrimary.innerHTML = "";
  if (selCompare) selCompare.innerHTML = '<option value="">-- No Comparison --</option>';
  AppState.activeComponentId = null;
  AppState.comparisonComponentId = null;
  AppState.comparisonComponentData = null;
}

async function populateComponentDropdowns() {
  const selPrimary = document.getElementById("component-selector-dropdown");
  const selCompare = document.getElementById("component-compare-dropdown");
  if (!selPrimary) return;

  // If already populated, synchronize selected values and return
  if (selPrimary.children.length > 0) {
    if (AppState.activeComponentId) {
      selPrimary.value = AppState.activeComponentId;
    }
    if (selCompare && AppState.comparisonComponentId) {
      selCompare.value = AppState.comparisonComponentId;
    }
    return;
  }

  const res = await fetch("/api/screening-results");
  const data = await res.json();
  if (!data.results) return;

  selPrimary.innerHTML = "";
  selCompare.innerHTML = '<option value="">-- No Comparison --</option>';

  data.results.forEach(r => {
    const optPrimary = document.createElement("option");
    optPrimary.value = r.component_id;
    optPrimary.textContent = `${r.component_id} (${r.screening_category} - ${r.composite_anomaly_score.toFixed(0)})`;
    if (r.component_id === AppState.activeComponentId) optPrimary.selected = true;
    selPrimary.appendChild(optPrimary);

    const optCompare = document.createElement("option");
    optCompare.value = r.component_id;
    optCompare.textContent = `${r.component_id} (${r.screening_category} - ${r.composite_anomaly_score.toFixed(0)})`;
    if (r.component_id === AppState.comparisonComponentId) optCompare.selected = true;
    selCompare.appendChild(optCompare);
  });
}

function renderChannelSwitcher(channels, curves) {
  const container = document.getElementById("channel-switcher-buttons");
  if (!container) return;
  container.innerHTML = "";

  if (channels && channels.length > 0 && !channels.includes(AppState.activeChannel)) {
    AppState.activeChannel = channels[0];
  }

  channels.forEach(ch => {
    const btn = document.createElement("button");
    btn.className = `btn-glass ${AppState.activeChannel === ch ? 'btn-primary' : 'btn-secondary'}`;
    btn.style.padding = "6px 14px";
    btn.style.fontSize = "12px";
    btn.textContent = ch.toUpperCase();
    btn.addEventListener("click", () => {
      AppState.activeChannel = ch;
      renderChannelSwitcher(channels, curves);
      if (AppState.comparisonComponentData) {
        renderComponentCurveChart(curves, ch, AppState.comparisonComponentData.curves);
      } else {
        renderComponentCurveChart(curves, ch);
      }
    });
    container.appendChild(btn);
  });
}

function renderComponentCurveChart(curves, channel, compareCurves = null) {
  const ctx = document.getElementById("chart-component-curve")?.getContext("2d");
  if (!ctx) return;
  const colors = getThemeColors();

  if (AppState.charts.curve) AppState.charts.curve.destroy();

  const chData = curves[channel];
  if (!chData) return;

  const times = chData.component_history.map(pt => pt.elapsed_time);
  const values = chData.component_history.map(pt => pt[channel]);

  const cohortMean = chData.cohort_envelope.map(e => e.mean);
  const cohortUpper = chData.cohort_envelope.map(e => e.mean + 2 * e.std);
  const cohortLower = chData.cohort_envelope.map(e => e.mean - 2 * e.std);

  const datasets = [
    {
      label: `${AppState.activeComponentId} (${channel.toUpperCase()})`,
      data: values,
      borderColor: colors.highColor,
      backgroundColor: colors.highColor,
      borderWidth: 3,
      pointRadius: 6,
      pointHoverRadius: 9,
      tension: 0.2
    }
  ];

  // If compareCurves provided, add comparison trace
  if (compareCurves && compareCurves[channel]) {
    const cmpValues = compareCurves[channel].component_history.map(pt => pt[channel]);
    datasets.push({
      label: `Reference: ${AppState.comparisonComponentId} (${channel.toUpperCase()})`,
      data: cmpValues,
      borderColor: colors.normalColor,
      backgroundColor: colors.normalColor,
      borderWidth: 2.5,
      borderDash: [2, 2],
      pointRadius: 5,
      pointHoverRadius: 8,
      tension: 0.2
    });
  }

  // Add Cohort Envelope
  datasets.push(
    {
      label: "Cohort Mean (Comparable Condition)",
      data: cohortMean,
      borderColor: colors.blueColor,
      borderDash: [5, 5],
      pointRadius: 3,
      borderWidth: 2,
      fill: false
    },
    {
      label: "Cohort +2σ Band",
      data: cohortUpper,
      borderColor: "rgba(56, 189, 248, 0.2)",
      borderWidth: 1,
      pointRadius: 0,
      fill: "+1",
      backgroundColor: "rgba(56, 189, 248, 0.08)"
    },
    {
      label: "Cohort -2σ Band",
      data: cohortLower,
      borderColor: "rgba(56, 189, 248, 0.2)",
      borderWidth: 1,
      pointRadius: 0,
      fill: false
    }
  );

  AppState.charts.curve = new Chart(ctx, {
    type: "line",
    data: {
      labels: times.map(t => `${t}h`),
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { color: colors.textColor } }
      },
      scales: {
        x: {
          title: { display: true, text: "Elapsed Burn-in Time (Hours)", color: colors.textColor },
          ticks: { color: colors.textColor },
          grid: { color: colors.gridColor }
        },
        y: {
          title: { display: true, text: `${channel.toUpperCase()} Reading`, color: colors.textColor },
          ticks: { color: colors.textColor },
          grid: { color: colors.gridColor }
        }
      }
    }
  });
}

// ==========================================================================
// Model Comparison View
// ==========================================================================
async function loadModelComparison() {
  try {
    const res = await fetch("/api/model-comparison");
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    // Render Algorithm Cards
    const cardsContainer = document.getElementById("model-comparison-cards");
    cardsContainer.innerHTML = "";
    data.algorithms.forEach(algo => {
      const card = document.createElement("div");
      card.className = "kpi-tile";

      let algoIcon = "";
      if (algo.key === "isolation_forest" || algo.name.includes("Isolation")) {
        algoIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-git-fork" style="color:var(--accent-blue);"><circle cx="12" cy="18" r="3" /><circle cx="6" cy="6" r="3" /><circle cx="18" cy="6" r="3" /><path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9" /><path d="M12 12v3" /></svg>`;
      } else if (algo.key === "lof" || algo.name.includes("Local Outlier")) {
        algoIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-radio" style="color:var(--accent-emerald);"><path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9" /><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5" /><circle cx="12" cy="12" r="2" /><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5" /><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19" /></svg>`;
      } else if (algo.key === "one_class_svm" || algo.name.includes("SVM")) {
        algoIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-crosshair" style="color:var(--accent-purple);"><circle cx="12" cy="12" r="10" /><line x1="22" x2="18" y1="12" y2="12" /><line x1="6" x2="2" y1="12" y2="12" /><line x1="12" x2="12" y1="6" y2="2" /><line x1="12" x2="12" y1="22" y2="18" /></svg>`;
      } else {
        algoIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-grid" style="color:var(--accent-amber);"><rect width="18" height="18" x="3" y="3" rx="2" /><line x1="3" x2="21" y1="9" y2="9" /><line x1="3" x2="21" y1="15" y2="15" /><line x1="9" x2="9" y1="3" y2="21" /><line x1="15" x2="15" y1="3" y2="21" /></svg>`;
      }

      card.innerHTML = `
        <div class="kpi-top">
          <span class="kpi-label" style="display:inline-flex; align-items:center; gap:6px;">${algoIcon} ${algo.name}</span>
          <span class="glass-badge badge-suspicious">${algo.flagged_pct}% Flagged</span>
        </div>
        <div class="kpi-value">${algo.flagged_count}</div>
        <div class="kpi-footer">${algo.description}</div>
      `;
      cardsContainer.appendChild(card);
    });

    // Render Overlap Agreement Chart
    renderAgreementChart(data.agreement_distribution);
  } catch (err) {
    console.error("Model comparison load failed", err);
  }
}

function renderAgreementChart(dist) {
  const ctx = document.getElementById("chart-model-agreement")?.getContext("2d");
  if (!ctx) return;
  const colors = getThemeColors();

  if (AppState.charts.agreement) AppState.charts.agreement.destroy();

  AppState.charts.agreement = new Chart(ctx, {
    type: "bar",
    data: {
      labels: Object.keys(dist).map(k => `${k} Model(s) Flagged`),
      datasets: [{
        label: "Components",
        data: Object.values(dist),
        backgroundColor: colors.purpleColor,
        borderRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: colors.textColor }, grid: { color: colors.gridColor } },
        y: { ticks: { color: colors.textColor, stepSize: 1 }, grid: { color: colors.gridColor } }
      }
    }
  });
}

// ==========================================================================
// Settings Management
// ==========================================================================
async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    if (data.settings) {
      const s = data.settings;
      if (s.threshold_suspicious !== undefined) {
        const el = document.getElementById("set-susp-thresh");
        if (el) el.value = s.threshold_suspicious;
      }
      if (s.threshold_high !== undefined) {
        const el = document.getElementById("set-high-thresh");
        if (el) el.value = s.threshold_high;
      }
      if (s.weights) {
        if (s.weights.isolation_forest !== undefined) {
          const el = document.getElementById("set-weight-if");
          if (el) el.value = s.weights.isolation_forest;
        }
        if (s.weights.lof !== undefined) {
          const el = document.getElementById("set-weight-lof");
          if (el) el.value = s.weights.lof;
        }
        if (s.weights.one_class_svm !== undefined) {
          const el = document.getElementById("set-weight-ocsvm");
          if (el) el.value = s.weights.one_class_svm;
        }
        if (s.weights.pca_reconstruction !== undefined) {
          const el = document.getElementById("set-weight-pca");
          if (el) el.value = s.weights.pca_reconstruction;
        }
      }
    }
  } catch (err) {
    console.error("Failed to load settings", err);
  }
}

async function saveSettings() {
  const susp = parseFloat(document.getElementById("set-susp-thresh")?.value || 60);
  const high = parseFloat(document.getElementById("set-high-thresh")?.value || 80);
  const w_if = parseFloat(document.getElementById("set-weight-if")?.value || 0.30);
  const w_lof = parseFloat(document.getElementById("set-weight-lof")?.value || 0.25);
  const w_ocsvm = parseFloat(document.getElementById("set-weight-ocsvm")?.value || 0.20);
  const w_pca = parseFloat(document.getElementById("set-weight-pca")?.value || 0.25);

  showToast("Saving screening settings...", "info");
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        threshold_suspicious: susp,
        threshold_high: high,
        weights: {
          isolation_forest: w_if,
          lof: w_lof,
          one_class_svm: w_ocsvm,
          pca_reconstruction: w_pca
        }
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    // Update live sliders on dashboard too
    const sliderSusp = document.getElementById("dash-slider-susp");
    const sliderHigh = document.getElementById("dash-slider-high");
    if (sliderSusp) sliderSusp.value = susp;
    if (sliderHigh) sliderHigh.value = high;
    const valSusp = document.getElementById("dash-val-susp");
    const valHigh = document.getElementById("dash-val-high");
    if (valSusp) valSusp.textContent = susp;
    if (valHigh) valHigh.textContent = high;

    showToast("Settings successfully saved and re-applied to screening scores!", "success");
    await loadDashboard();
    if (AppState.activeComponentId) {
      await loadComponentAnalysis(AppState.activeComponentId);
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================================================
// Historical Runs & Persistence
// ==========================================================================
async function loadPastRunsList() {
  const tbody = document.getElementById("past-runs-table-body");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 20px;">Loading historical runs...</td></tr>`;

  try {
    const res = await fetch("/api/runs");
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    const runs = data.runs || [];
    if (runs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 20px;">No saved screening runs found in database.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    runs.forEach(r => {
      const tr = document.createElement("tr");
      const isCurrent = r.run_id === AppState.datasetInfo?.current_run_id;
      const currentBadge = isCurrent ? '<span class="glass-badge badge-normal" style="margin-left:6px;">Active</span>' : '';

      tr.innerHTML = `
        <td><strong>${r.run_id}</strong> ${currentBadge}</td>
        <td>${r.run_timestamp || '—'}</td>
        <td>${r.dataset_filename || r.dataset_id || '—'}</td>
        <td><strong>${r.total_components ?? '—'}</strong></td>
        <td><span style="color:var(--accent-emerald)">${r.normal_count ?? 0}</span></td>
        <td><span style="color:var(--accent-amber)">${r.suspicious_count ?? 0}</span></td>
        <td><span style="color:var(--accent-rose)">${r.high_anomaly_count ?? 0}</span></td>
        <td><span style="color:var(--accent-purple)">${r.hidden_risk_count ?? 0}</span></td>
        <td>
          <button class="btn-glass ${isCurrent ? 'btn-secondary' : 'btn-primary'}" style="padding: 4px 10px; font-size: 11px; display:inline-flex; align-items:center; gap:4px;" onclick="restoreRun('${r.run_id}')">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-rotate-ccw">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
            </svg>
            ${isCurrent ? 'Reload' : 'Restore Run'}
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 20px; color:var(--accent-rose);">Failed to load past runs: ${err.message}</td></tr>`;
  }
}

async function restoreRun(runId) {
  showToast(`Restoring screening run ${runId}...`, "info");
  try {
    const res = await fetch(`/api/runs/${runId}/load`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    resetComponentDropdowns();
    showToast(`Run ${runId} successfully restored!`, "success");
    await checkDatasetStatus();
    await loadDashboard();
    switchTab("dashboard");
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function fetchFirstComponent() {
  try {
    const res = await fetch("/api/screening-results");
    const data = await res.json();
    if (data.results && data.results.length > 0) {
      loadComponentAnalysis(data.results[0].component_id);
    }
  } catch (err) {
    console.error("Could not fetch first component", err);
  }
}

// ==========================================================================
// Initialization & Event Listeners
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  checkDatasetStatus();

  // Theme Toggle Button
  document.getElementById("btn-toggle-theme")?.addEventListener("click", toggleTheme);

  // Tab Navigation Buttons
  document.querySelectorAll(".nav-pill-btn").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.getAttribute("data-tab")));
  });

  // Upload Actions
  const dropzone = document.getElementById("upload-dropzone");
  const fileInput = document.getElementById("file-input");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        resetComponentDropdowns();
        handleFileUpload(e.target.files[0]);
      }
    });

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files.length > 0) {
        resetComponentDropdowns();
        handleFileUpload(e.dataTransfer.files[0]);
      }
    });
  }

  // Load Benchmark Sample Button
  document.getElementById("btn-load-sample")?.addEventListener("click", () => {
    resetComponentDropdowns();
    loadSampleBenchmark();
  });
  document.getElementById("btn-empty-load-sample")?.addEventListener("click", () => {
    resetComponentDropdowns();
    loadSampleBenchmark();
  });

  // Mapping Modal Controls
  document.getElementById("btn-close-mapping")?.addEventListener("click", closeMappingModal);
  document.getElementById("btn-submit-mapping")?.addEventListener("click", submitMapping);

  // Run ML Screening Button
  document.getElementById("btn-run-screening")?.addEventListener("click", () => {
    resetComponentDropdowns();
    runAnomalyModels();
  });

  // Live Dashboard Sensitivity Sliders
  document.getElementById("dash-slider-susp")?.addEventListener("input", handleThresholdSliderChange);
  document.getElementById("dash-slider-high")?.addEventListener("input", handleThresholdSliderChange);
  document.getElementById("btn-reset-thresholds")?.addEventListener("click", () => {
    document.getElementById("dash-slider-susp").value = 60;
    document.getElementById("dash-slider-high").value = 80;
    handleThresholdSliderChange();
  });

  // Results Filter Controls
  document.getElementById("filter-category")?.addEventListener("change", loadScreeningResults);
  document.getElementById("filter-batch")?.addEventListener("change", loadScreeningResults);
  document.getElementById("filter-hidden-only")?.addEventListener("change", loadScreeningResults);
  document.getElementById("filter-search")?.addEventListener("input", loadScreeningResults);
  document.getElementById("filter-min-score")?.addEventListener("input", (e) => {
    document.getElementById("min-score-val").textContent = e.target.value;
    loadScreeningResults();
  });

  // Component Dropdown Change
  document.getElementById("component-selector-dropdown")?.addEventListener("change", (e) => {
    loadComponentAnalysis(e.target.value);
  });

  // Component Comparison Dropdown Change
  document.getElementById("component-compare-dropdown")?.addEventListener("change", (e) => {
    loadComparisonComponent(e.target.value);
  });

  // Settings Save Button
  document.getElementById("btn-save-settings")?.addEventListener("click", saveSettings);

  // Past Runs Refresh Button
  document.getElementById("btn-refresh-runs")?.addEventListener("click", loadPastRunsList);

  // Initialize Lucide Icons
  if (window.lucide && typeof window.lucide.createIcons === "function") {
    try {
      window.lucide.createIcons();
    } catch (e) {
      console.warn("Lucide initialization:", e);
    }
  }
});
