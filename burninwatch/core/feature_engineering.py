"""
Degradation-Focused Feature Engineering for BurninWatch.
Transforms time-series component measurements into rich degradation, drift,
instability, and multivariate features per component.
"""

from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np


class DegradationFeatureExtractor:
    """
    Extracts statistical, temporal, and physical degradation metrics per component
    across all available measurement channels.
    """

    def __init__(self, clean_df: pd.DataFrame, measurement_columns: List[str]):
        self.clean_df = clean_df.copy()
        self.measurement_columns = measurement_columns
        self.features_df: Optional[pd.DataFrame] = None
        self.feature_meta: Dict[str, Dict[str, Any]] = {}
        self.component_metadata: Dict[str, Dict[str, Any]] = {}

    def extract_features(self) -> pd.DataFrame:
        """
        Computes comprehensive degradation feature vector for every component.
        """
        grouped = self.clean_df.groupby("component_id")
        records = []

        for comp_id, group in grouped:
            group = group.sort_values(by="elapsed_time")
            t = group["elapsed_time"].to_numpy()
            n_points = len(t)
            batch = group["batch_id"].iloc[0] if "batch_id" in group.columns else "DEFAULT"
            test_id = group["test_id"].iloc[0] if "test_id" in group.columns else "DEFAULT"
            
            comp_record: Dict[str, Any] = {
                "component_id": comp_id,
                "batch_id": batch,
                "test_id": test_id,
                "n_observations": n_points,
                "total_burnin_hours": float(t[-1] - t[0]) if n_points > 1 else 0.0
            }

            # Extract features for each measurement channel
            for col in self.measurement_columns:
                vals = group[col].to_numpy()
                prefix = col

                # 1. Boundary & Extrema Values
                init_val = float(vals[0])
                final_val = float(vals[-1])
                min_val = float(np.min(vals))
                max_val = float(np.max(vals))
                mean_val = float(np.mean(vals))
                median_val = float(np.median(vals))
                std_val = float(np.std(vals, ddof=1)) if n_points > 1 else 0.0
                
                # 2. Variation & Relative Change
                cv_val = float(std_val / max(abs(mean_val), 1e-4))
                abs_range = float(max_val - min_val)
                pct_change = float(((final_val - init_val) / max(abs(init_val), 1e-3)) * 100.0)

                # 3. Temporal Degradation Slope (Linear Least Squares)
                if n_points >= 2 and (t[-1] - t[0]) > 0:
                    # Normalized time slope: unit change per 100 hours of burn-in
                    poly = np.polyfit(t, vals, deg=1)
                    slope = float(poly[0]) # change per hour
                    slope_per_100h = float(poly[0] * 100.0)
                    
                    # R^2 fit of monotonic degradation
                    y_pred = np.polyval(poly, t)
                    ss_tot = np.sum((vals - mean_val) ** 2)
                    ss_res = np.sum((vals - y_pred) ** 2)
                    r2_fit = float(np.clip(1.0 - (ss_res / (ss_tot + 1e-9)), -10.0, 1.0)) if ss_tot > 1e-6 else 1.0
                else:
                    slope = 0.0
                    slope_per_100h = 0.0
                    r2_fit = 1.0

                # 4. Cumulative Absolute Drift & Path Tortuosity
                if n_points > 1:
                    deltas = np.diff(vals)
                    cumulative_drift = float(np.sum(np.abs(deltas)))
                    # Tortuosity ratio: cumulative movement / net displacement (high ratio = erratic hunting/jitter)
                    # Use a sensible denominator floor to prevent exploding to billions when final_val == init_val
                    net_disp = abs(final_val - init_val)
                    denom = max(net_disp, std_val * 0.1, 1e-3)
                    drift_ratio = float(np.clip(cumulative_drift / denom, 1.0, 50.0))
                    # Step jumps
                    max_step_jump = float(np.max(np.abs(deltas)))
                    max_step_idx = int(np.argmax(np.abs(deltas)))
                    jump_time = float(t[max_step_idx + 1])
                else:
                    cumulative_drift = 0.0
                    drift_ratio = 1.0
                    max_step_jump = 0.0
                    jump_time = float(t[0])

                # 5. Rolling Instability (Local Volatility)
                # Compute rolling standard deviation across window size 3
                if n_points >= 3:
                    rolling_s = pd.Series(vals).rolling(window=3).std().dropna()
                    instability_mean = float(rolling_s.mean()) if not rolling_s.empty else 0.0
                    instability_max = float(rolling_s.max()) if not rolling_s.empty else 0.0
                else:
                    instability_mean = std_val
                    instability_max = std_val

                # 6. Sudden Shift vs Monotonic Drift Metric
                # If max_step_jump accounts for majority of range, it's a sudden step shift
                step_shift_ratio = float(np.clip(max_step_jump / (abs_range + 1e-9), 0.0, 1.0)) if abs_range > 0 else 0.0

                # Populate features
                comp_record.update({
                    f"{prefix}_init": init_val,
                    f"{prefix}_final": final_val,
                    f"{prefix}_min": min_val,
                    f"{prefix}_max": max_val,
                    f"{prefix}_mean": mean_val,
                    f"{prefix}_median": median_val,
                    f"{prefix}_std": std_val,
                    f"{prefix}_cv": cv_val,
                    f"{prefix}_pct_change": pct_change,
                    f"{prefix}_range": abs_range,
                    f"{prefix}_slope": slope,
                    f"{prefix}_slope_100h": slope_per_100h,
                    f"{prefix}_r2_fit": r2_fit,
                    f"{prefix}_cumulative_drift": cumulative_drift,
                    f"{prefix}_drift_ratio": drift_ratio,
                    f"{prefix}_max_step_jump": max_step_jump,
                    f"{prefix}_jump_time": jump_time,
                    f"{prefix}_instability_mean": instability_mean,
                    f"{prefix}_instability_max": instability_max,
                    f"{prefix}_step_shift_ratio": step_shift_ratio
                })

            # Multivariate Cross-Channel Interactions (if multiple key channels exist)
            if "resistance" in self.measurement_columns and "current" in self.measurement_columns:
                # Power factor or R*I cross-interaction
                res_final = comp_record.get("resistance_final", 1.0)
                curr_final = comp_record.get("current_final", 1.0)
                comp_record["multivariate_ir_product"] = float(res_final * curr_final)

            if "leakage_current" in self.measurement_columns and "voltage" in self.measurement_columns:
                leak_final = comp_record.get("leakage_current_final", 0.0)
                volt_final = comp_record.get("voltage_final", 1.0)
                comp_record["multivariate_leak_volt_ratio"] = float(leak_final / max(abs(volt_final), 1e-3))

            records.append(comp_record)

        feat_df = pd.DataFrame(records)

        # 7. Cohort Z-Scores (Batch-level & Condition-level Normalization)
        # Avoid comparing components exposed to significantly different conditions
        # Compute normalized relative deviation for slopes, drift, and CV within each batch/condition
        key_metrics_for_zscore = []
        for col in self.measurement_columns:
            key_metrics_for_zscore.extend([
                f"{col}_slope", f"{col}_cv", f"{col}_cumulative_drift", 
                f"{col}_max_step_jump", f"{col}_instability_mean"
            ])

        for metric in key_metrics_for_zscore:
            if metric in feat_df.columns:
                # Group by batch_id and test_id to prevent false cross-condition comparison
                raw_z = feat_df.groupby(["batch_id", "test_id"])[metric].transform(
                    lambda s: np.clip((s - s.mean()) / (s.std(ddof=1) + 1e-9), -10.0, 10.0) if s.std(ddof=1) > 0 else 0.0
                ).fillna(0.0)
                feat_df[f"{metric}_cohort_z"] = raw_z

        self.features_df = feat_df
        return self.features_df

    def get_feature_matrix_for_ml(
        self, 
        selected_channels: Optional[List[str]] = None,
        include_zscores: bool = True
    ) -> Tuple[np.ndarray, List[str], pd.DataFrame]:
        """
        Prepares standard scaled numerical feature matrix X suitable for unsupervised ML.
        Excludes non-feature identifiers (component_id, batch_id, test_id).
        """
        if self.features_df is None:
            self.extract_features()

        df = self.features_df.copy()
        channels = selected_channels or self.measurement_columns
        
        # Select relevant numeric degradation features
        cols_to_use = []
        for c in df.columns:
            if c in ["component_id", "batch_id", "test_id", "n_observations", "total_burnin_hours"]:
                continue
            
            # Check if column belongs to selected channels
            belongs_to_channel = any(c.startswith(f"{chan}_") for chan in channels) or c.startswith("multivariate_")
            if not belongs_to_channel:
                continue

            if not include_zscores and c.endswith("_cohort_z"):
                continue

            # Ensure numeric
            if pd.api.types.is_numeric_dtype(df[c]):
                cols_to_use.append(c)

        if not cols_to_use:
            # Fallback to all numeric columns
            cols_to_use = [
                c for c in df.columns 
                if c not in ["component_id", "batch_id", "test_id"] and pd.api.types.is_numeric_dtype(df[c])
            ]

        feature_matrix = df[cols_to_use].fillna(0.0).to_numpy()
        return feature_matrix, cols_to_use, df
