"""
Data Loader & File Handling for BurninWatch.
Supports genuine CSV and Excel burn-in datasets with flexible column mapping,
schema auto-detection, and raw data preservation.
"""

import io
import os
import re
import hashlib
import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np

# Standard canonical fields recognized by BurninWatch
CANONICAL_FIELDS = {
    "component_id": [
        "component_id", "component", "dut_id", "serial_number", "serial_no", 
        "device_id", "part_id", "dut", "part_number", "part_no", "device", "unit", "id"
    ],
    "batch_id": [
        "batch_id", "batch", "lot_id", "lot", "wafer_id", "wafer", "run_id", "lot_number", "lot_no", "batch_no"
    ],
    "test_id": [
        "test_id", "test_chamber_id", "chamber_id", "condition", "stress_chamber", 
        "profile", "test_condition", "stage", "station_id", "test_run", "test_chamber"
    ],
    "timestamp": [
        "timestamp", "elapsed_hours", "burn_in_time", "hours", "time_hours", 
        "time", "cycle", "cycles", "step_time", "elapsed_time", "datetime", "date"
    ],
    "temperature": [
        "temperature_c", "temperature", "chamber_c", "chamber_temp", "temp", "temp_c", 
        "ambient_temp", "junction_temp", "t_ambient", "tc"
    ],
    "voltage": [
        "voltage_v", "voltage", "vref", "vdd", "v_out", "v_in", "v_drain", 
        "vth", "threshold_voltage", "vcc"
    ],
    "current": [
        "current_ma", "current", "idd", "i_supply", "quiescent_current", 
        "i_drain", "isupply_ma", "iq_ma", "current_a"
    ],
    "resistance": [
        "resistance_mohm", "resistance", "rds_on", "rds", "r_on", "r_series", 
        "res_mohm", "resistance_ohm", "rds_mohm"
    ],
    "leakage_current": [
        "leakage_current_ua", "leakage_current", "leakage", "i_leak", "ileak_ua", 
        "i_off", "idss", "leakage_ua", "ileak"
    ],
    "power_consumption": [
        "power_consumption_mw", "power_consumption", "power", "p_mw", "p_diss", 
        "power_w", "power_mw"
    ]
}


def _normalize_name(name: str) -> str:
    """Normalize column header for fuzzy matching."""
    return re.sub(r"[^a-zA-Z0-9]", "", str(name).strip().lower())


def detect_column_mappings(columns: List[str]) -> Dict[str, Optional[str]]:
    """
    Intelligently auto-map user columns to BurninWatch canonical fields.
    Returns mapping: {canonical_field: matched_user_col_or_None}
    """
    normalized_cols = {col: _normalize_name(col) for col in columns}
    mapping: Dict[str, Optional[str]] = {}
    assigned_user_cols = set()

    for canon_field, aliases in CANONICAL_FIELDS.items():
        matched = None
        # First pass: exact normalized match with canonical or alias
        for alias in aliases:
            norm_alias = _normalize_name(alias)
            for user_col, norm_user in normalized_cols.items():
                if user_col in assigned_user_cols:
                    continue
                if norm_user == norm_alias:
                    matched = user_col
                    break
            if matched:
                break
        
        # Second pass: substring match if not yet matched (skip short aliases like 'id' to avoid false positives)
        if not matched:
            for alias in aliases:
                norm_alias = _normalize_name(alias)
                if len(norm_alias) < 3 or norm_alias in ["id", "tc"]:
                    continue
                for user_col, norm_user in normalized_cols.items():
                    if user_col in assigned_user_cols:
                        continue
                    if norm_alias in norm_user:
                        matched = user_col
                        break
                if matched:
                    break

        if matched:
            mapping[canon_field] = matched
            assigned_user_cols.add(matched)
        else:
            mapping[canon_field] = None

    return mapping


def detect_additional_measurements(df: pd.DataFrame, mapped_user_cols: List[str]) -> List[str]:
    """
    Detects numerical columns in the uploaded dataset that were not mapped
    to the primary canonical fields, treating them as additional measurement channels.
    """
    extra_channels = []
    for col in df.columns:
        if col in mapped_user_cols:
            continue
        # Check if column is numeric or can be converted to numeric
        sample = pd.to_numeric(df[col].dropna(), errors="coerce")
        if sample.count() > 0 and (sample.count() / max(1, len(df[col].dropna()))) > 0.8:
            extra_channels.append(col)
    return extra_channels


