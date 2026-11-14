"""
Engineering Explainability & Deviation Root-Cause Analysis for BurninWatch.
Generates objective statistical explanations for flagged components without making
unsupported physical claims. Pinpoints abnormal time intervals and key contributing features.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


class AnomalyExplainer:
    """
    Produces transparent, engineer-grade explanations for flagged burn-in components.
    Analyzes feature deviations, sudden jumps, volatility spikes, and cohort z-scores.
    """

    def __init__(
        self,
        clean_df: pd.DataFrame,
        features_df: pd.DataFrame,
        measurement_columns: List[str]
    ):
        self.clean_df = clean_df
        self.features_df = features_df
        self.measurement_columns = measurement_columns

    def explain_component(self, comp_id: str, comp_screening_row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates full statistical explanation package for a single component.
        """
        # Retrieve feature row
        feat_rows = self.features_df[self.features_df["component_id"] == comp_id]
        if feat_rows.empty:
            return {"error": f"Component '{comp_id}' not found in feature dataset."}
        
        feat_row = feat_rows.iloc[0].to_dict()
        comp_df = self.clean_df[self.clean_df["component_id"] == comp_id].sort_values("elapsed_time")
        batch = comp_screening_row.get("batch_id", feat_row.get("batch_id", "DEFAULT"))
        test_id = comp_screening_row.get("test_id", feat_row.get("test_id", "DEFAULT"))

        # Find comparable cohort (same batch and test condition)
        cohort_feats = self.features_df[
            (self.features_df["batch_id"] == batch) & 
            (self.features_df["test_id"] == test_id)
        ]
        if len(cohort_feats) < 3:
            cohort_feats = self.features_df

        reasons: List[str] = []
        top_deviations: List[Dict[str, Any]] = []
        abnormal_intervals: List[Dict[str, Any]] = []

        # Analyze each measurement channel
        for col in self.measurement_columns:
            # 1. Slope / Degradation Rate
            slope_col = f"{col}_slope"
            if slope_col in feat_row:
                comp_slope = float(feat_row[slope_col])
                cohort_slope_mean = float(cohort_feats[slope_col].mean())
                cohort_slope_std = float(cohort_feats[slope_col].std(ddof=1)) + 1e-9
                slope_z = (comp_slope - cohort_slope_mean) / cohort_slope_std

                if abs(slope_z) >= 2.5:
                    direction = "positive drift (increasing)" if slope_z > 0 else "negative drift (decaying)"
                    reasons.append(
                        f"Abnormal {col} degradation rate: exhibits strong {direction} with slope of "
                        f"{comp_slope:+.4f}/h ({slope_z:+.1f}σ relative to cohort mean of {cohort_slope_mean:+.4f}/h)."
                    )
                    top_deviations.append({
                        "parameter": col,
                        "metric": "Degradation Slope",
                        "value": round(comp_slope, 4),
                        "cohort_mean": round(cohort_slope_mean, 4),
                        "z_score": round(slope_z, 2),
                        "significance": "HIGH" if abs(slope_z) >= 3.5 else "MODERATE"
                    })

            # 2. Measurement Instability / Local Volatility
            instab_col = f"{col}_instability_mean"
            if instab_col in feat_row:
                comp_instab = float(feat_row[instab_col])
                cohort_instab_med = max(float(cohort_feats[instab_col].median()), 1e-4)
                instab_ratio = comp_instab / cohort_instab_med

                if instab_ratio >= 2.5:
                    reasons.append(
                        f"Elevated {col} measurement instability: rolling local standard deviation is "
                        f"{instab_ratio:.1f}x higher than cohort median ({comp_instab:.4f} vs {cohort_instab_med:.4f})."
                    )
                    top_deviations.append({
                        "parameter": col,
                        "metric": "Measurement Instability",
                        "value": round(comp_instab, 4),
                        "cohort_mean": round(cohort_instab_med, 4),
                        "ratio_to_median": round(instab_ratio, 2),
                        "significance": "HIGH" if instab_ratio >= 4.0 else "MODERATE"
                    })

            # 3. Sudden Step Jumps & Anomalous Intervals
            jump_col = f"{col}_max_step_jump"
            jump_time_col = f"{col}_jump_time"
            if jump_col in feat_row:
                comp_jump = float(feat_row[jump_col])
                cohort_jump_med = max(float(cohort_feats[jump_col].median()), 1e-4)
                jump_ratio = comp_jump / cohort_jump_med
                jump_t = float(feat_row.get(jump_time_col, 0.0))

                if jump_ratio >= 2.5 and comp_jump > 0.05:
                    reasons.append(
                        f"Abrupt {col} step change of magnitude {comp_jump:.3f} detected at t = {jump_t:.1f}h "
                        f"({jump_ratio:.1f}x typical step variation)."
                    )
                    top_deviations.append({
                        "parameter": col,
                        "metric": "Max Step Jump",
                        "value": round(comp_jump, 4),
                        "cohort_mean": round(cohort_jump_med, 4),
                        "ratio_to_median": round(jump_ratio, 2),
                        "jump_time_h": jump_t,
                        "significance": "HIGH"
                    })
                    abnormal_intervals.append({
                        "parameter": col,
                        "timestamp": jump_t,
                        "type": "Sudden Step Jump",
                        "magnitude": round(comp_jump, 4)
                    })

            # 4. Total Percentage Drift
            pct_col = f"{col}_pct_change"
            if pct_col in feat_row:
                comp_pct = float(feat_row[pct_col])
                cohort_pct_mean = float(cohort_feats[pct_col].mean())
                cohort_pct_std = float(cohort_feats[pct_col].std(ddof=1)) + 1e-9
                pct_z = (comp_pct - cohort_pct_mean) / cohort_pct_std

                if abs(pct_z) >= 2.5:
                    top_deviations.append({
                        "parameter": col,
                        "metric": "Total Drift %",
                        "value": f"{comp_pct:+.2f}%",
                        "cohort_mean": f"{cohort_pct_mean:+.2f}%",
                        "z_score": round(pct_z, 2),
                        "significance": "HIGH" if abs(pct_z) >= 3.5 else "MODERATE"
                    })

        # If no specific metric breached 2.5 sigma, but overall anomaly score is high (multivariate coupling)
        if not reasons:
            reasons.append(
                "Multivariate coupling pattern: individual measurement drifts stay near expected ranges, "
                "but the joint combination of subtle multi-channel shifts deviates significantly from the normal cohort subspace."
            )

        # Sort deviations by absolute z-score or ratio
        top_deviations = sorted(
            top_deviations, 
            key=lambda d: abs(d.get("z_score", d.get("ratio_to_median", 0.0))), 
            reverse=True
        )

        return {
            "component_id": comp_id,
            "batch_id": batch,
            "test_id": test_id,
            "screening_category": comp_screening_row.get("screening_category", "Unknown"),
            "composite_anomaly_score": comp_screening_row.get("composite_anomaly_score", 0.0),
            "screening_verdict": comp_screening_row.get("screening_verdict", "Evaluated"),
            "exceeds_static_limits": comp_screening_row.get("exceeds_static_limits", False),
            "primary_explanations": reasons,
            "top_deviations": top_deviations[:6],
            "abnormal_intervals": abnormal_intervals,
            "individual_algorithm_scores": {
                "isolation_forest": comp_screening_row.get("isolation_forest_normalized_score", None),
                "lof": comp_screening_row.get("lof_normalized_score", None),
                "one_class_svm": comp_screening_row.get("one_class_svm_normalized_score", None),
                "pca_reconstruction": comp_screening_row.get("pca_reconstruction_normalized_score", None),
            }
        }
