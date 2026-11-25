"""Configuration constants, thresholds, and disclaimers for KAVACH."""

APP_TITLE = "KAVACH – Business Document Forensics"
APP_VERSION = "1.0.0"

DOCUMENT_TYPES = [
    "Business Invoice",
    "GST Registration Certificate",
    "Bank Statement",
    "Supplier / Vendor Document",
]

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_FILE_SIZE_MB = 15
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_PDF_PAGES = 10

SHORT_DISCLAIMER = (
    "Disclaimer: KAVACH identifies heuristic visual, structural, and arithmetic anomalies for human review. "
    "Findings are assistive indicators, not conclusive legal proof of forgery."
)

FORENSIC_DISCLAIMER = (
    "IMPORTANT FORENSIC & ACADEMIC DISCLAIMER: Error Level Analysis (ELA), local noise variance, ORB copy-move "
    "matching, font/alignment checks, and PDF metadata inspections highlight anomalies that warrant human review. "
    "Benign scanning, compression, or re-saving can trigger visual artifacts. The 0-100 Risk Score is a rule-weighted "
    "heuristic index, not a calibrated statistical probability of fraud. GSTIN checks verify 15-character syntax and "
    "mod-36 checksum locally and do not query live government GSTN servers."
)

# Risk thresholds
RISK_LOW_MAX = 29
RISK_MEDIUM_MAX = 59

# GST valid slabs in India (%)
VALID_GST_RATES = {0.0, 0.25, 3.0, 5.0, 12.0, 18.0, 28.0}

# Valid Indian State Codes (01 to 38 + 97 Other Territory)
VALID_GST_STATE_CODES = {
    f"{i:02d}" for i in range(1, 39)
} | {"97", "99"}
