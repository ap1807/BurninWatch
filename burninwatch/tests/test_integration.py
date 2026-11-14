"""
End-to-End Integration Test for BurninWatch.
Simulates real industry workflow on HTOL burn-in dataset.
"""

import os
import pytest
import pandas as pd
from burninwatch.core.data_loader import DatasetManager
from burninwatch.core.preprocessor import DataQualityAuditor
from burninwatch.core.feature_engineering import DegradationFeatureExtractor
from burninwatch.core.models import UnsupervisedAnomalyDetector
from burninwatch.core.scoring import ScreeningScorer
from burninwatch.core.explainability import AnomalyExplainer
from burninwatch.core.storage import StorageManager
from burninwatch.reporting.exporter import ReportExporter


def test_full_burninwatch_workflow():
    sample_path = "data/samples/htol_burnin_measurements.csv"
    assert os.path.exists(sample_path), "Sample dataset missing."

    with open(sample_path, "rb") as f:
        content = f.read()

    # 1. Load Dataset
    dm = DatasetManager()
    info = dm.load_bytes(content, "htol_burnin_measurements.csv")
    assert info["total_records"] == 480
    assert dm.mapped_df is not None

    # 2. Quality Audit & Clean
    auditor = DataQualityAuditor(dm.mapped_df, dm.extra_measurement_channels)
    clean_df, audit_summary, warnings = auditor.run_audit_and_clean()
    assert audit_summary["total_components"] == 60
    assert "resistance" in audit_summary["available_measurements"]

    # 3. Feature Extraction
    extractor = DegradationFeatureExtractor(clean_df, audit_summary["available_measurements"])
    features_df = extractor.extract_features()
    assert len(features_df) == 60
    assert "resistance_slope" in features_df.columns
    assert "resistance_instability_mean" in features_df.columns

    # 4. Unsupervised Model Fitting
    X, feat_names, _ = extractor.get_feature_matrix_for_ml()
    detector = UnsupervisedAnomalyDetector(contamination=0.10)
    model_results = detector.fit_predict(X)
    assert len(model_results) == 4

    # 5. Composite Scoring & Screening Categories
    comp_ids = list(features_df["component_id"])
    scorer = ScreeningScorer(threshold_suspicious=60.0, threshold_high=80.0)
    scores_df = scorer.compute_composite_scores(model_results, comp_ids)
    
    # Merge batch and test metadata
    scores_df["batch_id"] = features_df["batch_id"].values
    scores_df["test_id"] = features_df["test_id"].values
    
    # Static limits check
    final_screening_df = scorer.audit_static_limits(clean_df, scores_df)
    
    assert len(final_screening_df) == 60
    assert "is_hidden_degradation_risk" in final_screening_df.columns

    # 6. Explainability
    explainer = AnomalyExplainer(clean_df, features_df, audit_summary["available_measurements"])
    explanations = {}
    for _, row in final_screening_df[final_screening_df["screening_category"] != "Normal"].iterrows():
        cid = row["component_id"]
        exp = explainer.explain_component(cid, row.to_dict())
        explanations[cid] = exp
        assert "primary_explanations" in exp
        assert len(exp["primary_explanations"]) > 0

    # Verify DUT_007 (steep monotonic drift) or DUT_028 (instability) is flagged
    flagged_ids = list(final_screening_df[final_screening_df["screening_category"] != "Normal"]["component_id"])
    assert len(flagged_ids) >= 3

    # 7. Persistence
    sm = StorageManager(base_dir="data/storage")
    sm.save_dataset("ds_test", "htol_burnin_measurements.csv", content, info, dm.column_mapping)
    run_dir = sm.save_run(
        run_id="run_integ_001",
        dataset_id="ds_test",
        clean_df=clean_df,
        features_df=features_df,
        screening_df=final_screening_df,
        model_results=model_results,
        model_params={"contamination": 0.10},
        audit_summary=audit_summary,
        explanations=explanations
    )
    assert os.path.exists(run_dir)

    # 8. Export Reports
    csv_bytes = ReportExporter.export_csv(final_screening_df)
    assert len(csv_bytes) > 500

    excel_bytes = ReportExporter.export_excel(final_screening_df, features_df, audit_summary)
    assert len(excel_bytes) > 2000

    run_bundle = {
        "run_id": "run_integ_001",
        "screening_df": final_screening_df,
        "metadata": {
            "audit_summary": audit_summary
        }
    }
    html_report = ReportExporter.generate_html_report(run_bundle, explanations)
    assert "BurninWatch" in html_report
    assert "ENGINEERING SCREENING NOTICE" in html_report
