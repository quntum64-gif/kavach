"""Internal document consistency checks (arithmetic, GSTIN checksum, dates, duplicates)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from core.config import VALID_GST_RATES, VALID_GST_STATE_CODES
from core.ocr_extractor import ExtractedFields

GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass
class ConsistencyCheckResult:
    check_name: str
    status: str  # "PASS", "FAIL", "WARN", "SKIPPED"
    scope: str
    severity: str  # "None", "Low", "Medium", "High"
    details: str
    points: int = 0


def validate_gstin_checksum(gstin: str) -> tuple[bool, str]:
    """Validate 15-character Indian GSTIN format, state code, and mod-36 check digit locally."""
    if not gstin:
        return False, "GSTIN is missing."
    code = gstin.strip().upper()
    if len(code) != 15:
        return False, f"GSTIN length is {len(code)} (expected 15 characters)."
    if code[:2] not in VALID_GST_STATE_CODES:
        return False, f"Invalid Indian GST state code '{code[:2]}'."
    if not (code[2:7].isalpha() and code[7:11].isdigit() and code[11].isalpha()):
        return False, "Embedded PAN structure (positions 3-12) does not match AAAAA9999A format."
    if code[13] != "Z":
        return False, f"14th character must be 'Z' (found '{code[13]}')."
    if any(ch not in GSTIN_CHARSET for ch in code):
        return False, "GSTIN contains invalid non-alphanumeric characters."

    # Mod-36 checksum verification
    total = 0
    for idx, ch in enumerate(code[:14]):
        val = GSTIN_CHARSET.index(ch)
        factor = 1 if idx % 2 == 0 else 2
        prod = val * factor
        quotient, remainder = divmod(prod, 36)
        total += quotient + remainder

    check_val = (36 - (total % 36)) % 36
    expected_char = GSTIN_CHARSET[check_val]
    if code[14] != expected_char:
        return False, f"GSTIN mod-36 check digit mismatch (expected '{expected_char}', found '{code[14]}')."

    return True, "Valid 15-character GSTIN format, state code, and mod-36 check digit (local syntax check)."


def _parse_date_flexible(date_str: str) -> Optional[datetime]:
    formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%y",
        "%d/%m/%y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def run_consistency_checks(
    fields: ExtractedFields,
    document_type: str,
    duplicate_records: Optional[List[dict]] = None,
) -> List[ConsistencyCheckResult]:
    """Run arithmetic, format, plausibility, and duplicate checks on extracted fields."""
    results: List[ConsistencyCheckResult] = []

    # 1. Line Items vs Subtotal
    if fields.line_items and fields.subtotal is not None:
        item_sum = round(sum(li.amount for li in fields.line_items), 2)
        diff = abs(item_sum - fields.subtotal)
        if diff <= 1.0:
            results.append(
                ConsistencyCheckResult(
                    check_name="Line Items vs. Subtotal",
                    status="PASS",
                    scope="Internal Arithmetic",
                    severity="None",
                    details=f"Sum of {len(fields.line_items)} line items (INR {item_sum:,.2f}) matches Subtotal (INR {fields.subtotal:,.2f}).",
                    points=0,
                )
            )
        else:
            results.append(
                ConsistencyCheckResult(
                    check_name="Line Items vs. Subtotal",
                    status="FAIL",
                    scope="Internal Arithmetic",
                    severity="High",
                    details=f"Sum of line items (INR {item_sum:,.2f}) differs from stated Subtotal (INR {fields.subtotal:,.2f}) by INR {diff:,.2f}.",
                    points=18,
                )
            )
    else:
        results.append(
            ConsistencyCheckResult(
                check_name="Line Items vs. Subtotal",
                status="SKIPPED",
                scope="Internal Arithmetic",
                severity="None",
                details="Insufficient structured line items or subtotal extracted to compare.",
                points=0,
            )
        )

    # 2. Tax Components vs Total Tax & GST Slab Plausibility
    comp_parts = [x for x in (fields.cgst, fields.sgst, fields.igst) if x is not None]
    if comp_parts and fields.total_tax is not None:
        comp_sum = round(sum(comp_parts), 2)
        diff = abs(comp_sum - fields.total_tax)
        if diff <= 1.0:
            results.append(
                ConsistencyCheckResult(
                    check_name="GST Component Sum",
                    status="PASS",
                    scope="Internal Arithmetic",
                    severity="None",
                    details=f"CGST/SGST/IGST sum (INR {comp_sum:,.2f}) matches Total Tax (INR {fields.total_tax:,.2f}).",
                    points=0,
                )
            )
        else:
            results.append(
                ConsistencyCheckResult(
                    check_name="GST Component Sum",
                    status="FAIL",
                    scope="Internal Arithmetic",
                    severity="High",
                    details=f"Tax components sum to INR {comp_sum:,.2f}, conflicting with Total Tax INR {fields.total_tax:,.2f}.",
                    points=15,
                )
            )

    if fields.subtotal and fields.subtotal > 0 and fields.total_tax is not None:
        implied_rate = round((fields.total_tax / fields.subtotal) * 100.0, 2)
        nearest_slab = min(VALID_GST_RATES, key=lambda r: abs(r - implied_rate))
        if abs(implied_rate - nearest_slab) <= 0.35:
            results.append(
                ConsistencyCheckResult(
                    check_name="GST Slab Plausibility",
                    status="PASS",
                    scope="Tax Rate Heuristic",
                    severity="None",
                    details=f"Effective tax rate ({implied_rate:.2f}%) aligns with standard {nearest_slab:g}% GST slab.",
                    points=0,
                )
            )
        else:
            results.append(
                ConsistencyCheckResult(
                    check_name="GST Slab Plausibility",
                    status="WARN",
                    scope="Tax Rate Heuristic",
                    severity="Medium",
                    details=f"Effective tax rate ({implied_rate:.2f}%) does not match standard GST slabs (0%, 5%, 12%, 18%, 28%).",
                    points=10,
                )
            )

    # 3. Subtotal + Total Tax = Grand Total
    if fields.subtotal is not None and fields.total_tax is not None and fields.grand_total is not None:
        expected_gt = round(fields.subtotal + fields.total_tax, 2)
        diff = abs(expected_gt - fields.grand_total)
        if diff <= 1.0:
            results.append(
                ConsistencyCheckResult(
                    check_name="Subtotal + Tax = Grand Total",
                    status="PASS",
                    scope="Internal Arithmetic",
                    severity="None",
                    details=f"INR {fields.subtotal:,.2f} + INR {fields.total_tax:,.2f} = INR {expected_gt:,.2f} (matches Grand Total).",
                    points=0,
                )
            )
        else:
            results.append(
                ConsistencyCheckResult(
                    check_name="Subtotal + Tax = Grand Total",
                    status="FAIL",
                    scope="Internal Arithmetic",
                    severity="High",
                    details=f"Arithmetic mismatch: Subtotal (INR {fields.subtotal:,.2f}) + Tax (INR {fields.total_tax:,.2f}) = INR {expected_gt:,.2f}, but Grand Total states INR {fields.grand_total:,.2f}.",
                    points=22,
                )
            )
    else:
        results.append(
            ConsistencyCheckResult(
                check_name="Subtotal + Tax = Grand Total",
                status="SKIPPED",
                scope="Internal Arithmetic",
                severity="None",
                details="One or more of Subtotal, Total Tax, or Grand Total was not detected.",
                points=0,
            )
        )

    # 4. GSTIN Syntax & Checksum Validation
    if fields.gstin:
        valid, msg = validate_gstin_checksum(fields.gstin)
        if valid:
            results.append(
                ConsistencyCheckResult(
                    check_name="GSTIN Format & Checksum",
                    status="PASS",
                    scope="Local Syntax Check",
                    severity="None",
                    details=f"{fields.gstin}: {msg}",
                    points=0,
                )
            )
        else:
            results.append(
                ConsistencyCheckResult(
                    check_name="GSTIN Format & Checksum",
                    status="FAIL",
                    scope="Local Syntax Check",
                    severity="High",
                    details=f"{fields.gstin}: {msg}",
                    points=18,
                )
            )
    elif "GST" in document_type.upper() or "INVOICE" in document_type.upper():
        results.append(
            ConsistencyCheckResult(
                check_name="GSTIN Format & Checksum",
                status="WARN",
                scope="Completeness Check",
                severity="Low",
                details="No 15-character GSTIN detected on document.",
                points=6,
            )
        )

    # 5. Date Plausibility
    if fields.invoice_date:
        dt = _parse_date_flexible(fields.invoice_date)
        if dt is None:
            results.append(
                ConsistencyCheckResult(
                    check_name="Document Date Plausibility",
                    status="WARN",
                    scope="Format Check",
                    severity="Low",
                    details=f"Could not parse extracted date '{fields.invoice_date}' into a standard calendar date.",
                    points=5,
                )
            )
        else:
            now = datetime.utcnow()
            if dt.year < 2000 or (dt - now).days > 2:
                results.append(
                    ConsistencyCheckResult(
                        check_name="Document Date Plausibility",
                        status="FAIL",
                        scope="Plausibility Check",
                        severity="Medium",
                        details=f"Extracted date '{fields.invoice_date}' is implausible (far past or future-dated).",
                        points=12,
                    )
                )
            else:
                results.append(
                    ConsistencyCheckResult(
                        check_name="Document Date Plausibility",
                        status="PASS",
                        scope="Plausibility Check",
                        severity="None",
                        details=f"Extracted date '{fields.invoice_date}' is calendar-valid and plausible.",
                        points=0,
                    )
                )

    # 6. Duplicate Invoice Number Check (if Firestore history provided)
    if fields.invoice_number and duplicate_records:
        results.append(
            ConsistencyCheckResult(
                check_name="Historical Duplicate Invoice Check",
                status="WARN",
                scope="Firestore History",
                severity="Medium",
                details=f"Invoice/Document number '{fields.invoice_number}' was previously analyzed ({len(duplicate_records)} prior record(s)).",
                points=12,
            )
        )
    elif fields.invoice_number:
        results.append(
            ConsistencyCheckResult(
                check_name="Historical Duplicate Invoice Check",
                status="PASS",
                scope="History Check",
                severity="None",
                details=f"No duplicate records found for '{fields.invoice_number}'.",
                points=0,
            )
        )

    return results
