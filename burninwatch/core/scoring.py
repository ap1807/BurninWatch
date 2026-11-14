"""
Anomaly Scoring, Calibration, and Screening Categorization for BurninWatch.
Normalizes heterogeneous unsupervised algorithm scores to a 0-100 screening index,
calculates composite ensemble scores, and categorizes components into Normal,
Suspicious, or High Anomaly.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy.stats import rankdata


def normalize_scores_to_index(raw_scores: np.ndarray) -> np.ndarray:
    """
    Transforms raw model anomaly scores to a calibrated 0.0 to 100.0 screening index.
    Uses a hybrid approach combining percentile ranking with min-max scaling to preserve
    both relative rank order and magnitude separation between extreme and subtle anomalies.
    """
    scores = np.asarray(raw_scores, dtype=float)
    n = len(scores)
    if n <= 1:
        return np.array([50.0] * n)

    min_s = float(np.min(scores))
    max_s = float(np.max(scores))
    
    # If all scores identical
    if abs(max_s - min_s) < 1e-9:
        return np.array([10.0] * n)

    # 1. Percentile rank (0 to 1)
    ranks = rankdata(scores, method="average") / n
    
    # 2. Linear min-max (0 to 1)
    linear_norm = (scores - min_s) / (max_s - min_s)

    # Hybrid blend: 50% rank-based (robust to outliers) + 50% linear scale (preserves relative magnitude)
    blended = 0.5 * ranks + 0.5 * linear_norm
    
    # Scale to 0.0 - 100.0 range
    normalized_index = np.clip(blended * 100.0, 0.0, 100.0)
    return np.round(normalized_index, 2)


class ScreeningScorer:
    """
    Aggregates model outputs into unified screening scores and assigns categories.
    """

    DEFAULT_THRESHOLD_SUSPICIOUS = 60.0
    DEFAULT_THRESHOLD_HIGH = 80.0

    DISCLAIMER = (
        "ENGINEERING SCREENING NOTICE: BurninWatch anomaly scores (0-100) quantify statistical "
        "deviation, drift rates, and instability across burn-in degradation trajectories. "
        "The anomaly score is a screening indicator requiring engineering evaluation, "
        "and is NOT a confirmed physical probability of field failure or operational defect."
    )

    def __init__(
        self,
        threshold_suspicious: float = DEFAULT_THRESHOLD_SUSPICIOUS,
        threshold_high: float = DEFAULT_THRESHOLD_HIGH,
        weights: Optional[Dict[str, float]] = None
    ):
        self.threshold_suspicious = float(threshold_suspicious)
        self.threshold_high = float(threshold_high)
        self.weights = weights or {}

    def compute_composite_scores(
        self,
        model_results: Dict[str, Any],
        component_ids: List[str]
    ) -> pd.DataFrame:
        """
        Combines individual algorithm scores into normalized scores and composite screening score.
        """
        n_components = len(component_ids)
        score_df = pd.DataFrame({"component_id": component_ids})

        active_algos = list(model_results.keys())
        if not active_algos:
            raise ValueError("No model results provided for scoring.")

        # Default equal weights if not specified
        equal_weight = 1.0 / len(active_algos)
        normalized_cols = []

        for algo in active_algos:
            raw = np.array(model_results[algo]["raw_scores"], dtype=float)
            norm_scores = normalize_scores_to_index(raw)
            col_norm = f"{algo}_normalized_score"
            col_raw = f"{algo}_raw_score"
            col_flag = f"{algo}_flag"

            score_df[col_raw] = np.round(raw, 4)
            score_df[col_norm] = norm_scores
            score_df[col_flag] = model_results[algo]["flags"]
            normalized_cols.append(col_norm)

        # Calculate composite score
        composite = np.zeros(n_components)
        total_w = 0.0

        for algo in active_algos:
            w = float(self.weights.get(algo, equal_weight))
            composite += w * score_df[f"{algo}_normalized_score"].to_numpy()
            total_w += w

        if total_w > 0:
            composite = composite / total_w
        
        score_df["composite_anomaly_score"] = np.round(composite, 2)

        # Number of models that flagged the component
        flag_cols = [f"{algo}_flag" for algo in active_algos]
        score_df["models_flagged_count"] = score_df[flag_cols].sum(axis=1)

        # Assign Screening Category
        def _classify(row):
            score = row["composite_anomaly_score"]
            if score >= self.threshold_high:
                return "High Anomaly"
            elif score >= self.threshold_suspicious:
                return "Suspicious"
            else:
                return "Normal"

        score_df["screening_category"] = score_df.apply(_classify, axis=1)

        return score_df

    def audit_static_limits(
        self,
        clean_df: pd.DataFrame,
        screening_df: pd.DataFrame,
        static_specs: Optional[Dict[str, Tuple[float, float]]] = None
    ) -> pd.DataFrame:
        """
        Evaluates measurements against static engineering limits (LSL, USL).
        Explicitly distinguishes between components that exceed static limits vs
        components that pass static limits but exhibit abnormal degradation patterns!
        
        Default static specs will use 3.5-sigma bounds from initial (t=0) readings
        if not provided by the engineer.
        """
        df = clean_df.copy()
        result_df = screening_df.copy()

        # Build static spec limits if not provided
        specs = static_specs or {}
        if not specs:
            # Auto-calculate realistic engineering tolerance limits based on t=0 distribution
            t0_df = df.groupby("component_id").first()
            for col in df.columns:
                if col in ["component_id", "batch_id", "test_id", "timestamp", "raw_timestamp", "elapsed_time", "dt"]:
                    continue
                if pd.api.types.is_numeric_dtype(df[col]):
                    mu = float(t0_df[col].mean()) if col in t0_df.columns else float(df[col].mean())
                    sigma = float(t0_df[col].std(ddof=1)) if (col in t0_df.columns and len(t0_df) > 1) else 1.0

                    if "resistance" in col:
                        # Standard RDS(on) spec limit allows +25% margin over nominal
                        lsl = round(max(0.0, mu * 0.70), 2)
                        usl = round(mu * 1.25, 2)
                    elif "leakage" in col:
                        # Leakage limit typically allows up to 1.0 uA or 5x baseline
                        lsl = 0.0
                        usl = round(max(1.0, mu * 5.0), 3)
                    elif "voltage" in col:
                        # Standard +/- 8% rail tolerance
                        lsl = round(mu * 0.92, 3)
                        usl = round(mu * 1.08, 3)
                    elif "current" in col:
                        lsl = round(max(0.0, mu * 0.75), 2)
                        usl = round(mu * 1.30, 2)
                    else:
                        lsl = round(mu - 6.0 * sigma, 3)
                        usl = round(mu + 6.0 * sigma, 3)

                    specs[col] = (lsl, usl)

        # Check static violations per component
        static_violation_comps = set()
        static_violation_reasons = {}

        for comp_id, group in df.groupby("component_id"):
            violations = []
            for col, (lsl, usl) in specs.items():
                if col in group.columns:
                    min_val = group[col].min()
                    max_val = group[col].max()
                    if min_val < lsl:
                        violations.append(f"{col} dropped below LSL ({min_val:.3f} < {lsl})")
                    if max_val > usl:
                        violations.append(f"{col} exceeded USL ({max_val:.3f} > {usl})")

            if violations:
                static_violation_comps.add(comp_id)
                static_violation_reasons[comp_id] = "; ".join(violations)

        # Add flags to screening dataframe
        result_df["exceeds_static_limits"] = result_df["component_id"].isin(static_violation_comps)
        result_df["static_violations_detail"] = result_df["component_id"].map(static_violation_reasons).fillna("None (Within Limits)")

        # Screening Persona Classification
        def _get_screening_verdict(row):
            is_static_fail = row["exceeds_static_limits"]
            cat = row["screening_category"]
            
            if is_static_fail:
                if cat in ["High Anomaly", "Suspicious"]:
                    return "Dual Failure (Static Limit & Abnormal Degradation)"
                else:
                    return "Static Limit Exceeded (Threshold Fail)"
            else:
                if cat == "High Anomaly":
                    return "Abnormal Degradation (Passes Static Limits)"
                elif cat == "Suspicious":
                    return "Suspicious Degradation (Passes Static Limits)"
                else:
                    return "Normal Pass (Static & Trend Compliant)"

        result_df["screening_verdict"] = result_df.apply(_get_screening_verdict, axis=1)
        result_df["is_hidden_degradation_risk"] = (
            (~result_df["exceeds_static_limits"]) & 
            (result_df["screening_category"].isin(["High Anomaly", "Suspicious"]))
        )

        return result_df
