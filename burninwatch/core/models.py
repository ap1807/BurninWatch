"""
Unsupervised Anomaly Detection Algorithms for BurninWatch.
Implements:
1. Isolation Forest
2. Local Outlier Factor (LOF)
3. One-Class Support Vector Machine (One-Class SVM)
4. PCA Reconstruction Error Outlier Detection
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM
from sklearn.decomposition import PCA



class UnsupervisedAnomalyDetector:
    """
    Executes and compares genuine unsupervised screening algorithms on degradation features.
    Provides individual model outputs, configurable hyperparameters, and raw anomaly scores.
    """

    def __init__(
        self,
        scaler_type: str = "robust",
        contamination: float = 0.05,
        random_state: int = 42
    ):
        self.scaler_type = scaler_type
        self.contamination = max(0.01, min(0.40, float(contamination)))
        self.random_state = random_state
        self.scaler = RobustScaler() if scaler_type == "robust" else StandardScaler()
        self.fitted_models: Dict[str, Any] = {}
        self.raw_scores: Dict[str, np.ndarray] = {}
        self.binary_flags: Dict[str, np.ndarray] = {}

    def fit_predict(
        self,
        X: np.ndarray,
        algorithms: Optional[List[str]] = None,
        model_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fits selected unsupervised models and returns raw anomaly scores and binary flags.
        
        Args:
            X: 2D numpy array of shape (n_components, n_features)
            algorithms: List of algorithm keys to run. Default: all 4 algorithms.
            model_params: Optional dictionary of hyperparameter overrides.
        """
        n_samples, n_features = X.shape
        if n_samples < 3:
            raise ValueError(f"At least 3 components required for unsupervised detection; found {n_samples}.")

        selected_algos = algorithms or ["isolation_forest", "lof", "one_class_svm", "pca_reconstruction"]
        params = model_params or {}

        # 1. Feature Preprocessing / Scaling
        # Fit scaler on dataset (unsupervised)
        X_scaled = self.scaler.fit_transform(X)

        results: Dict[str, Any] = {}

        # =====================================================================
        # 1. Isolation Forest
        # =====================================================================
        if "isolation_forest" in selected_algos:
            n_trees = int(params.get("if_n_estimators", 150))
            if_model = IsolationForest(
                n_estimators=n_trees,
                contamination=self.contamination,
                random_state=self.random_state,
                n_jobs=-1
            )
            if_model.fit(X_scaled)
            # decision_function: higher is more normal; negative of it is anomaly score
            raw_dec = if_model.decision_function(X_scaled)
            if_anomaly_score = -raw_dec
            if_flags = (if_model.predict(X_scaled) == -1).astype(int)

            self.fitted_models["isolation_forest"] = if_model
            self.raw_scores["isolation_forest"] = if_anomaly_score
            self.binary_flags["isolation_forest"] = if_flags

            results["isolation_forest"] = {
                "name": "Isolation Forest",
                "description": "Randomized recursive decision-tree partitioning isolation depth.",
                "raw_scores": if_anomaly_score.tolist(),
                "flags": if_flags.tolist(),
                "flagged_count": int(np.sum(if_flags)),
                "flagged_pct": round(float(np.mean(if_flags) * 100.0), 2)
            }

        # =====================================================================
        # 2. Local Outlier Factor (LOF)
        # =====================================================================
        if "lof" in selected_algos:
            # Dynamically constrain k-neighbors to sample size
            k_neighbors = int(params.get("lof_n_neighbors", 20))
            k_neighbors = max(2, min(k_neighbors, n_samples - 1))
            
            # Add micro-jitter (1e-8) to prevent exact duplicate distance division warnings
            jitter = np.random.RandomState(self.random_state).normal(0, 1e-8, X_scaled.shape)
            X_lof = X_scaled + jitter

            lof_model = LocalOutlierFactor(
                n_neighbors=k_neighbors,
                contamination=self.contamination,
                novelty=False,
                n_jobs=-1
            )
            pred_flags = lof_model.fit_predict(X_lof)
            # negative_outlier_factor_: close to -1 is normal; inverted is anomaly score
            lof_raw = -lof_model.negative_outlier_factor_
            lof_flags = (pred_flags == -1).astype(int)

            self.fitted_models["lof"] = lof_model
            self.raw_scores["lof"] = lof_raw
            self.binary_flags["lof"] = lof_flags

            results["lof"] = {
                "name": "Local Outlier Factor (LOF)",
                "description": "Local reachability density deviation relative to k-nearest neighbors.",
                "raw_scores": lof_raw.tolist(),
                "flags": lof_flags.tolist(),
                "flagged_count": int(np.sum(lof_flags)),
                "flagged_pct": round(float(np.mean(lof_flags) * 100.0), 2)
            }

        # =====================================================================
        # 3. One-Class SVM
        # =====================================================================
        if "one_class_svm" in selected_algos:
            kernel = str(params.get("ocsvm_kernel", "rbf"))
            nu = float(params.get("ocsvm_nu", self.contamination))
            nu = max(0.01, min(0.50, nu))

            ocsvm_model = OneClassSVM(
                kernel=kernel,
                nu=nu,
                gamma="scale"
            )
            ocsvm_model.fit(X_scaled)
            dec = ocsvm_model.decision_function(X_scaled)
            ocsvm_raw = -dec
            # Calibrate flags using contamination quantile for balanced multi-model ensembling
            thresh = float(np.quantile(ocsvm_raw, 1.0 - self.contamination))
            ocsvm_flags = (ocsvm_raw >= thresh).astype(int)

            self.fitted_models["one_class_svm"] = ocsvm_model
            self.raw_scores["one_class_svm"] = ocsvm_raw
            self.binary_flags["one_class_svm"] = ocsvm_flags

            results["one_class_svm"] = {
                "name": "One-Class SVM",
                "description": "Maximum-margin support vector boundary enclosing high-density normal region.",
                "raw_scores": ocsvm_raw.tolist(),
                "flags": ocsvm_flags.tolist(),
                "flagged_count": int(np.sum(ocsvm_flags)),
                "flagged_pct": round(float(np.mean(ocsvm_flags) * 100.0), 2)
            }

        # =====================================================================
        # 4. PCA Reconstruction Error
        # =====================================================================
        if "pca_reconstruction" in selected_algos:
            max_comp = max(1, min(n_samples - 1, n_features))
            # Fit preliminary PCA to determine optimal low-rank subspace explaining ~75-80% variance
            pca_prelim = PCA(random_state=self.random_state).fit(X_scaled)
            cum_var = np.cumsum(pca_prelim.explained_variance_ratio_)
            auto_k = int(np.searchsorted(cum_var, 0.75) + 1)
            # Default components: between 1 and min(max_comp, 3) unless user overridden
            default_k = max(1, min(auto_k, max_comp, 3))
            n_components = int(params.get("pca_components", default_k))
            n_components = max(1, min(n_components, max_comp))

            pca = PCA(n_components=n_components, random_state=self.random_state)
            X_projected = pca.fit_transform(X_scaled)
            X_reconstructed = pca.inverse_transform(X_projected)
            
            # Reconstruction error: squared Euclidean distance per sample
            reconstruction_errors = np.mean((X_scaled - X_reconstructed) ** 2, axis=1)
            
            # Threshold using empirical contamination quantile
            thresh = float(np.quantile(reconstruction_errors, 1.0 - self.contamination))
            pca_flags = (reconstruction_errors >= thresh).astype(int)

            self.fitted_models["pca_reconstruction"] = pca
            self.raw_scores["pca_reconstruction"] = reconstruction_errors
            self.binary_flags["pca_reconstruction"] = pca_flags

            results["pca_reconstruction"] = {
                "name": "PCA Reconstruction Error",
                "description": "Projection-reconstruction residual divergence from principal normal subspace.",
                "raw_scores": reconstruction_errors.tolist(),
                "flags": pca_flags.tolist(),
                "flagged_count": int(np.sum(pca_flags)),
                "flagged_pct": round(float(np.mean(pca_flags) * 100.0), 2),
                "explained_variance_ratio": float(np.sum(pca.explained_variance_ratio_))
            }

        return results