class DatasetManager:
    """Manages raw and mapped dataset loading, hashing, and metadata preservation."""

    def __init__(self):
        self.raw_df: Optional[pd.DataFrame] = None
        self.mapped_df: Optional[pd.DataFrame] = None
        self.file_info: Dict[str, Any] = {}
        self.column_mapping: Dict[str, Optional[str]] = {}
        self.extra_measurement_channels: List[str] = []

    def load_bytes(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parses CSV or Excel file content, preserves raw data, and performs initial inspection.
        """
        sha256_hash = hashlib.sha256(content).hexdigest()
        ext = os.path.splitext(filename)[1].lower()

        if ext in [".xlsx", ".xls"]:
            raw = pd.read_excel(io.BytesIO(content))
        elif ext in [".csv", ".txt", ".tsv"]:
            sep = "\t" if ext == ".tsv" else ","
            try:
                raw = pd.read_csv(io.BytesIO(content), sep=sep, comment="#")
                # If parsed into a single column containing semicolons, re-parse with sep=";"
                if len(raw.columns) == 1 and ";" in str(raw.columns[0]):
                    raw = pd.read_csv(io.BytesIO(content), sep=";", comment="#")
            except Exception:
                # Fallback to python engine with auto-sniffing
                raw = pd.read_csv(io.BytesIO(content), sep=None, engine="python", comment="#")
        else:
            raise ValueError(f"Unsupported file format '{ext}'. BurninWatch supports .csv, .xlsx, .xls, and .tsv.")

        if raw.empty:
            raise ValueError("Uploaded file contains no data rows.")

        self.raw_df = raw.copy()
        
        # Auto-detect column mapping
        self.column_mapping = detect_column_mappings(list(raw.columns))
        mapped_values = [v for v in self.column_mapping.values() if v is not None]
        self.extra_measurement_channels = detect_additional_measurements(raw, mapped_values)

        self.file_info = {
            "filename": filename,
            "sha256": sha256_hash,
            "size_kb": round(len(content) / 1024.0, 2),
            "upload_timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_records": len(raw),
            "total_columns": len(raw.columns),
            "columns": list(raw.columns),
            "auto_mapping": self.column_mapping,
            "extra_channels": self.extra_measurement_channels,
            "has_component_id": self.column_mapping.get("component_id") is not None,
            "has_timestamp": self.column_mapping.get("timestamp") is not None
        }

        # Apply default mapping to build initial mapped_df
        self.apply_mapping(self.column_mapping)
        return self.file_info

    def apply_mapping(self, mapping: Dict[str, Optional[str]]) -> pd.DataFrame:
        """
        Applies verified user mapping to create a standardized mapped_df.
        Preserves original raw_df untouched.
        """
        if self.raw_df is None:
            raise ValueError("No dataset loaded yet.")

        self.column_mapping = mapping
        mapped_cols = {}
        
        for canon, user_col in mapping.items():
            if user_col and user_col in self.raw_df.columns:
                mapped_cols[user_col] = canon

        df = self.raw_df.rename(columns=mapped_cols).copy()
        
        # If component_id is not mapped, check if first string column can be used
        if "component_id" not in df.columns:
            candidates = [c for c in df.columns if df[c].dtype == object]
            if candidates:
                df = df.rename(columns={candidates[0]: "component_id"})
                self.column_mapping["component_id"] = candidates[0]
            else:
                # Synthesize a sequential DUT identifier only as fallback with warning
                df["component_id"] = [f"DUT_{(i // 8) + 1:03d}" for i in range(len(df))]

        # If batch_id missing, assign default
        if "batch_id" not in df.columns:
            df["batch_id"] = "DEFAULT_LOT"

        # If test_id missing, assign default
        if "test_id" not in df.columns:
            df["test_id"] = "HTOL_CHAMBER_1"

        # If timestamp missing, compute index order per component
        if "timestamp" not in df.columns:
            df["timestamp"] = df.groupby("component_id").cumcount() * 24.0

        self.mapped_df = df
        return self.mapped_df

    def get_template_csv(self) -> str:
        """Returns downloadable empty CSV template with standard engineering headers."""
        headers = [
            "component_id", "batch_id", "test_id", "timestamp",
            "temperature_c", "voltage_v", "current_ma",
            "resistance_mohm", "leakage_current_ua", "power_consumption_mw"
        ]
        doc = [
            "# BurninWatch Official Component Screening Dataset Template",
            "# Fields description:",
            "# - component_id (Required): Unique Device Under Test (DUT) ID / Serial Number",
            "# - batch_id (Optional): Manufacturing lot, wafer ID, or run number",
            "# - test_id (Optional): Test chamber ID or stress condition profile",
            "# - timestamp (Required): Elapsed burn-in time (hours) or sequential test timestamp",
            "# - temperature_c (Optional): Chamber/ambient stress temperature (Celsius)",
            "# - voltage_v (Optional): Operating, reference, or threshold voltage (Volts)",
            "# - current_ma (Optional): Quiescent / supply current (milliamperes)",
            "# - resistance_mohm (Optional): On-state resistance RDS(on) / contact resistance (milliohms)",
            "# - leakage_current_ua (Optional): Off-state / reverse leakage current (microamperes)",
            "# - power_consumption_mw (Optional): Electrical power dissipation (milliwatts)",
            ",".join(headers)
        ]
        return "\n".join(doc)
