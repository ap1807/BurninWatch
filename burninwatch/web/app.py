"""
FastAPI Application Server for BurninWatch.
Provides RESTful APIs for file upload, preprocessing, feature extraction,
unsupervised model execution, screening aggregation, explainability, and report export.
"""

import os
import io
import json
import uuid
import datetime
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import pandas as pd
import numpy as np

from burninwatch.core.data_loader import DatasetManager
from burninwatch.core.preprocessor import DataQualityAuditor
from burninwatch.core.feature_engineering import DegradationFeatureExtractor
from burninwatch.core.models import UnsupervisedAnomalyDetector
from burninwatch.core.scoring import ScreeningScorer
from burninwatch.core.explainability import AnomalyExplainer
from burninwatch.core.storage import StorageManager
from burninwatch.reporting.exporter import ReportExporter

app = FastAPI(
    title="BurninWatch – Component Screening Anomaly Detection",
    description="Industry-grade Unsupervised ML for Electronic Component Burn-in Screening",
    version="1.0.0"
)

# Mount static files and templates
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")
templates_dir = os.path.join(base_dir, "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Application Global State & Managers
dataset_mgr = DatasetManager()
storage_mgr = StorageManager(base_dir="data/storage")

# Active Session State
session_state: Dict[str, Any] = {
    "dataset_id": None,
    "clean_df": None,
    "audit_summary": None,
    "warnings": [],
    "features_df": None,
    "feature_matrix": None,
    "feature_names": [],
    "model_results": {},
    "model_params": {
        "contamination": 0.08,
        "if_n_estimators": 150,
        "lof_n_neighbors": 20,
        "ocsvm_kernel": "rbf",
        "ocsvm_nu": 0.08,
        "pca_components": 3
    },
    "screening_df": None,
    "explanations": {},
    "settings": {
        "threshold_suspicious": 60.0,
        "threshold_high": 80.0,
        "weights": {
            "isolation_forest": 0.30,
            "lof": 0.25,
            "one_class_svm": 0.20,
            "pca_reconstruction": 0.25
        },
        "static_specs": {}
    },
    "current_run_id": None
}


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Renders the main single-page application."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/template/csv")
async def download_template():
    """Serves downloadable empty CSV template with standard engineering headers."""
    csv_text = dataset_mgr.get_template_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="burninwatch_template.csv"'}
    )


