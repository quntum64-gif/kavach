"""Generate downloadable PDF forensic assessment reports using fpdf2."""

from __future__ import annotations

import io
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import numpy as np
from fpdf import FPDF
from PIL import Image

from core.config import APP_VERSION, FORENSIC_DISCLAIMER
from core.consistency_checker import ConsistencyCheckResult
from core.ocr_extractor import ExtractedFields
from core.risk_scorer import RiskAssessment
from core.tampering_detector import TamperingIndicator


def _safe_latin1(text: str) -> str:
    """Ensure strings render cleanly with built-in Helvetica font in fpdf2."""
    if not text:
        return ""
    replacements = {
        "–": "-",
        "—": "-",
        "•": "*",
        "₹": "INR ",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf_report(
    document_id: str,
    filename: str,
    document_type: str,
    fields: ExtractedFields,
    checks: list[ConsistencyCheckResult],
    indicators: list[TamperingIndicator],
    risk: RiskAssessment,
    annotated_pages_rgb: Dict[int, np.ndarray],
) -> bytes:
    """Build a multi-section executive PDF report and return raw PDF bytes."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Executive Dark Blue Header Banner
    pdf.set_fill_color(11, 29, 58)
    pdf.rect(10, 10, 190, 26, style="F")
    pdf.set_xy(14, 14)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 7, _safe_latin1("KAVACH - Defensive Document Forensic Report"), ln=True)
    pdf.set_x(14)
    pdf.set_font("Helvetica", "", 9)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.cell(0, 6, _safe_latin1(f"Report ID: {document_id} | Version: {APP_VERSION} | Generated: {ts}"), ln=True)

    pdf.set_y(42)
    pdf.set_text_color(15, 23, 42)

    # Risk Summary Box
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _safe_latin1("1. Heuristic Risk Assessment Summary"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _safe_latin1(f"File Analyzed: {filename} ({document_type})"), ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _safe_latin1(f"Heuristic Risk Score: {risk.score} / 100  [{risk.level}]"), ln=True)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.multi_cell(0, 5.5, _safe_latin1(risk.summary))
    pdf.ln(3)

    # Section 2: Extracted Business Fields
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _safe_latin1("2. Extracted Document Details (Sensitive Digits Masked)"), ln=True)
    pdf.set_font("Helvetica", "", 9.5)

    kv_rows = [
        ("Company Name", fields.company_name or "Not detected"),
        ("GSTIN", fields.gstin or "Not detected"),
        ("Invoice / Document No.", fields.invoice_number or "Not detected"),
        ("Document Date", fields.invoice_date or "Not detected"),
        ("Subtotal", f"INR {fields.subtotal:,.2f}" if fields.subtotal is not None else "N/A"),
        ("Total Tax", f"INR {fields.total_tax:,.2f}" if fields.total_tax is not None else "N/A"),
        ("Grand Total", f"INR {fields.grand_total:,.2f}" if fields.grand_total is not None else "N/A"),
        ("Bank Account (Masked)", fields.bank_account_masked or "Not detected"),
        ("Bank IFSC", fields.bank_ifsc or "Not detected"),
    ]
    for label, val in kv_rows:
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.cell(55, 6, _safe_latin1(f"{label}:"), border=1)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.cell(135, 6, _safe_latin1(str(val)), border=1, ln=True)

    pdf.ln(4)

    # Section 3: Internal Consistency Checks
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _safe_latin1("3. Internal Consistency Verification"), ln=True)
    pdf.set_font("Helvetica", "", 9)
    for chk in checks:
        line = f"[{chk.status}] {chk.check_name}: {chk.details}"
        pdf.multi_cell(0, 5.2, _safe_latin1(line))
        pdf.ln(1)

    pdf.ln(3)

    # Section 4: Tampering Indicators
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _safe_latin1("4. Flagged Tampering & Structural Indicators (Heuristic)"), ln=True)
    pdf.set_font("Helvetica", "", 9)
    if not indicators:
        pdf.multi_cell(0, 5.5, _safe_latin1("No localized visual or PDF structural tampering indicators triggered."))
    else:
        for ind in indicators:
            loc = f"Page {ind.page}, Box {ind.bbox}" if ind.bbox else f"Page {ind.page}, Document-level"
            strength_pct = int(round(ind.evidence_strength * 100))
            line = (
                f"{ind.id} [{ind.severity} | {strength_pct}% strength] {ind.title} ({loc}): "
                f"{ind.description}"
            )
            pdf.multi_cell(0, 5.2, _safe_latin1(line))
            pdf.ln(1)

    # Section 5: Annotated Visual Evidence (Page 1 preview)
    if annotated_pages_rgb:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _safe_latin1("5. Annotated Document Inspection Preview (Page 1)"), ln=True)
        first_page_num = sorted(annotated_pages_rgb.keys())[0]
        img_arr = annotated_pages_rgb[first_page_num]
        pil_img = Image.fromarray(img_arr)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            pil_img.save(tmp_path, format="JPEG", quality=85)
        try:
            pdf.image(str(tmp_path), x=15, w=180)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    # Disclaimer Footer Section
    pdf.ln(5)
    pdf.set_fill_color(239, 246, 255)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.multi_cell(0, 4.8, _safe_latin1(FORENSIC_DISCLAIMER), fill=True)

    raw_out = pdf.output()
    return bytes(raw_out)
