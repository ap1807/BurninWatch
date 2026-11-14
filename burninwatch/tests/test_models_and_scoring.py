"""Tests for ML algorithms and scoring calibration."""
import pytest
import numpy as np
import pandas as pd
from burninwatch.core.models import UnsupervisedAnomalyDetector
from burninwatch.core.scoring import ScreeningScorer, normalize_scores_to_index

def test_unsupervised_models_fit():
    np.random.seed(42)
    # 20 components, 6 degradation features
    # 18 normal, 2 extreme outliers
    X_normal = np.random.normal(0, 1.0, (18, 6))
    X_outliers = np.array([
        [10.0, -8.0, 12.0, -9.0, 14.0, -7.0],
        [-12.0, 14.0, -10.0, 16.0, -9.0, 11.0]
    ])
    X = np.vstack([X_normal, X_outliers])
    
    detector = UnsupervisedAnomalyDetector(contamination=0.10)
    results = detector.fit_predict(X)
    
    assert "isolation_forest" in results
    assert "lof" in results
    assert "one_class_svm" in results
    assert "pca_reconstruction" in results
    
    # Check that outlier components received higher raw anomaly score
    if_scores = np.array(results["isolation_forest"]["raw_scores"])
    assert if_scores[-1] > np.median(if_scores[:-2])
    
    pca_scores = np.array(results["pca_reconstruction"]["raw_scores"])
    assert pca_scores[-1] > np.median(pca_scores[:-2])

def test_scoring_and_screening_categories():
    comp_ids = [f"DUT_{i:02d}" for i in range(10)]
    # Mock model results
    model_results = {
        "isolation_forest": {
            "raw_scores": [0.1, 0.2, 0.15, 0.12, 0.18, 0.11, 0.14, 0.16, 0.85, 0.95],
            "flags": [0, 0, 0, 0, 0, 0, 0, 0, 1, 1]
        },
        "pca_reconstruction": {
            "raw_scores": [0.05, 0.06, 0.04, 0.07, 0.05, 0.06, 0.05, 0.08, 4.2, 5.1],
            "flags": [0, 0, 0, 0, 0, 0, 0, 0, 1, 1]
        }
    }
    
    scorer = ScreeningScorer(threshold_suspicious=60.0, threshold_high=80.0)
    scores_df = scorer.compute_composite_scores(model_results, comp_ids)
    
    assert len(scores_df) == 10
    assert "composite_anomaly_score" in scores_df.columns
    assert "screening_category" in scores_df.columns
    
    # Check top outlier has High Anomaly
    top_dut = scores_df.iloc[-1]
    assert top_dut["screening_category"] == "High Anomaly"
    assert top_dut["composite_anomaly_score"] >= 80.0
