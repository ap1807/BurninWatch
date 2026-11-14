"""
Comprehensive API Endpoint Tests for BurninWatch FastAPI Server.
Verifies full REST API functionality and data flow.
"""

import pytest
from fastapi.testclient import TestClient
from burninwatch.web.app import app

client = TestClient(app)

def test_home_page():
    res = client.get("/")
    assert res.status_code == 200
    assert "BurninWatch" in res.text
    assert "Liquid Glassmorphism" in res.text or "data-theme" in res.text

def test_template_download():
    res = client.get("/api/template/csv")
    assert res.status_code == 200
    assert "component_id" in res.text
    assert "resistance_mohm" in res.text

def test_load_sample_and_run_audit():
    # 1. Load sample benchmark
    res_sample = client.post("/api/load-sample")
    assert res_sample.status_code == 200
    sample_data = res_sample.json()
    assert sample_data["status"] == "success"
    assert "dataset_id" in sample_data
    
    # 2. Check dataset info
    res_info = client.get("/api/dataset-info")
    assert res_info.status_code == 200
    info_data = res_info.json()
    assert info_data["has_dataset"] is True
    assert info_data["file_info"]["total_records"] == 480

    # 3. Run quality audit
    res_audit = client.post("/api/run-audit")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["status"] == "success"
    assert audit_data["audit_summary"]["total_components"] == 60

    # 4. Get features
    res_feat = client.get("/api/features?page=1&page_size=20")
    assert res_feat.status_code == 200
    feat_data = res_feat.json()
    assert feat_data["total_components"] == 60
    assert len(feat_data["records"]) == 20

def test_run_models_and_dashboard():
    # Execute unsupervised anomaly models
    payload = {
        "algorithms": ["isolation_forest", "lof", "one_class_svm", "pca_reconstruction"],
        "params": {
            "contamination": 0.10,
            "if_n_estimators": 100,
            "lof_n_neighbors": 15,
            "ocsvm_nu": 0.10,
            "pca_components": 3
        }
    }
    res_models = client.post("/api/run-models", json=payload)
    assert res_models.status_code == 200
    model_data = res_models.json()
    assert model_data["status"] == "success"
    assert model_data["total_screened"] == 60
    assert model_data["normal_count"] > 0
    assert (model_data["suspicious_count"] + model_data["high_anomaly_count"]) > 0

    # Dashboard data
    res_dash = client.get("/api/dashboard")
    assert res_dash.status_code == 200
    dash_data = res_dash.json()
    assert dash_data["is_ready"] is True
    assert dash_data["kpis"]["total_screened"] == 60
    assert "score_distribution" in dash_data
    assert "batch_breakdown" in dash_data
    assert "scatter_data" in dash_data

def test_screening_results_and_component_deep_dive():
    # All results
    res_all = client.get("/api/screening-results")
    assert res_all.status_code == 200
    all_data = res_all.json()
    assert all_data["total_results"] == 60

    # Hidden risks only filter
    res_hidden = client.get("/api/screening-results?hidden_only=true")
    assert res_hidden.status_code == 200
    hidden_data = res_hidden.json()
    assert hidden_data["total_results"] >= 1
    # Verify that every returned component passed static limits but was flagged
    for r in hidden_data["results"]:
        assert r["exceeds_static_limits"] is False
        assert r["screening_category"] in ["High Anomaly", "Suspicious"]

    # Component Deep-Dive (DUT_007)
    res_comp = client.get("/api/component/DUT_007")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["component_id"] == "DUT_007"
    assert "curves" in comp_data
    assert "explanation" in comp_data
    assert len(comp_data["explanation"]["primary_explanations"]) > 0

def test_model_comparison_and_exports():
    # Model comparison
    res_comp = client.get("/api/model-comparison")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert len(comp_data["algorithms"]) == 4
    assert "agreement_distribution" in comp_data
    assert "pairwise_jaccard" in comp_data

    # CSV Export
    res_csv = client.get("/api/export/csv")
    assert res_csv.status_code == 200
    assert res_csv.headers["content-type"].startswith("text/csv")
    assert b"DUT_" in res_csv.content

    # Excel Export
    res_excel = client.get("/api/export/excel")
    assert res_excel.status_code == 200
    assert len(res_excel.content) > 2000

    # Printable HTML Report
    res_html = client.get("/api/export/report-html")
    assert res_html.status_code == 200
    assert "BurninWatch" in res_html.text
    assert "ENGINEERING SCREENING NOTICE" in res_html.text

def test_settings_update():
    # GET settings
    res_get = client.get("/api/settings")
    assert res_get.status_code == 200
    assert "settings" in res_get.json()

    # POST settings
    res_settings = client.post("/api/settings", json={"threshold_suspicious": 65.0, "threshold_high": 85.0})
    assert res_settings.status_code == 200
    data = res_settings.json()
    assert data["settings"]["threshold_suspicious"] == 65.0
    assert data["settings"]["threshold_high"] == 85.0

def test_past_runs():
    res_runs = client.get("/api/runs")
    assert res_runs.status_code == 200
    data = res_runs.json()
    assert "runs" in data
    assert len(data["runs"]) >= 1

    # Load past run
    run_id = data["runs"][0]["run_id"]
    res_load = client.post(f"/api/runs/{run_id}/load")
    assert res_load.status_code == 200
    assert res_load.json()["status"] == "success"

    # Verify session restored properly
    res_info = client.get("/api/dataset-info")
    assert res_info.status_code == 200
    assert res_info.json()["has_dataset"] is True
    assert res_info.json()["current_run_id"] == run_id

def test_step_jump_explainability():
    # DUT_043 was engineered with a step jump at 72h
    res_comp = client.get("/api/component/DUT_043")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["component_id"] == "DUT_043"
    
    # Check top_deviations has ratio_to_median for step jumps without undefined
    top_devs = comp_data["explanation"]["top_deviations"]
    for dev in top_devs:
        if dev["metric"] == "Max Step Jump":
            assert "ratio_to_median" in dev
            assert isinstance(dev["ratio_to_median"], (int, float))

def test_semicolon_csv_upload():
    # Test uploading a semicolon-delimited CSV
    semicolon_content = (
        "dut_id;lot_id;test_chamber;hours;rds_mohm;current_ma\n"
        "DUT_S1;LOT_S;CH_1;0.0;110.5;12.1\n"
        "DUT_S1;LOT_S;CH_1;24.0;110.8;12.1\n"
        "DUT_S1;LOT_S;CH_1;48.0;111.0;12.2\n"
        "DUT_S2;LOT_S;CH_1;0.0;112.0;12.0\n"
        "DUT_S2;LOT_S;CH_1;24.0;112.3;12.0\n"
        "DUT_S2;LOT_S;CH_1;48.0;112.5;12.1\n"
    ).encode("utf-8")

    files = {"file": ("test_semicolon.csv", semicolon_content, "text/csv")}
    res = client.post("/api/upload", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "rds_mohm" in data["raw_columns"]
    assert data["mapping"]["component_id"] == "dut_id"
    assert data["mapping"]["resistance"] == "rds_mohm"
