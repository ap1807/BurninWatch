"""
Reporting and Export Engine for BurninWatch.
Generates CSV, Excel (.xlsx) multi-sheet workbooks, and comprehensive printable
HTML screening reports with engineering disclaimers.
"""

import io
import json
import datetime
from typing import Dict, List, Optional, Any
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class ReportExporter:
    """Generates standardized engineering screening exports and audit reports."""

    DISCLAIMER = (
        "ENGINEERING SCREENING NOTICE & DISCLAIMER: BurninWatch anomaly scores and classifications "
        "are statistical screening indicators derived from unsupervised degradation trajectory analysis. "
        "Flagged components represent abnormal drift rates, variance spikes, or multi-parameter deviations "
        "requiring engineering review and bench re-testing. An anomaly score does NOT constitute a confirmed "
        "physical failure probability or defect diagnosis."
    )

    @staticmethod
    def export_csv(screening_df: pd.DataFrame) -> bytes:
        """Exports screening results as UTF-8 CSV."""
        buffer = io.StringIO()
        screening_df.to_csv(buffer, index=False)
        return buffer.getvalue().encode("utf-8")

    @staticmethod
    def export_excel(
        screening_df: pd.DataFrame,
        features_df: Optional[pd.DataFrame] = None,
        audit_summary: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Exports comprehensive multi-tab Excel workbook with professional styling:
        - Tab 1: Screening Summary & KPIs
        - Tab 2: Flagged Components & Explanations
        - Tab 3: Complete Screening Results
        - Tab 4: Engineered Features
        """
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # 1. Summary Sheet
            summary_data = [
                ["BurninWatch Component Screening Audit Report", ""],
                ["Generated At", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                ["Disclaimer", ReportExporter.DISCLAIMER],
                ["", ""],
                ["Metric", "Value"],
                ["Total Components Screened", len(screening_df)],
                ["Normal Components", int((screening_df["screening_category"] == "Normal").sum())],
                ["Suspicious Components", int((screening_df["screening_category"] == "Suspicious").sum())],
                ["High Anomaly Components", int((screening_df["screening_category"] == "High Anomaly").sum())],
                ["Static Limit Exceeded (Threshold)", int(screening_df["exceeds_static_limits"].sum()) if "exceeds_static_limits" in screening_df else 0],
                ["Hidden Degradation Risks (Passed Limits but Abnormal)", int(screening_df["is_hidden_degradation_risk"].sum()) if "is_hidden_degradation_risk" in screening_df else 0],
            ]
            if audit_summary:
                summary_data.extend([
                    ["", ""],
                    ["Dataset Quality Summary", ""],
                    ["Initial Records", audit_summary.get("initial_rows", "")],
                    ["Cleaned Records", audit_summary.get("clean_rows", "")],
                    ["Available Channels", ", ".join(audit_summary.get("available_measurements", []))],
                    ["Quality Grade", audit_summary.get("quality_grade", "")]
                ])
            
            df_summary = pd.DataFrame(summary_data, columns=["Parameter", "Details"])
            df_summary.to_excel(writer, sheet_name="Executive Summary", index=False)

            # 2. Flagged Components Only
            flagged = screening_df[screening_df["screening_category"].isin(["High Anomaly", "Suspicious"])]
            flagged.to_excel(writer, sheet_name="Flagged Components", index=False)

            # 3. All Screening Results
            screening_df.to_excel(writer, sheet_name="All Screening Results", index=False)

            # 4. Feature Matrix
            if features_df is not None:
                features_df.to_excel(writer, sheet_name="Engineered Features", index=False)

        return output.getvalue()

    @staticmethod
    def generate_html_report(
        run_data: Dict[str, Any],
        explanations: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generates an elegant, printable HTML engineering audit report.
        """
        meta = run_data.get("metadata", {})
        audit = meta.get("audit_summary", {})
        screening_df = run_data.get("screening_df")
        if screening_df is None:
            return "<html><body><h1>No screening data available</h1></body></html>"

        total_comp = len(screening_df)
        normal_cnt = int((screening_df["screening_category"] == "Normal").sum())
        susp_cnt = int((screening_df["screening_category"] == "Suspicious").sum())
        high_cnt = int((screening_df["screening_category"] == "High Anomaly").sum())
        hidden_cnt = int(screening_df["is_hidden_degradation_risk"].sum()) if "is_hidden_degradation_risk" in screening_df else 0

        # Build flagged components table
        flagged = screening_df[screening_df["screening_category"].isin(["High Anomaly", "Suspicious"])].sort_values(
            "composite_anomaly_score", ascending=False
        )

        rows_html = []
        for _, row in flagged.iterrows():
            cid = str(row["component_id"])
            cat = str(row["screening_category"])
            score = float(row.get("composite_anomaly_score", 0.0))
            verdict = str(row.get("screening_verdict", ""))
            static_fail = bool(row.get("exceeds_static_limits", False))
            
            badge_class = "badge-high" if cat == "High Anomaly" else "badge-susp"
            static_badge = '<span class="badge-danger">Exceeds Limits</span>' if static_fail else '<span class="badge-success">Passes Limits</span>'
            hidden_badge = '<span class="badge-warning">Hidden Risk</span>' if row.get("is_hidden_degradation_risk", False) else ''

            exp_data = (explanations or {}).get(cid, {})
            reasons = exp_data.get("primary_explanations") or ["Statistical anomaly flagged across multiple degradation dimensions."]
            reasons_html = "<ul>" + "".join([f"<li>{r}</li>" for r in reasons]) + "</ul>"

            rows_html.append(f"""
            <tr>
                <td><strong>{cid}</strong></td>
                <td>{row.get('batch_id', 'N/A')}</td>
                <td><span class="{badge_class}">{cat}</span></td>
                <td><strong>{score:.1f}</strong> / 100</td>
                <td>{static_badge} {hidden_badge}</td>
                <td><div class="reason-cell">{reasons_html}</div></td>
            </tr>
            """)

        table_body = "\n".join(rows_html) if rows_html else "<tr><td colspan='6' class='text-center'>No components flagged as Suspicious or High Anomaly.</td></tr>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>BurninWatch Screening Audit Report - {run_data.get('run_id', 'RUN')}</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        background: #f8fafc;
        margin: 0;
        padding: 40px;
    }}
    .report-container {{
        max-width: 1100px;
        margin: 0 auto;
        background: #ffffff;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
        padding: 40px;
        border: 1px solid #e2e8f0;
    }}
    .header {{
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 20px;
        margin-bottom: 25px;
    }}
    .title {{
        font-size: 26px;
        font-weight: 700;
        color: #0f172a;
        margin: 0 0 8px 0;
    }}
    .subtitle {{
        font-size: 14px;
        color: #64748b;
        margin: 0;
    }}
    .disclaimer-box {{
        background: #f1f5f9;
        border-left: 4px solid #3b82f6;
        padding: 14px 18px;
        border-radius: 6px;
        font-size: 12px;
        line-height: 1.5;
        color: #334155;
        margin-bottom: 30px;
    }}
    .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 30px;
    }}
    .kpi-card {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }}
    .kpi-val {{
        font-size: 28px;
        font-weight: 700;
        color: #0f172a;
    }}
    .kpi-label {{
        font-size: 12px;
        text-transform: uppercase;
        color: #64748b;
        margin-top: 4px;
        font-weight: 600;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        margin-top: 15px;
    }}
    th {{
        background: #f1f5f9;
        color: #475569;
        font-weight: 600;
        text-align: left;
        padding: 12px;
        border-bottom: 2px solid #cbd5e1;
    }}
    td {{
        padding: 12px;
        border-bottom: 1px solid #e2e8f0;
        vertical-align: top;
    }}
    .badge-high {{
        background: #fee2e2;
        color: #991b1b;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 11px;
    }}
    .badge-susp {{
        background: #fef3c7;
        color: #92400e;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 11px;
    }}
    .badge-danger {{
        background: #fee2e2;
        color: #dc2626;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
    }}
    .badge-success {{
        background: #dcfce7;
        color: #166534;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
    }}
    .badge-warning {{
        background: #fef08a;
        color: #854d0e;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
    }}
    .reason-cell ul {{
        margin: 0;
        padding-left: 16px;
    }}
    .reason-cell li {{
        margin-bottom: 4px;
        color: #334155;
    }}
    .footer {{
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid #e2e8f0;
        font-size: 12px;
        color: #94a3b8;
        display: flex;
        justify-content: space-between;
    }}
    @media print {{
        body {{ padding: 0; background: #fff; }}
        .report-container {{ box-shadow: none; border: none; padding: 0; }}
    }}
</style>
</head>
<body>
<div class="report-container">
    <div class="header">
        <h1 class="title">BurninWatch – Component Screening Anomaly Audit</h1>
        <p class="subtitle">Screening Run ID: <code>{run_data.get('run_id', 'RUN')}</code> | Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>

    <div class="disclaimer-box">
        <strong>IMPORTANT SCREENING NOTICE:</strong><br>
        {ReportExporter.DISCLAIMER}
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-val">{total_comp}</div>
            <div class="kpi-label">Total Screened</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val" style="color: #16a34a;">{normal_cnt}</div>
            <div class="kpi-label">Normal Pass</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val" style="color: #d97706;">{susp_cnt}</div>
            <div class="kpi-label">Suspicious</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val" style="color: #dc2626;">{high_cnt}</div>
            <div class="kpi-label">High Anomaly</div>
        </div>
    </div>

    <div style="margin-bottom: 25px; padding: 14px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
        <strong>Screening Insight:</strong> Detected <strong>{hidden_cnt}</strong> component(s) classified as <em>Hidden Degradation Risk</em> (devices that stay strictly within static engineering test limits, but exhibit statistically abnormal drift, volatility spikes, or step jumps).
    </div>

    <h2>Flagged Components & Degradation Root Explanations</h2>
    <table>
        <thead>
            <tr>
                <th>Component ID</th>
                <th>Batch / Lot</th>
                <th>Screening Category</th>
                <th>Anomaly Score</th>
                <th>Engineering Limits</th>
                <th>Statistical Degradation Explanations</th>
            </tr>
        </thead>
        <tbody>
            {table_body}
        </tbody>
    </table>

    <div class="footer">
        <span>BurninWatch v1.0.0 – Industrial Component Screening</span>
        <span>Unsupervised ML Trajectory Screening</span>
    </div>
</div>
</body>
</html>"""
        return html
