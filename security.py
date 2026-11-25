"""Input validation, magic-byte inspection, sanitization, and sensitive data masking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB


@dataclass
class ValidationResult:
    sanitized_filename: str
    extension: str
    mime_type: str
    size_bytes: int


def sanitize_filename(filename: str) -> str:
    """Strip path traversal components and unsafe characters."""
    base = Path(filename or "uploaded_document").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return cleaned or "document.bin"


def detect_magic_mime(file_bytes: bytes) -> str:
    """Inspect leading header magic bytes to determine real file format."""
    if not file_bytes or len(file_bytes) < 8:
        raise ValueError("File is empty or too small to be a valid document.")

    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    raise ValueError("Unsupported or unrecognized file signature (magic bytes mismatch). Only PDF, JPG, and PNG are allowed.")


def validate_upload(filename: str, file_bytes: bytes) -> ValidationResult:
    """Validate file size, extension, and header magic bytes."""
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    size_bytes = len(file_bytes)
    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File exceeds maximum limit of {MAX_FILE_SIZE_MB} MB.")

    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension '.{ext}'. Allowed: PDF, JPG, JPEG, PNG.")

    mime = detect_magic_mime(file_bytes)
    expected_map = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }
    if expected_map[ext] != mime:
        raise ValueError(
            f"File extension '.{ext}' does not match actual binary header ({mime}). Possible disguised file."
        )

    return ValidationResult(
        sanitized_filename=safe_name,
        extension=ext,
        mime_type=mime,
        size_bytes=size_bytes,
    )


def mask_account_number(account_no: str | None) -> str | None:
    """Mask bank account numbers leaving only the last 4 digits visible."""
    if not account_no:
        return None
    digits = re.sub(r"\s+", "", account_no)
    if len(digits) <= 4:
        return "XXXX"
    return "X" * (len(digits) - 4) + digits[-4:]


def redact_sensitive_text(text: str) -> str:
    """Redact long bank account numbers (9 to 18 digits) in raw text previews."""
    if not text:
        return ""

    def _repl(match: re.Match) -> str:
        prefix = match.group(1) or ""
        num = match.group(2)
        return f"{prefix}{'X' * (len(num) - 4)}{num[-4:]}"

    # Match account numbers preceded by A/c or Account labels, or standalone 11-18 digit numbers
    pattern = re.compile(
        r"((?:A/c|Account|Acct|Acc)[\s.:#-]*No[\s.:#-]*|(?:A/c|Account|Acct)[\s.:#-]*)(\d{9,18})\b",
        re.IGNORECASE,
    )
    redacted = pattern.sub(_repl, text)
    standalone = re.compile(r"\b(\d{11,18})\b")
    redacted = standalone.sub(lambda m: "X" * (len(m.group(1)) - 4) + m.group(1)[-4:], redacted)
    return redacted
