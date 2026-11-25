"""End-to-end orchestration pipeline for KAVACH document forensics."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np

from core.consistency_checker import ConsistencyCheckResult, run_consistency_checks
from core.document_loader import LoadedDocument, load_document
from core.firebase_service import FirebaseService
from core.ocr_extractor import ExtractedFields, extract_document_fields
from core.report_generator import generate_pdf_report
from core.risk_scorer import RiskAssessment, compute_risk_score
from core.security import ValidationResult, validate_upload
from core.tampering_detector import TamperingReport, detect_tampering
from core.visualizer import render_annotated_pages


@dataclass
class AnalysisOutput:
    document_id: str
    document_type: str
    validation: ValidationResult
    document: LoadedDocument
    fields: ExtractedFields
    tampering: TamperingReport
    consistency_checks: List[ConsistencyCheckResult]
    risk: RiskAssessment
    annotated_pages_rgb: Dict[int, np.ndarray]
    pdf_report_bytes: bytes
    firebase_saved: bool
    firebase_message: str


def analyze_document(
    filename: str,
    file_bytes: bytes,
    document_type: str,
    firebase_service: Optional[FirebaseService] = None,
    persist_to_firebase: bool = True,
    upload_to_storage: bool = False,
    force_ocr: bool = False,
    analyst_id: Optional[str] = None,
) -> AnalysisOutput:
    """Validate, inspect, extract, score, visualize, report, and optionally persist a document."""
    validation = validate_upload(filename, file_bytes)
    loaded_doc = load_document(validation, file_bytes)
    fields = extract_document_fields(loaded_doc, force_ocr=force_ocr)
    tampering = detect_tampering(loaded_doc, fields.ocr_tokens)

    duplicates = []
    if firebase_service and firebase_service.is_connected and fields.invoice_number:
        duplicates = firebase_service.find_duplicate_invoices(fields.invoice_number)

    checks = run_consistency_checks(fields, document_type, duplicate_records=duplicates)
    risk = compute_risk_score(tampering.indicators, checks)
    annotated_pages = render_annotated_pages(loaded_doc, tampering.indicators)

    document_id = f"KVC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    pdf_bytes = generate_pdf_report(
        document_id=document_id,
        filename=validation.sanitized_filename,
        document_type=document_type,
        fields=fields,
        checks=checks,
        indicators=tampering.indicators,
        risk=risk,
        annotated_pages_rgb=annotated_pages,
    )

    fb_saved = False
    fb_msg = "Firebase persistence disabled or not configured."
    if firebase_service and persist_to_firebase:
        now_iso = datetime.now(timezone.utc).isoformat()
        doc_record = {
            "document_id": document_id,
            "filename": validation.sanitized_filename,
            "document_type": document_type,
            "mime_type": validation.mime_type,
            "size_bytes": validation.size_bytes,
            "upload_timestamp": now_iso,
            "extracted_info": fields.to_safe_dict(),
            "risk_score": risk.score,
            "risk_level": risk.level,
            "analysis_status": "completed",
        }
        analysis_record = {
            "document_id": document_id,
            "risk_score": risk.score,
            "risk_level": risk.level,
            "risk_summary": risk.summary,
            "risk_factors": [f.to_dict() for f in risk.factors],
            "tampering_indicators": [
                {
                    "id": ind.id,
                    "page": ind.page,
                    "category": ind.category,
                    "title": ind.title,
                    "severity": ind.severity,
                    "evidence_strength": ind.evidence_strength,
                    "bbox": list(ind.bbox) if ind.bbox else None,
                    "description": ind.description,
                }
                for ind in tampering.indicators
            ],
            "consistency_checks": [
                {
                    "check_name": c.check_name,
                    "status": c.status,
                    "scope": c.scope,
                    "severity": c.severity,
                    "details": c.details,
                }
                for c in checks
            ],
        }
        fb_saved, fb_msg = firebase_service.persist_analysis(
            document_id=document_id,
            doc_record=doc_record,
            analysis_record=analysis_record,
            analyst_id=analyst_id,
            upload_artifacts=upload_to_storage,
            raw_bytes=file_bytes if upload_to_storage else None,
            raw_filename=validation.sanitized_filename,
            pdf_report_bytes=pdf_bytes if upload_to_storage else None,
        )

    return AnalysisOutput(
        document_id=document_id,
        document_type=document_type,
        validation=validation,
        document=loaded_doc,
        fields=fields,
        tampering=tampering,
        consistency_checks=checks,
        risk=risk,
        annotated_pages_rgb=annotated_pages,
        pdf_report_bytes=pdf_bytes,
        firebase_saved=fb_saved,
        firebase_message=fb_msg,
    )
