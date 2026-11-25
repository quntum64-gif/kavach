"""OCR and structured business field extraction using PyMuPDF and EasyOCR."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from core.document_loader import LoadedDocument
from core.security import mask_account_number, redact_sensitive_text

_EASYOCR_READER = None


def _get_easyocr_reader():
    """Lazy-load EasyOCR reader once per process."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        import easyocr

        _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _EASYOCR_READER


@dataclass
class OCRToken:
    page: int
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2


@dataclass
class LineItem:
    description: str
    amount: float


@dataclass
class ExtractedFields:
    company_name: Optional[str] = None
    gstin: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    subtotal: Optional[float] = None
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None
    total_tax: Optional[float] = None
    grand_total: Optional[float] = None
    bank_account_raw: Optional[str] = None
    bank_account_masked: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    line_items: List[LineItem] = field(default_factory=list)
    raw_text: str = ""
    raw_text_masked: str = ""
    ocr_tokens: List[OCRToken] = field(default_factory=list)
    ocr_engine_used: str = ""
    ocr_warnings: List[str] = field(default_factory=list)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Return Firestore/UI-safe dictionary with sensitive digits masked."""
        return {
            "company_name": self.company_name,
            "gstin": self.gstin,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "subtotal": self.subtotal,
            "cgst": self.cgst,
            "sgst": self.sgst,
            "igst": self.igst,
            "total_tax": self.total_tax,
            "grand_total": self.grand_total,
            "bank_account_masked": self.bank_account_masked,
            "bank_ifsc": self.bank_ifsc,
            "bank_name": self.bank_name,
            "line_item_count": len(self.line_items),
            "ocr_engine_used": self.ocr_engine_used,
        }


def extract_document_fields(doc: LoadedDocument, force_ocr: bool = False) -> ExtractedFields:
    """Extract text via PyMuPDF (digital PDFs) and/or EasyOCR (images & scanned PDFs)."""
    tokens: List[OCRToken] = []
    text_chunks: List[str] = []
    warnings: List[str] = []
    engines: List[str] = []

    has_digital_text = doc.is_pdf and any(len(p.embedded_text.strip()) >= 40 for p in doc.pages)

    if has_digital_text:
        engines.append("PyMuPDF Embedded Text")
        for p in doc.pages:
            text_chunks.append(p.embedded_text)
            for sp in p.text_spans:
                tokens.append(
                    OCRToken(
                        page=p.page_number,
                        text=sp["text"],
                        confidence=0.99,
                        bbox=sp["bbox"],
                    )
                )

    if (not has_digital_text) or force_ocr:
        try:
            reader = _get_easyocr_reader()
            engines.append("EasyOCR")
            for p in doc.pages:
                # Downscale very large renders for CPU efficiency while keeping coordinates mapped
                img = p.image_rgb
                h, w = img.shape[:2]
                scale = 1.0
                if max(h, w) > 1800:
                    scale = 1800.0 / float(max(h, w))
                    import cv2

                    img_in = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                else:
                    img_in = img

                results = reader.readtext(img_in, detail=1, paragraph=False)
                page_lines: List[str] = []
                for box, txt, conf in results:
                    clean_t = (txt or "").strip()
                    if not clean_t:
                        continue
                    xs = [int(pt[0] / scale) for pt in box]
                    ys = [int(pt[1] / scale) for pt in box]
                    bbox = (min(xs), min(ys), max(xs), max(ys))
                    if not has_digital_text:
                        tokens.append(
                            OCRToken(
                                page=p.page_number,
                                text=clean_t,
                                confidence=float(conf),
                                bbox=bbox,
                            )
                        )
                    page_lines.append(clean_t)
                if not has_digital_text:
                    text_chunks.append("\n".join(page_lines))
        except Exception as exc:
            warnings.append(f"EasyOCR fallback warning: {exc}")

    full_text = "\n".join(text_chunks).strip()
    parsed = _parse_business_fields(full_text)
    parsed.raw_text = full_text
    parsed.raw_text_masked = redact_sensitive_text(full_text)
    parsed.ocr_tokens = tokens
    parsed.ocr_engine_used = " + ".join(engines) if engines else "None"
    parsed.ocr_warnings = warnings
    return parsed


def _parse_amount(val_str: str) -> Optional[float]:
    if not val_str:
        return None
    cleaned = re.sub(r"[^0-9.]", "", val_str.replace(",", ""))
    if not cleaned or cleaned.count(".") > 1:
        return None
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _parse_business_fields(text: str) -> ExtractedFields:
    fields = ExtractedFields()
    if not text:
        return fields

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 1. Company Name (first prominent business line or labeled Seller/Supplier)
    for ln in lines[:8]:
        if re.search(r"\b(PVT|PRIVATE|LTD|LIMITED|LLP|ENTERPRISES|TRADERS|INDUSTRIES|SOLUTIONS|TECH)\b", ln, re.I):
            fields.company_name = re.sub(r"^(M/s\.?|Supplier|Vendor|Seller)[:\s-]*", "", ln, flags=re.I).strip()
            break
    if not fields.company_name and lines:
        for ln in lines[:4]:
            if not re.search(r"\b(TAX INVOICE|INVOICE|GSTIN|DATE|BILL TO|STATEMENT)\b", ln, re.I) and len(ln) >= 4:
                fields.company_name = ln
                break

    # 2. GSTIN (15-char Indian GST pattern)
    gst_match = re.search(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b", text.upper())
    if gst_match:
        fields.gstin = gst_match.group(1)
    else:
        # Relaxed capture if OCR misread a character in a labeled GSTIN field
        labeled_gst = re.search(r"GSTIN[\s:#-]*([A-Z0-9]{15})", text.upper())
        if labeled_gst:
            fields.gstin = labeled_gst.group(1)

    # 3. Invoice / Document Number
    inv_match = re.search(
        r"(?:Invoice|Inv|Bill|Receipt|Voucher|Certificate|Doc)[\s.#-]*(?:No|Number|ID)?[\s:#-]+([A-Z0-9][A-Z0-9/_-]{2,24})",
        text,
        re.IGNORECASE,
    )
    if inv_match:
        fields.invoice_number = inv_match.group(1).strip()

    # 4. Document Date
    date_match = re.search(
        r"(?:Date|Dated|Invoice Date)[\s:#-]*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
        text,
        re.IGNORECASE,
    )
    if date_match:
        fields.invoice_date = date_match.group(1).strip()
    else:
        any_date = re.search(r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b", text)
        if any_date:
            fields.invoice_date = any_date.group(1).strip()

    # 5. Monetary totals
    amt_pat = r"(?:INR|Rs\.?|₹)?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})|[0-9]+(?:\.[0-9]{1,2})?)"

    sub_m = re.search(rf"(?:Sub[-\s]?Total|Taxable\s+(?:Amount|Value))[\s:#-]*{amt_pat}", text, re.I)
    if sub_m:
        fields.subtotal = _parse_amount(sub_m.group(1))

    cgst_m = re.search(rf"CGST(?:\s*@?\s*\d+(?:\.\d+)?%?)?[\s:#-]*{amt_pat}", text, re.I)
    if cgst_m:
        fields.cgst = _parse_amount(cgst_m.group(1))

    sgst_m = re.search(rf"SGST(?:\s*@?\s*\d+(?:\.\d+)?%?)?[\s:#-]*{amt_pat}", text, re.I)
    if sgst_m:
        fields.sgst = _parse_amount(sgst_m.group(1))

    igst_m = re.search(rf"IGST(?:\s*@?\s*\d+(?:\.\d+)?%?)?[\s:#-]*{amt_pat}", text, re.I)
    if igst_m:
        fields.igst = _parse_amount(igst_m.group(1))

    tax_m = re.search(rf"(?:Total\s+Tax|GST\s+Amount|Total\s+GST)[\s:#-]*{amt_pat}", text, re.I)
    if tax_m:
        fields.total_tax = _parse_amount(tax_m.group(1))
    else:
        parts = [x for x in (fields.cgst, fields.sgst, fields.igst) if x is not None]
        if parts:
            fields.total_tax = round(sum(parts), 2)

    gt_m = re.search(rf"(?:Grand\s+Total|Total\s+Amount|Net\s+Payable|Total\s+Payable|Invoice\s+Total)[\s:#-]*{amt_pat}", text, re.I)
    if gt_m:
        fields.grand_total = _parse_amount(gt_m.group(1))

    # 6. Line items (heuristic: lines with item name + trailing price)
    for ln in lines:
        if re.search(r"\b(Sub[-\s]?Total|CGST|SGST|IGST|Grand\s+Total|Total|Tax|Balance|Account|GSTIN)\b", ln, re.I):
            continue
        m_item = re.match(r"^([A-Za-z][A-Za-z0-9\s()/_-]{2,45})\s+(?:INR|Rs\.?|₹)?\s*([0-9]{1,3}(?:,[0-9]{2,3})*\.[0-9]{2}|[0-9]+\.[0-9]{2})$", ln)
        if m_item:
            val = _parse_amount(m_item.group(2))
            if val is not None and val > 0:
                fields.line_items.append(LineItem(description=m_item.group(1).strip(), amount=val))

    # 7. Bank details
    acc_m = re.search(r"(?:A/c|Account|Acct)[\s.#-]*(?:No|Number)?[\s:#-]+(\d{9,18})", text, re.I)
    if acc_m:
        fields.bank_account_raw = acc_m.group(1)
        fields.bank_account_masked = mask_account_number(acc_m.group(1))

    ifsc_m = re.search(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", text.upper())
    if ifsc_m:
        fields.bank_ifsc = ifsc_m.group(1)

    bank_m = re.search(r"Bank(?:\s+Name)?[\s:#-]+([A-Za-z\s]{3,35}(?:Bank|Limited|Ltd)?)", text, re.I)
    if bank_m:
        fields.bank_name = bank_m.group(1).strip().splitlines()[0]

    return fields
