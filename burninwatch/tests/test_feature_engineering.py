"""Tests for feature engineering module."""
import pytest
import pandas as pd
import numpy as np
from burninwatch.core.feature_engineering import DegradationFeatureExtractor

def test_degradation_feature_extractor():
    # Construct 2 components: one steady, one steep drift
    t = [0.0, 24.0, 48.0, 72.0, 96.0]
    comp1_res = [100.0, 100.2, 100.4, 100.6, 100.8] # gentle drift (+0.8 over 96h)
    comp2_res = [100.0, 105.0, 110.0, 115.0, 120.0] # steep degradation (+20 over 96h)
    
    df1 = pd.DataFrame({
        "component_id": "DUT_STEADY", "batch_id": "B1", "test_id": "T1",
        "elapsed_time": t, "resistance": comp1_res, "current": [10.0]*5
    })
    df2 = pd.DataFrame({
        "component_id": "DUT_DRIFT", "batch_id": "B1", "test_id": "T1",
        "elapsed_time": t, "resistance": comp2_res, "current": [10.0]*5
    })
    df = pd.concat([df1, df2], ignore_index=True)
    
    extractor = DegradationFeatureExtractor(df, measurement_columns=["resistance", "current"])
    feat_df = extractor.extract_features()
    
    assert len(feat_df) == 2
    row_steady = feat_df[feat_df["component_id"] == "DUT_STEADY"].iloc[0]
    row_drift = feat_df[feat_df["component_id"] == "DUT_DRIFT"].iloc[0]
    
    assert row_drift["resistance_slope"] > row_steady["resistance_slope"]
    assert row_drift["resistance_cumulative_drift"] > row_steady["resistance_cumulative_drift"]
    assert row_drift["resistance_pct_change"] == pytest.approx(20.0, abs=0.1)

    X, cols, df_out = extractor.get_feature_matrix_for_ml()
    assert X.shape[0] == 2
    assert X.shape[1] > 5

def test_flat_signal_drift_ratio_stability():
    # Test that when a component starts and ends at the exact same value (net_disp == 0),
    # the drift ratio does not explode into billions due to division by 1e-9.
    t = [0.0, 24.0, 48.0, 72.0, 96.0]
    # Starts at 125.0 and ends at 125.0, with minor thermal fluctuations in between
    vals = [125.0, 125.2, 124.9, 125.1, 125.0]
    
    df = pd.DataFrame({
        "component_id": ["DUT_FLAT"] * 5,
        "batch_id": ["B1"] * 5,
        "test_id": ["T1"] * 5,
        "elapsed_time": t,
        "temperature": vals
    })
    
    extractor = DegradationFeatureExtractor(df, measurement_columns=["temperature"])
    feat_df = extractor.extract_features()
    
    row = feat_df.iloc[0]
    assert row["temperature_drift_ratio"] <= 50.0
    assert not np.isnan(row["temperature_drift_ratio"])
    assert not np.isinf(row["temperature_drift_ratio"])
