"""Tests for data_loader module."""
import pytest
import io
import pandas as pd
from burninwatch.core.data_loader import (
    DatasetManager, detect_column_mappings, detect_additional_measurements
)

def test_detect_column_mappings():
    cols = ["DUT_SN", "LOT_CODE", "BURN_HOURS", "CHAMBER_C", "RDS_ON_MOHM", "IQ_MA"]
    mapping = detect_column_mappings(cols)
    assert mapping["component_id"] == "DUT_SN"
    assert mapping["batch_id"] == "LOT_CODE"
    assert mapping["timestamp"] == "BURN_HOURS"
    assert mapping["temperature"] == "CHAMBER_C"
    assert mapping["resistance"] == "RDS_ON_MOHM"
    assert mapping["current"] == "IQ_MA"

def test_load_csv_and_apply_mapping():
    csv_data = (
        "dut_id,lot_id,hours,temp_c,rds_mohm\n"
        "DUT_01,LOT_A,0.0,125.0,110.2\n"
        "DUT_01,LOT_A,24.0,125.0,110.5\n"
        "DUT_02,LOT_A,0.0,125.0,112.0\n"
        "DUT_02,LOT_A,24.0,125.0,112.4\n"
    ).encode("utf-8")
    
    dm = DatasetManager()
    info = dm.load_bytes(csv_data, "test_burnin.csv")
    
    assert info["total_records"] == 4
    assert info["has_component_id"] is True
    assert dm.mapped_df is not None
    assert "component_id" in dm.mapped_df.columns
    assert "resistance" in dm.mapped_df.columns

def test_template_csv():
    dm = DatasetManager()
    template = dm.get_template_csv()
    assert "component_id" in template
    assert "resistance_mohm" in template
