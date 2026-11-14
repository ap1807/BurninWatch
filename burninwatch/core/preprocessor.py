"""
Data Validation, Preprocessing, and Quality Auditing for BurninWatch.
Handles missing values, duplicate detection, timestamp sorting, irregular intervals,
and data quality reporting.
"""

from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np

class DataQualityAuditor:
    """Performs comprehensive validation, cleaning, and quality audit on mapped burn-in data."""

    def __init__(self, mapped_df: pd.DataFrame, extra_channels: Optional[List[str]] = None):
        self.raw_mapped = mapped_df.copy()
        self.extra_channels = extra_channels or []
        self.clean_df: Optional[pd.DataFrame] = None
        self.audit_summary: Dict[str, Any] = {}
        self.warnings: List[str] = []
        self.measurement_columns: List[str] = []

    def run_audit_and_clean(self) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:
        """
        Executes complete quality audit and cleansing pipeline.
        Returns cleaned DataFrame, audit summary dictionary, and warning messages.
        """
        df = self.raw_mapped.copy()
        total_initial_rows = len(df)
        self.warnings = []

        # 1. Identify active measurement columns
        potential_measurements = [
            "temperature", "voltage", "current", "resistance", 
            "leakage_current", "power_consumption"
        ] + self.extra_channels
        
        self.measurement_columns = [
            c for c in potential_measurements 
            if c in df.columns and c not in ["component_id", "batch_id", "test_id", "timestamp"]
        ]

        if not self.measurement_columns:
            raise ValueError(
                "No valid measurement parameters found in the dataset. "
                "Map at least one electrical or physical measurement (e.g. resistance, current, voltage)."
            )

        # 2. Check for missing component_id
        if "component_id" not in df.columns or df["component_id"].isna().all():
            raise ValueError("Dataset is missing a valid 'component_id' column for tracking individual components.")

        # Exclude rows where component_id is NaN or empty
        invalid_id_mask = df["component_id"].isna() | (df["component_id"].astype(str).str.strip() == "")
        num_invalid_ids = int(invalid_id_mask.sum())
        if num_invalid_ids > 0:
            self.warnings.append(f"Excluded {num_invalid_ids} rows with missing or blank Component ID.")
            df = df[~invalid_id_mask].copy()

        # 3. Timestamp parsing and normalization
        df["raw_timestamp"] = df["timestamp"]
        # Try numeric conversion first
        numeric_time = pd.to_numeric(df["timestamp"], errors="coerce")
        if numeric_time.notna().sum() / max(1, len(df)) > 0.8:
            df["elapsed_time"] = numeric_time
        else:
            # Try datetime parsing
            try:
                parsed_dates = pd.to_datetime(df["timestamp"], errors="coerce")
                if parsed_dates.notna().sum() / max(1, len(df)) > 0.5:
                    # Convert to elapsed hours relative to the earliest timestamp per component
                    df["elapsed_time"] = parsed_dates.groupby(df["component_id"]).transform(
                        lambda s: (s - s.min()).dt.total_seconds() / 3600.0 if s.notna().any() else 0.0
                    )
                else:
                    df["elapsed_time"] = df.groupby("component_id").cumcount() * 24.0
                    self.warnings.append("Could not parse timestamps as dates or numbers; assigned sequential burn-in step index.")
            except Exception:
                # Fallback to sequential index
                df["elapsed_time"] = df.groupby("component_id").cumcount() * 24.0
                self.warnings.append("Could not parse timestamps as dates or numbers; assigned sequential burn-in step index.")

        # Fill any remaining NaN elapsed times with sequential interpolation
        df["elapsed_time"] = df.groupby("component_id")["elapsed_time"].transform(
            lambda s: s.ffill().bfill().fillna(0.0)
        )

        # 4. Numerical conversion and invalid measurement handling
        nan_counts = {}
        for col in self.measurement_columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            nan_cnt = int(df[col].isna().sum())
            if nan_cnt > 0:
                nan_counts[col] = nan_cnt
                # Impute missing measurement per component using forward-fill, then backward-fill, then cohort median
                df[col] = df.groupby("component_id")[col].transform(lambda s: s.ffill().bfill())
                if df[col].isna().any():
                    cohort_median = df[col].median()
                    df[col] = df[col].fillna(cohort_median)

        # 5. Duplicate detection
        # Exact duplicate rows
        exact_dups = int(df.duplicated(subset=["component_id", "elapsed_time"] + self.measurement_columns).sum())
        if exact_dups > 0:
            df = df.drop_duplicates(subset=["component_id", "elapsed_time"] + self.measurement_columns)
            self.warnings.append(f"Removed {exact_dups} exact duplicate measurement records.")

        # Duplicate timestamp per component (keep last or mean)
        time_dups = int(df.duplicated(subset=["component_id", "elapsed_time"]).sum())
        if time_dups > 0:
            agg_dict = {col: "mean" for col in self.measurement_columns}
            for col in df.columns:
                if col not in ["component_id", "elapsed_time", "batch_id", "test_id"] + self.measurement_columns:
                    agg_dict[col] = "first"
            df = df.groupby(["component_id", "elapsed_time", "batch_id", "test_id"], as_index=False).agg(agg_dict)
            self.warnings.append(f"Averaged {time_dups} duplicate observations sharing the same timestamp for a component.")

        # 6. Chronological sorting per component
        df = df.sort_values(by=["component_id", "elapsed_time"]).reset_index(drop=True)

        # 7. Sampling interval analysis (dt)
        df["dt"] = df.groupby("component_id")["elapsed_time"].diff().fillna(0.0)
        dt_positive = df[df["dt"] > 0]["dt"]
        mean_dt = float(dt_positive.mean()) if not dt_positive.empty else 0.0
        min_dt = float(dt_positive.min()) if not dt_positive.empty else 0.0
        max_dt = float(dt_positive.max()) if not dt_positive.empty else 0.0
        is_regular = False
        if not dt_positive.empty and (max_dt - min_dt) < 0.1 * (mean_dt + 1e-6):
            is_regular = True

        # 8. Component count & observations per component
        obs_per_comp = df.groupby("component_id").size()
        min_obs = int(obs_per_comp.min()) if not obs_per_comp.empty else 0
        max_obs = int(obs_per_comp.max()) if not obs_per_comp.empty else 0
        avg_obs = float(obs_per_comp.mean()) if not obs_per_comp.empty else 0.0
        total_components = int(df["component_id"].nunique())

        # Reliability checks & warnings
        if total_components < 5:
            self.warnings.append(
                f"Dataset contains only {total_components} component(s). Unsupervised screening models "
                "require at least 5-10 components to establish statistical cohort norms reliably."
            )
        if min_obs < 3:
            under_sampled = list(obs_per_comp[obs_per_comp < 3].index[:5])
            self.warnings.append(
                f"Some components have fewer than 3 time points (e.g. {under_sampled}). "
                "Degradation trend features (slope, drift, curvature) require at least 3 points."
            )

        excluded_rows = total_initial_rows - len(df)

        self.clean_df = df
        self.audit_summary = {
            "initial_rows": total_initial_rows,
            "clean_rows": len(df),
            "excluded_rows": excluded_rows,
            "total_components": total_components,
            "total_batches": int(df["batch_id"].nunique()),
            "total_test_conditions": int(df["test_id"].nunique()),
            "available_measurements": self.measurement_columns,
            "measurement_count": len(self.measurement_columns),
            "missing_values_imputed": nan_counts,
            "duplicate_records_removed": exact_dups + time_dups,
            "obs_per_component": {
                "min": min_obs,
                "max": max_obs,
                "mean": round(avg_obs, 1)
            },
            "sampling_intervals": {
                "mean_dt_hours": round(mean_dt, 2),
                "min_dt_hours": round(min_dt, 2),
                "max_dt_hours": round(max_dt, 2),
                "is_regular_sampling": is_regular
            },
            "batches": list(df["batch_id"].unique()),
            "conditions": list(df["test_id"].unique()),
            "quality_grade": "EXCELLENT" if (excluded_rows == 0 and not nan_counts and total_components >= 10) else ("GOOD" if total_components >= 5 else "MARGINAL")
        }

        return self.clean_df, self.audit_summary, self.warnings
