"""Tests for preprocessor and auditor."""
import pytest
import pandas as pd
import numpy as np
from burninwatch.core.preprocessor import DataQualityAuditor

def test_data_quality_clean_and_audit():
    # Construct test dataframe with missing values and duplicates
    df = pd.DataFrame({
        "component_id": ["DUT_01", "DUT_01", "DUT_01", "DUT_01", "DUT_02", "DUT_02", "DUT_02", None],
        "batch_id": ["B1"] * 8,
        "test_id": ["T1"] * 8,
        "timestamp": [0.0, 24.0, 24.0, 48.0, 0.0, 24.0, 48.0, 0.0], # duplicate at 24.0 for DUT_01
        "resistance": [100.0, 101.0, 101.0, np.nan, 105.0, 106.0, 107.0, 100.0],
        "current": [10.0, 10.1, 10.1, 10.2, 11.0, 11.1, 11.2, 10.0]
    })
    
    auditor = DataQualityAuditor(df)
    clean_df, summary, warnings = auditor.run_audit_and_clean()
    
    # Check that None component_id was excluded
    assert clean_df["component_id"].isna().sum() == 0
    assert summary["excluded_rows"] >= 1
    # Check that duplicate at 24.0 was handled
    assert len(clean_df[clean_df["component_id"] == "DUT_01"]) == 3
    # Check missing resistance was imputed
    assert clean_df["resistance"].isna().sum() == 0
    assert summary["total_components"] == 2
