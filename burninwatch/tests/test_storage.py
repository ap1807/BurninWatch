"""Tests for persistent storage manager."""
import pytest
import os
import shutil
import pandas as pd
from burninwatch.core.storage import StorageManager

def test_storage_manager_lifecycle(tmp_path):
    test_dir = str(tmp_path / "test_storage")
    sm = StorageManager(base_dir=test_dir)
    
    # Save dataset
    file_info = {"sha256": "fakehash123", "size_kb": 12.5, "total_records": 10}
    sm.save_dataset("ds_001", "burnin.csv", b"col1,col2\n1,2", file_info, {"col1": "component_id"})
    
    # Save run
    clean_df = pd.DataFrame({"component_id": ["DUT_01"], "elapsed_time": [0.0], "resistance": [100.0]})
    feats_df = pd.DataFrame({"component_id": ["DUT_01"], "resistance_slope": [0.01]})
    screen_df = pd.DataFrame({
        "component_id": ["DUT_01"],
        "batch_id": ["B1"],
        "test_id": ["T1"],
        "composite_anomaly_score": [15.2],
        "screening_category": ["Normal"],
        "screening_verdict": ["Normal Pass"],
        "exceeds_static_limits": [False],
        "is_hidden_degradation_risk": [False],
        "models_flagged_count": [0]
    })
    
    run_dir = sm.save_run(
        run_id="run_001",
        dataset_id="ds_001",
        clean_df=clean_df,
        features_df=feats_df,
        screening_df=screen_df,
        model_results={"isolation_forest": {"flags": [0]}},
        model_params={"contamination": 0.05},
        audit_summary={"total_components": 1}
    )
    
    assert os.path.exists(run_dir)
    
    runs = sm.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run_001"
    
    loaded_run = sm.get_run("run_001")
    assert loaded_run is not None
    assert len(loaded_run["screening_df"]) == 1
