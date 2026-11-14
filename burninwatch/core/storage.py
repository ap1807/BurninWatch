"""
Persistent Storage Manager for BurninWatch.
Maintains relational SQLite tables and file artifacts for datasets, runs, model configs,
and screening results across application restarts.
"""

import os
import json
import sqlite3
import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd


class StorageManager:
    """Manages SQLite database and filesystem storage for BurninWatch runs and datasets."""

    def __init__(self, base_dir: str = "data/storage"):
        self.base_dir = base_dir
        self.db_path = os.path.join(self.base_dir, "burninwatch.db")
        self.raw_dir = os.path.join(self.base_dir, "raw_datasets")
        self.runs_dir = os.path.join(self.base_dir, "runs")

        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.runs_dir, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Datasets Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_kb REAL,
                total_records INTEGER,
                upload_timestamp TEXT NOT NULL,
                column_mapping_json TEXT,
                raw_file_path TEXT
            )
            """)

            # Screening Runs Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                run_timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                algorithms_json TEXT,
                model_params_json TEXT,
                total_components INTEGER,
                normal_count INTEGER,
                suspicious_count INTEGER,
                high_anomaly_count INTEGER,
                hidden_risk_count INTEGER,
                audit_summary_json TEXT,
                artifacts_path TEXT,
                FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id)
            )
            """)

            # Component Anomalies Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS component_anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                component_id TEXT NOT NULL,
                batch_id TEXT,
                test_id TEXT,
                composite_score REAL,
                screening_category TEXT,
                screening_verdict TEXT,
                exceeds_static_limits INTEGER,
                is_hidden_risk INTEGER,
                models_flagged_count INTEGER,
                details_json TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
            """)

            conn.commit()

    def save_dataset(
        self,
        dataset_id: str,
        filename: str,
        content: bytes,
        file_info: Dict[str, Any],
        mapping: Dict[str, Any]
    ) -> str:
        """Saves raw dataset file and records metadata in database."""
        ext = os.path.splitext(filename)[1].lower()
        raw_path = os.path.join(self.raw_dir, f"{dataset_id}{ext}")
        with open(raw_path, "wb") as f:
            f.write(content)

        with self._get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO datasets 
            (dataset_id, filename, sha256, size_kb, total_records, upload_timestamp, column_mapping_json, raw_file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dataset_id,
                filename,
                file_info.get("sha256", ""),
                file_info.get("size_kb", 0.0),
                file_info.get("total_records", 0),
                file_info.get("upload_timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                json.dumps(mapping),
                raw_path
            ))
            conn.commit()

        return raw_path

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves raw dataset file and metadata from database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,))
            row = cursor.fetchone()
            if not row:
                return None

            record = dict(row)
            raw_path = record.get("raw_file_path")
            content = None
            if raw_path and os.path.exists(raw_path):
                with open(raw_path, "rb") as f:
                    content = f.read()

            mapping = {}
            if record.get("column_mapping_json"):
                try:
                    mapping = json.loads(record["column_mapping_json"])
                except Exception:
                    mapping = {}

            return {
                "dataset_id": record["dataset_id"],
                "filename": record["filename"],
                "sha256": record["sha256"],
                "size_kb": record["size_kb"],
                "total_records": record["total_records"],
                "upload_timestamp": record["upload_timestamp"],
                "content": content,
                "mapping": mapping,
                "raw_file_path": raw_path
            }

    def save_run(
        self,
        run_id: str,
        dataset_id: str,
        clean_df: pd.DataFrame,
        features_df: pd.DataFrame,
        screening_df: pd.DataFrame,
        model_results: Dict[str, Any],
        model_params: Dict[str, Any],
        audit_summary: Dict[str, Any],
        explanations: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Persists completed screening run: database rows and CSV/JSON artifacts.
        """
        run_folder = os.path.join(self.runs_dir, run_id)
        os.makedirs(run_folder, exist_ok=True)

        clean_path = os.path.join(run_folder, "clean_measurements.csv")
        feats_path = os.path.join(run_folder, "engineered_features.csv")
        screen_path = os.path.join(run_folder, "screening_results.csv")
        meta_path = os.path.join(run_folder, "run_metadata.json")

        clean_df.to_csv(clean_path, index=False)
        features_df.to_csv(feats_path, index=False)
        screening_df.to_csv(screen_path, index=False)

        metadata = {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model_results": model_results,
            "model_params": model_params,
            "audit_summary": audit_summary,
            "explanations": explanations or {}
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # Calculate counts
        total_comp = len(screening_df)
        normal_cnt = int((screening_df["screening_category"] == "Normal").sum())
        susp_cnt = int((screening_df["screening_category"] == "Suspicious").sum())
        high_cnt = int((screening_df["screening_category"] == "High Anomaly").sum())
        hidden_risk_cnt = int(screening_df["is_hidden_degradation_risk"].sum()) if "is_hidden_degradation_risk" in screening_df else 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO runs
            (run_id, dataset_id, run_timestamp, status, algorithms_json, model_params_json,
             total_components, normal_count, suspicious_count, high_anomaly_count, 
             hidden_risk_count, audit_summary_json, artifacts_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                dataset_id,
                metadata["timestamp"],
                "COMPLETED",
                json.dumps(list(model_results.keys())),
                json.dumps(model_params),
                total_comp,
                normal_cnt,
                susp_cnt,
                high_cnt,
                hidden_risk_cnt,
                json.dumps(audit_summary),
                run_folder
            ))

            # Delete old anomalies for this run if any
            cursor.execute("DELETE FROM component_anomalies WHERE run_id = ?", (run_id,))

            # Batch insert component anomalies
            anomaly_records = []
            for _, row in screening_df.iterrows():
                comp_id = str(row["component_id"])
                comp_exp = (explanations or {}).get(comp_id, {})
                anomaly_records.append((
                    run_id,
                    comp_id,
                    str(row.get("batch_id", "")),
                    str(row.get("test_id", "")),
                    float(row.get("composite_anomaly_score", 0.0)),
                    str(row.get("screening_category", "Normal")),
                    str(row.get("screening_verdict", "Evaluated")),
                    int(row.get("exceeds_static_limits", False)),
                    int(row.get("is_hidden_degradation_risk", False)),
                    int(row.get("models_flagged_count", 0)),
                    json.dumps(comp_exp)
                ))

            cursor.executemany("""
            INSERT INTO component_anomalies
            (run_id, component_id, batch_id, test_id, composite_score,
             screening_category, screening_verdict, exceeds_static_limits,
             is_hidden_risk, models_flagged_count, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, anomaly_records)

            conn.commit()

        return run_folder

    def list_runs(self) -> List[Dict[str, Any]]:
        """Returns list of past completed screening runs with metadata."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT r.*, d.filename as dataset_filename
            FROM runs r
            LEFT JOIN datasets d ON r.dataset_id = d.dataset_id
            ORDER BY r.run_timestamp DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Loads dataframes and metadata for a specific run."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            run_row = cursor.fetchone()
            if not run_row:
                return None

            run_dict = dict(run_row)
            folder = run_dict["artifacts_path"]
            
            clean_path = os.path.join(folder, "clean_measurements.csv")
            feats_path = os.path.join(folder, "engineered_features.csv")
            screen_path = os.path.join(folder, "screening_results.csv")
            meta_path = os.path.join(folder, "run_metadata.json")

            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    run_dict["metadata"] = json.load(f)

            if os.path.exists(clean_path):
                run_dict["clean_df"] = pd.read_csv(clean_path)
            if os.path.exists(feats_path):
                run_dict["features_df"] = pd.read_csv(feats_path)
            if os.path.exists(screen_path):
                run_dict["screening_df"] = pd.read_csv(screen_path)

            return run_dict

    def get_latest_run(self) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent completed screening run."""
        runs = self.list_runs()
        if not runs:
            return None
        return self.get_run(runs[0]["run_id"])
