# BurninWatch – Component Screening Anomaly Detection

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.9%2B-F7931E.svg)](https://scikit-learn.org)
[![UI: Liquid Glassmorphism](https://img.shields.io/badge/UI-Liquid%20Glassmorphism-38bdf8.svg)](#iphone-inspired-liquid-glassmorphism-ui)
[![Tests: 20 Passed](https://img.shields.io/badge/Tests-20%20Passed-10b981.svg)](#automated-testing)

**BurninWatch** is an industrial-grade screening and anomaly detection system engineered for high-reliability electronic components (automotive-grade microcontrollers, power MOSFETs, precision analog ICs, aerospace gate drivers, and passive arrays) undergoing High-Temperature Operating Life (HTOL) and burn-in testing.

Traditional component screening relies almost exclusively on static upper/lower specification limits ($USL$ / $LSL$). However, early-life failures (infant mortality) often manifest as **gradual monotonic drift**, **micro-step level shifts**, or **elevated measurement instability** that technically remain inside wide static windows until deployed in the field. **BurninWatch** solves this challenge by deploying **Unsupervised Machine Learning** to analyze temporal degradation trajectories, flagging abnormal components without requiring pre-labeled training data.

---

## 🌟 Key Capabilities

- **Pure Python Architecture**: Built entirely on the modern Python scientific stack (`fastapi`, `uvicorn`, `scikit-learn`, `pandas`, `numpy`, `scipy`, `openpyxl`, `jinja2`).
- **Genuine Unsupervised ML**: Implements four complementary anomaly algorithms:
  - **Isolation Forest**: Identifies trajectory anomalies via recursive decision partitioning.
  - **Local Outlier Factor (LOF)**: Computes local density ratios against neighboring components in the same test condition.
  - **One-Class SVM**: Establishes non-linear support vector boundaries enclosing the normal degradation subspace.
  - **PCA Reconstruction Error**: Projects degradation profiles onto principal component subspaces and quantifies out-of-subspace residual energy.
- **Degradation-Focused Feature Engineering**:
  - Trajectory slopes ($\Delta/h$) via least-squares linear fits.
  - Cumulative drift and path tortuosity ratios.
  - Local measurement instability (rolling window standard deviation).
  - Maximum abrupt step jump ($\max |\Delta x_t|$) and exact timestamp of occurrence.
  - Coefficient of variation ($CV = \sigma / |\mu|$) and percentage shift.
  - Condition-stratified cohort $Z$-scores to prevent false cross-chamber comparisons.
- **Static vs. Trajectory Anomaly Separation**:
  - Automatically isolates **Hidden Degradation Risks** (components that pass static limits but exhibit abnormal degradation).
- **iPhone-Inspired Liquid Glassmorphism Interface**:
  - Translucent frosted glass panels with `backdrop-filter: blur(24px)`.
  - Floating pill navigation and dynamic theme toggle (**Light Mode** and **Dark Mode**) without page refreshes or state loss.
  - High-performance, reactive 60fps Chart.js visualizations that dynamically adapt color palettes to the active theme.
- **Automated Explainability**:
  - Transparent statistical explanations detailing exact parameter deviations, $Z$-scores, and anomalous time intervals without unsupported physical claims.
- **Auditable Reports & Persistence**:
  - Multi-sheet Excel (`.xlsx`) workbooks, CSV datasets, and standalone printable HTML executive audit reports.
  - SQLite metadata catalog with file-based persistence across server restarts.

---

## 🏗️ System Architecture

```
burninwatch/
├── core/
│   ├── data_loader.py          # Flexible CSV/Excel ingestion, auto-mapping, template generator
│   ├── preprocessor.py         # Missing-value imputation, duplicate cleanup, sampling regularity audit
│   ├── feature_engineering.py  # Degradation slope, drift, instability, and cohort z-scores
│   ├── models.py               # Isolation Forest, LOF, One-Class SVM, PCA Reconstruction Error
│   ├── scoring.py              # Calibrated 0-100 screening scoring & static limit separation
│   ├── explainability.py       # Deviation analysis, interval detection, statistical explanations
│   └── storage.py              # Persistent SQLite store and artifact directory manager
├── reporting/
│   └── exporter.py             # CSV, multi-tab Excel (.xlsx), and printable HTML audit reports
├── web/
│   ├── app.py                  # FastAPI REST API and view controller
│   ├── static/
│   │   ├── css/glassmorphism.css # Liquid Glass design system (Light & Dark themes)
│   │   └── js/app.js           # Reactive UI, Chart.js integrations, filters, modal dialogs
│   └── templates/
│       └── index.html          # Liquid Glass single-page application container
├── tests/                      # Automated test suite (20 comprehensive tests)
├── data/
│   ├── templates/burnin_template.csv     # Standard downloadable empty CSV template
│   ├── samples/htol_burnin_measurements.csv # Automotive HTOL benchmark dataset (60 components)
│   └── storage/                          # Persistent SQLite database and screening artifacts
├── run.py                      # Application launcher
└── requirements.txt            # Frozen Python dependencies
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13

### 2. Environment Setup
```bash
# Clone or navigate to the repository directory
cd burninwatch

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Launching the Application
```bash
python run.py
```
Open your web browser and navigate to:
**`http://127.0.0.1:8000`**

---

## 📊 End-to-End Workflow

1. **Data Upload**:
   - Upload any custom burn-in dataset (`.csv`, `.xlsx`, `.xls`) or click **"Load Automotive HTOL Benchmark"** for instant exploration.
   - Use the auto-detected column mapping modal to verify or remap custom column headers to canonical channels (Component ID, Batch, Timestamp, Voltage, Current, Resistance, Leakage, Power).
2. **Data Quality Audit**:
   - Inspect data hygiene: total components, clean rows, missing value imputations, duplicate resolutions, and sampling rate regularity ($\Delta t$).
3. **Feature Engineering**:
   - Review engineered degradation features ($R_{DS(on)}$ degradation slopes, leakage drift rates, local instability index, step jumps).
4. **Model Execution**:
   - Select individual or ensemble models (Isolation Forest, LOF, One-Class SVM, PCA Reconstruction).
   - Tune hyperparameters (contamination rate, trees, $k$-neighbors, SVM $\nu$, principal components).
   - Click **"Run Unsupervised Screening"**.
5. **Dashboard & Results**:
   - Explore executive KPIs, score distributions, lot-wise comparisons, and the Degradation Slope vs. Instability scatter plot.
   - Filter results to inspect **"Hidden Degradation Risks"** (devices that stayed strictly within static limits but were flagged by trajectory models).
6. **Component Deep Dive**:
   - Select any Device Under Test (DUT) to view its time-series curve plotted against the comparable batch cohort normal envelope ($\pm 2\sigma$).
   - Read transparent statistical explanations detailing why the component was flagged.
7. **Exporting Reports**:
   - Download the multi-sheet Excel audit workbook (`.xlsx`), CSV dataset, or open the printable HTML executive report.

---

## 🧪 Automated Testing

Run the automated test suite with pytest:
```bash
# Run all tests
.venv\Scripts\python -m pytest burninwatch/tests -v
```

The 20 automated tests validate:
- Header auto-detection and fuzzy alias matching.
- Semicolon and comma CSV parsing and format flexibility.
- Data cleansing, timestamp interpolation, and duplicate handling.
- Least-squares slope, cumulative drift, and rolling instability calculations without division-by-zero on flat signals.
- Step jump detection and quantitative root-cause explainability.
- Unsupervised model fitting and anomaly score normalization across all four algorithms.
- Static limit evaluation and hidden degradation risk isolation.
- Persistent SQLite run save, listing, and cold-start restore lifecycle.
- Settings configuration endpoints and live threshold sensitivity.
- FastAPI REST endpoints and report export generators (CSV, Excel, printable HTML).

---

## ⚖️ Engineering Screening Disclaimer

> **IMPORTANT NOTICE:** BurninWatch anomaly scores (0–100) and screening categories (*Normal*, *Suspicious*, *High Anomaly*) quantify statistical deviation across burn-in degradation trajectories. Flagged units represent abnormal drift rates, variance spikes, or multi-parameter deviations requiring engineering evaluation and bench re-testing. An anomaly score does **NOT** constitute a confirmed physical defect guarantee or failure probability.