@app.post("/api/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Handles CSV/Excel upload, detects schema, and computes initial metadata."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        dataset_id = f"ds_{uuid.uuid4().hex[:10]}"
        info = dataset_mgr.load_bytes(content, file.filename)
        
        # Persist raw dataset
        storage_mgr.save_dataset(
            dataset_id=dataset_id,
            filename=file.filename,
            content=content,
            file_info=info,
            mapping=dataset_mgr.column_mapping
        )

        session_state["dataset_id"] = dataset_id
        session_state["clean_df"] = None
        session_state["features_df"] = None
        session_state["screening_df"] = None
        session_state["explanations"] = {}
        session_state["current_run_id"] = None

        return {
            "status": "success",
            "dataset_id": dataset_id,
            "file_info": info,
            "mapping": dataset_mgr.column_mapping,
            "raw_columns": list(dataset_mgr.raw_df.columns),
            "preview": dataset_mgr.raw_df.head(10).replace({np.nan: None}).to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/load-sample")
async def load_sample_dataset():
    """Loads the pre-generated industry HTOL benchmark dataset for immediate exploration."""
    sample_path = "data/samples/htol_burnin_measurements.csv"
    if not os.path.exists(sample_path):
        from burninwatch.core.sample_generator import generate_sample_burnin_dataset
        generate_sample_burnin_dataset(sample_path)

    with open(sample_path, "rb") as f:
        content = f.read()

    dataset_id = f"ds_sample_{uuid.uuid4().hex[:6]}"
    info = dataset_mgr.load_bytes(content, "htol_burnin_measurements.csv")
    storage_mgr.save_dataset(
        dataset_id=dataset_id,
        filename="htol_burnin_measurements.csv",
        content=content,
        file_info=info,
        mapping=dataset_mgr.column_mapping
    )

    session_state["dataset_id"] = dataset_id
    session_state["clean_df"] = None
    session_state["features_df"] = None
    session_state["screening_df"] = None
    session_state["explanations"] = {}
    session_state["current_run_id"] = None

    return {
        "status": "success",
        "dataset_id": dataset_id,
        "file_info": info,
        "mapping": dataset_mgr.column_mapping,
        "raw_columns": list(dataset_mgr.raw_df.columns),
        "preview": dataset_mgr.raw_df.head(10).replace({np.nan: None}).to_dict(orient="records")
    }


@app.post("/api/apply-mapping")
async def apply_column_mapping(request: Request):
    """Applies updated column mapping from user."""
    payload = await request.json()
    mapping = payload.get("mapping", {})
    if not mapping:
        raise HTTPException(status_code=400, detail="Empty mapping provided.")

    try:
        dataset_mgr.apply_mapping(mapping)
        # Invalidate downstream calculations
        session_state["clean_df"] = None
        session_state["features_df"] = None
        session_state["screening_df"] = None
        return {"status": "success", "mapped_columns": list(dataset_mgr.mapped_df.columns)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/dataset-info")
async def get_dataset_info():
    """Returns current active dataset metadata."""
    if dataset_mgr.raw_df is None:
        return {"has_dataset": False}

    return {
        "has_dataset": True,
        "dataset_id": session_state["dataset_id"],
        "file_info": dataset_mgr.file_info,
        "mapping": dataset_mgr.column_mapping,
        "extra_channels": dataset_mgr.extra_measurement_channels,
        "is_audited": session_state["clean_df"] is not None,
        "is_screened": session_state["screening_df"] is not None,
        "current_run_id": session_state["current_run_id"]
    }


@app.post("/api/run-audit")
async def run_data_audit():
    """Executes data validation, missing value imputation, duplicate removal, and quality audit."""
    if dataset_mgr.mapped_df is None:
        raise HTTPException(status_code=400, detail="No dataset loaded. Upload a dataset first.")

    try:
        auditor = DataQualityAuditor(dataset_mgr.mapped_df, dataset_mgr.extra_measurement_channels)
        clean_df, audit_summary, warnings = auditor.run_audit_and_clean()

        session_state["clean_df"] = clean_df
        session_state["audit_summary"] = audit_summary
        session_state["warnings"] = warnings

        # Auto-extract features
        extractor = DegradationFeatureExtractor(clean_df, audit_summary["available_measurements"])
        features_df = extractor.extract_features()
        X, cols, _ = extractor.get_feature_matrix_for_ml()

        session_state["features_df"] = features_df
        session_state["feature_matrix"] = X
        session_state["feature_names"] = cols

        return {
            "status": "success",
            "audit_summary": audit_summary,
            "warnings": warnings,
            "feature_count": len(cols),
            "sample_clean_rows": clean_df.head(15).replace({np.nan: None}).to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/features")
async def get_features(page: int = 1, page_size: int = 50):
    """Returns extracted degradation features for components."""
    if session_state["features_df"] is None:
        raise HTTPException(status_code=400, detail="Features not extracted yet. Run data audit first.")

    df = session_state["features_df"]
    start = (page - 1) * page_size
    end = start + page_size

    paged = df.iloc[start:end].replace({np.nan: None}).to_dict(orient="records")
    return {
        "total_components": len(df),
        "feature_names": session_state["feature_names"],
        "records": paged,
        "page": page,
        "page_size": page_size
    }


@app.post("/api/run-models")
async def run_anomaly_models(request: Request):
    """Fits selected unsupervised algorithms and calculates raw anomaly scores."""
    if session_state["feature_matrix"] is None:
        raise HTTPException(status_code=400, detail="Feature matrix unavailable. Run data audit first.")

    payload = await request.json()
    algorithms = payload.get("algorithms", ["isolation_forest", "lof", "one_class_svm", "pca_reconstruction"])
    params = payload.get("params", {})
    session_state["model_params"].update(params)

    contamination = float(params.get("contamination", session_state["model_params"]["contamination"]))
    detector = UnsupervisedAnomalyDetector(contamination=contamination)

    try:
        model_results = detector.fit_predict(
            X=session_state["feature_matrix"],
            algorithms=algorithms,
            model_params=session_state["model_params"]
        )
        session_state["model_results"] = model_results

        # Compute screening scores
        features_df = session_state["features_df"]
        comp_ids = list(features_df["component_id"])
        settings = session_state["settings"]

        scorer = ScreeningScorer(
            threshold_suspicious=settings["threshold_suspicious"],
            threshold_high=settings["threshold_high"],
            weights=settings.get("weights")
        )
        scores_df = scorer.compute_composite_scores(model_results, comp_ids)
        scores_df["batch_id"] = features_df["batch_id"].values
        scores_df["test_id"] = features_df["test_id"].values

        # Static limits audit
        final_screening_df = scorer.audit_static_limits(
            clean_df=session_state["clean_df"],
            screening_df=scores_df,
            static_specs=settings.get("static_specs")
        )
        session_state["screening_df"] = final_screening_df

        # Generate explainability for flagged components
        explainer = AnomalyExplainer(
            clean_df=session_state["clean_df"],
            features_df=features_df,
            measurement_columns=session_state["audit_summary"]["available_measurements"]
        )
        explanations = {}
        for _, row in final_screening_df.iterrows():
            cid = str(row["component_id"])
            if row["screening_category"] != "Normal" or row.get("exceeds_static_limits", False):
                explanations[cid] = explainer.explain_component(cid, row.to_dict())
        session_state["explanations"] = explanations

        # Persist Run
        run_id = f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session_state["current_run_id"] = run_id
        storage_mgr.save_run(
            run_id=run_id,
            dataset_id=session_state["dataset_id"],
            clean_df=session_state["clean_df"],
            features_df=features_df,
            screening_df=final_screening_df,
            model_results=model_results,
            model_params=session_state["model_params"],
            audit_summary=session_state["audit_summary"],
            explanations=explanations
        )

        return {
            "status": "success",
            "run_id": run_id,
            "model_results": model_results,
            "total_screened": len(final_screening_df),
            "normal_count": int((final_screening_df["screening_category"] == "Normal").sum()),
            "suspicious_count": int((final_screening_df["screening_category"] == "Suspicious").sum()),
            "high_anomaly_count": int((final_screening_df["screening_category"] == "High Anomaly").sum()),
            "hidden_risk_count": int(final_screening_df["is_hidden_degradation_risk"].sum()),
            "static_fail_count": int(final_screening_df["exceeds_static_limits"].sum())
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/dashboard")
async def get_dashboard_data():
    """Returns aggregated KPIs and visualization datasets for the main dashboard."""
    if session_state["screening_df"] is None:
        return {"is_ready": False}

    sdf = session_state["screening_df"]
    fdf = session_state["features_df"]
    total = len(sdf)
    normal = int((sdf["screening_category"] == "Normal").sum())
    suspicious = int((sdf["screening_category"] == "Suspicious").sum())
    high = int((sdf["screening_category"] == "High Anomaly").sum())
    flagged = suspicious + high
    pct_flagged = round((flagged / max(1, total)) * 100.0, 1)
    hidden_risks = int(sdf["is_hidden_degradation_risk"].sum())

    # Anomaly Score Bins (0-10, 10-20, ... 90-100)
    bins = np.linspace(0, 100, 11)
    hist, _ = np.histogram(sdf["composite_anomaly_score"], bins=bins)
    bin_labels = [f"{int(bins[i])}-{int(bins[i+1])}" for i in range(len(hist))]

    # Batch Breakdown
    batch_summary = []
    for batch_id, grp in sdf.groupby("batch_id"):
        batch_summary.append({
            "batch_id": batch_id,
            "total": len(grp),
            "normal": int((grp["screening_category"] == "Normal").sum()),
            "suspicious": int((grp["screening_category"] == "Suspicious").sum()),
            "high": int((grp["screening_category"] == "High Anomaly").sum()),
            "hidden_risks": int(grp["is_hidden_degradation_risk"].sum())
        })

    # Degradation Scatter Data (Resistance Slope vs Instability, or primary measurement)
    meas = session_state["audit_summary"]["available_measurements"]
    primary_meas = "resistance" if "resistance" in meas else meas[0]
    
    slope_col = f"{primary_meas}_slope"
    instab_col = f"{primary_meas}_instability_mean"

    scatter_pts = []
    for _, row in sdf.iterrows():
        cid = row["component_id"]
        feat_match = fdf[fdf["component_id"] == cid]
        s_val = float(feat_match[slope_col].iloc[0]) if (not feat_match.empty and slope_col in feat_match) else 0.0
        i_val = float(feat_match[instab_col].iloc[0]) if (not feat_match.empty and instab_col in feat_match) else 0.0
        scatter_pts.append({
            "component_id": cid,
            "batch_id": row["batch_id"],
            "score": float(row["composite_anomaly_score"]),
            "category": row["screening_category"],
            "slope": round(s_val, 4),
            "instability": round(i_val, 4),
            "is_hidden": bool(row["is_hidden_degradation_risk"]),
            "exceeds_limits": bool(row["exceeds_static_limits"])
        })

    return {
        "is_ready": True,
        "run_id": session_state["current_run_id"],
        "kpis": {
            "total_screened": total,
            "normal_count": normal,
            "suspicious_count": suspicious,
            "high_anomaly_count": high,
            "flagged_count": flagged,
            "pct_flagged": pct_flagged,
            "hidden_degradation_risks": hidden_risks,
            "static_limit_failures": int(sdf["exceeds_static_limits"].sum())
        },
        "score_distribution": {
            "bins": bin_labels,
            "counts": [int(x) for x in hist]
        },
        "category_counts": {
            "Normal": normal,
            "Suspicious": suspicious,
            "High Anomaly": high
        },
        "batch_breakdown": batch_summary,
        "scatter_data": {
            "parameter": primary_meas,
            "points": scatter_pts
        },
        "top_flagged": sdf[sdf["screening_category"].isin(["High Anomaly", "Suspicious"])].sort_values(
            "composite_anomaly_score", ascending=False
        ).head(10).replace({np.nan: None}).to_dict(orient="records")
    }


@app.get("/api/screening-results")
async def get_screening_results(
    category: Optional[str] = Query(None),
    batch: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    hidden_only: bool = Query(False),
    min_score: float = Query(0.0)
):
    """Returns filtered screening results table."""
    if session_state["screening_df"] is None:
        raise HTTPException(status_code=400, detail="No screening results available.")

    df = session_state["screening_df"].copy()

    if category and category != "All":
        df = df[df["screening_category"] == category]

    if batch and batch != "All":
        df = df[df["batch_id"] == batch]

    if hidden_only:
        df = df[df["is_hidden_degradation_risk"] == True]

    if min_score > 0.0:
        df = df[df["composite_anomaly_score"] >= min_score]

    if search:
        s = search.strip().lower()
        df = df[df["component_id"].astype(str).str.lower().str.contains(s)]

    df = df.sort_values("composite_anomaly_score", ascending=False)
    return {
        "total_results": len(df),
        "results": df.replace({np.nan: None}).to_dict(orient="records")
    }


@app.get("/api/component/{comp_id}")
async def get_component_analysis(comp_id: str):
    """
    Returns individual component deep dive:
    - Time-series measurement history
    - Cohort min/max/mean envelopes
    - Engineered degradation features
    - Explainability breakdown and detected abnormal intervals
    - Static limit vs anomaly comparison
    """
    if session_state["clean_df"] is None or session_state["screening_df"] is None:
        raise HTTPException(status_code=400, detail="Screening data not ready.")

    cdf = session_state["clean_df"]
    sdf = session_state["screening_df"]
    fdf = session_state["features_df"]

    comp_records = cdf[cdf["component_id"] == comp_id].sort_values("elapsed_time")
    if comp_records.empty:
        raise HTTPException(status_code=404, detail=f"Component '{comp_id}' not found.")

    screen_row = sdf[sdf["component_id"] == comp_id]
    screen_dict = screen_row.iloc[0].to_dict() if not screen_row.empty else {}
    feat_row = fdf[fdf["component_id"] == comp_id]
    feat_dict = feat_row.iloc[0].to_dict() if not feat_row.empty else {}

    # Cohort analysis (components in same batch/condition)
    batch = comp_records["batch_id"].iloc[0]
    test_id = comp_records["test_id"].iloc[0]
    cohort_df = cdf[(cdf["batch_id"] == batch) & (cdf["test_id"] == test_id)]
    if len(cohort_df["component_id"].unique()) < 3:
        cohort_df = cdf

    measurements = session_state["audit_summary"]["available_measurements"]
    timepoints = list(comp_records["elapsed_time"].unique())

    # Build curves for each measurement channel
    channel_curves = {}
    for col in measurements:
        comp_series = comp_records[["elapsed_time", col]].to_dict(orient="records")
        
        # Calculate cohort envelope across timepoints
        cohort_envelope = []
        for t in timepoints:
            t_data = cohort_df[cohort_df["elapsed_time"] == t][col].dropna()
            if not t_data.empty:
                cohort_envelope.append({
                    "time": float(t),
                    "mean": round(float(t_data.mean()), 4),
                    "min": round(float(t_data.min()), 4),
                    "max": round(float(t_data.max()), 4),
                    "std": round(float(t_data.std(ddof=1)), 4) if len(t_data) > 1 else 0.0
                })

        channel_curves[col] = {
            "component_history": comp_series,
            "cohort_envelope": cohort_envelope
        }

    # Retrieve explanation
    exp = session_state["explanations"].get(comp_id)
    if not exp:
        explainer = AnomalyExplainer(cdf, fdf, measurements)
        exp = explainer.explain_component(comp_id, screen_dict)

    return {
        "component_id": comp_id,
        "batch_id": batch,
        "test_id": test_id,
        "screening": screen_dict,
        "features": feat_dict,
        "curves": channel_curves,
        "explanation": exp,
        "available_channels": measurements
    }


@app.get("/api/model-comparison")
async def get_model_comparison():
    """Returns algorithm agreement, overlap counts, and correlation statistics."""
    if session_state["screening_df"] is None or not session_state["model_results"]:
        raise HTTPException(status_code=400, detail="Models have not been executed yet.")

    sdf = session_state["screening_df"]
    algos = list(session_state["model_results"].keys())
    
    # 1. Summary per model
    algo_stats = []
    for algo in algos:
        flag_col = f"{algo}_flag"
        norm_col = f"{algo}_normalized_score"
        flagged_cnt = int(sdf[flag_col].sum()) if flag_col in sdf else 0
        algo_stats.append({
            "key": algo,
            "name": session_state["model_results"][algo]["name"],
            "flagged_count": flagged_cnt,
            "flagged_pct": round((flagged_cnt / max(1, len(sdf))) * 100.0, 1),
            "mean_score": round(float(sdf[norm_col].mean()), 2) if norm_col in sdf else 0.0,
            "max_score": round(float(sdf[norm_col].max()), 2) if norm_col in sdf else 0.0,
            "description": session_state["model_results"][algo]["description"]
        })

    # 2. Agreement Venn / Overlap: components flagged by N models
    agreement_counts = {str(i): int((sdf["models_flagged_count"] == i).sum()) for i in range(len(algos) + 1)}

    # 3. Pairwise Jaccard Agreement Matrix
    matrix = {}
    for a1 in algos:
        matrix[a1] = {}
        flags1 = sdf[f"{a1}_flag"].to_numpy()
        for a2 in algos:
            flags2 = sdf[f"{a2}_flag"].to_numpy()
            intersection = np.sum((flags1 == 1) & (flags2 == 1))
            union = np.sum((flags1 == 1) | (flags2 == 1))
            jaccard = round(float(intersection / max(1, union)), 2)
            matrix[a1][a2] = jaccard

    return {
        "algorithms": algo_stats,
        "agreement_distribution": agreement_counts,
        "pairwise_jaccard": matrix,
        "total_screened": len(sdf),
        "post_training_evaluation": {
            "has_ground_truth_labels": False,
            "message": (
                "Unsupervised ML screening operates strictly without ground-truth labels during training. "
                "If engineering failure labels become available post-testing, import verification tags in Settings "
                "to calculate formal Precision, Recall, and ROC metrics."
            )
        }
    }


@app.get("/api/runs")
async def list_past_runs():
    """Lists saved screening runs from persistent storage."""
    runs = storage_mgr.list_runs()
    return {"runs": runs}


@app.post("/api/runs/{run_id}/load")
async def load_past_run(run_id: str):
    """Restores a previous screening session from persistent storage."""
    run_dict = storage_mgr.get_run(run_id)
    if not run_dict:
        raise HTTPException(status_code=404, detail="Run not found.")

    meta = run_dict.get("metadata", {})
    session_state["current_run_id"] = run_id
    session_state["dataset_id"] = run_dict["dataset_id"]
    session_state["clean_df"] = run_dict.get("clean_df")
    session_state["features_df"] = run_dict.get("features_df")
    session_state["screening_df"] = run_dict.get("screening_df")
    session_state["model_results"] = meta.get("model_results", {})
    session_state["model_params"] = meta.get("model_params", session_state["model_params"])
    session_state["audit_summary"] = meta.get("audit_summary", {})
    session_state["explanations"] = meta.get("explanations", {})

    # Restore dataset manager
    ds_record = storage_mgr.get_dataset(run_dict["dataset_id"])
    if ds_record and ds_record.get("content"):
        dataset_mgr.load_bytes(ds_record["content"], ds_record["filename"])
        if ds_record.get("mapping"):
            dataset_mgr.apply_mapping(ds_record["mapping"])

    # Reconstruct feature matrix and feature names
    fdf = session_state["features_df"]
    if fdf is not None and session_state["clean_df"] is not None:
        meas = session_state["audit_summary"].get("available_measurements", [])
        if not meas:
            meas = [c for c in dataset_mgr.extra_measurement_channels if c in fdf.columns]
        extractor = DegradationFeatureExtractor(session_state["clean_df"], meas)
        extractor.features_df = fdf
        X, cols, _ = extractor.get_feature_matrix_for_ml()
        session_state["feature_matrix"] = X
        session_state["feature_names"] = cols

    return {"status": "success", "run_id": run_id}


@app.get("/api/settings")
async def get_settings():
    """Returns current screening thresholds, weights, and static limits."""
    return {"status": "success", "settings": session_state["settings"]}


@app.post("/api/settings")
async def update_settings(request: Request):
    """Updates screening thresholds, weights, or static engineering limits."""
    payload = await request.json()
    if "threshold_suspicious" in payload:
        session_state["settings"]["threshold_suspicious"] = float(payload["threshold_suspicious"])
    if "threshold_high" in payload:
        session_state["settings"]["threshold_high"] = float(payload["threshold_high"])
    if "weights" in payload:
        session_state["settings"]["weights"] = payload["weights"]
    if "static_specs" in payload:
        session_state["settings"]["static_specs"] = payload["static_specs"]

    # Recompute scores if screening results exist
    if session_state["model_results"] and session_state["features_df"] is not None:
        features_df = session_state["features_df"]
        scorer = ScreeningScorer(
            threshold_suspicious=session_state["settings"]["threshold_suspicious"],
            threshold_high=session_state["settings"]["threshold_high"],
            weights=session_state["settings"].get("weights")
        )
        scores_df = scorer.compute_composite_scores(session_state["model_results"], list(features_df["component_id"]))
        scores_df["batch_id"] = features_df["batch_id"].values
        scores_df["test_id"] = features_df["test_id"].values

        final_screening_df = scorer.audit_static_limits(
            clean_df=session_state["clean_df"],
            screening_df=scores_df,
            static_specs=session_state["settings"].get("static_specs")
        )
        session_state["screening_df"] = final_screening_df

        # Regenerate explanations for flagged components
        if session_state["clean_df"] is not None and session_state.get("audit_summary"):
            meas = session_state["audit_summary"].get("available_measurements", [])
            explainer = AnomalyExplainer(
                clean_df=session_state["clean_df"],
                features_df=features_df,
                measurement_columns=meas
            )
            explanations = {}
            for _, row in final_screening_df.iterrows():
                cid = str(row["component_id"])
                if row["screening_category"] != "Normal" or row.get("exceeds_static_limits", False):
                    explanations[cid] = explainer.explain_component(cid, row.to_dict())
            session_state["explanations"] = explanations

    return {"status": "success", "settings": session_state["settings"]}


@app.get("/api/export/csv")
async def export_screening_csv():
    """Exports screening results as CSV."""
    if session_state["screening_df"] is None:
        raise HTTPException(status_code=400, detail="No screening results to export.")

    csv_bytes = ReportExporter.export_csv(session_state["screening_df"])
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="burninwatch_screening_results.csv"'}
    )


@app.get("/api/export/excel")
async def export_screening_excel():
    """Exports comprehensive multi-tab Excel report."""
    if session_state["screening_df"] is None:
        raise HTTPException(status_code=400, detail="No screening results to export.")

    excel_bytes = ReportExporter.export_excel(
        screening_df=session_state["screening_df"],
        features_df=session_state["features_df"],
        audit_summary=session_state["audit_summary"]
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="burninwatch_screening_audit.xlsx"'}
    )


@app.get("/api/export/report-html")
async def export_screening_html_report():
    """Serves printable executive HTML audit report."""
    if session_state["screening_df"] is None:
        raise HTTPException(status_code=400, detail="No screening results to export.")

    run_bundle = {
        "run_id": session_state["current_run_id"] or "ACTIVE_RUN",
        "screening_df": session_state["screening_df"],
        "metadata": {
            "audit_summary": session_state["audit_summary"]
        }
    }
    html = ReportExporter.generate_html_report(run_bundle, session_state["explanations"])
    return HTMLResponse(content=html)
