"""Safe PDF and image rendering using PyMuPDF, Pillow, and OpenCV."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Dict, List

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from core.config import MAX_PDF_PAGES
from core.security import ValidationResult


class DocumentLoadError(Exception):
    """Raised when a PDF or image is malformed, encrypted, or unreadable."""


@dataclass
class LoadedPage:
    page_number: int  # 1-indexed
    image_rgb: np.ndarray  # H x W x 3 uint8 RGB
    width: int
    height: int
    embedded_text: str = ""
    text_spans: List[Dict[str, Any]] = field(default_factory=list)
    drawings: List[Dict[str, Any]] = field(default_factory=list)
    annotations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LoadedDocument:
    validation: ValidationResult
    raw_bytes: bytes
    is_pdf: bool
    pages: List[LoadedPage]
    pdf_metadata: Dict[str, Any] = field(default_factory=dict)


def load_document(validation: ValidationResult, file_bytes: bytes) -> LoadedDocument:
    """Safely load a validated PDF or image into normalized RGB arrays and structural metadata."""
    if validation.mime_type == "application/pdf":
        return _load_pdf(validation, file_bytes)
    return _load_image(validation, file_bytes)


def _load_image(validation: ValidationResult, file_bytes: bytes) -> LoadedDocument:
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            rgb = img.convert("RGB")
            arr = np.array(rgb, dtype=np.uint8)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise DocumentLoadError(f"Malformed or corrupted image file: {exc}") from exc

    if arr.size == 0 or arr.shape[0] < 32 or arr.shape[1] < 32:
        raise DocumentLoadError("Image dimensions are too small for forensic analysis.")

    page = LoadedPage(
        page_number=1,
        image_rgb=arr,
        width=int(arr.shape[1]),
        height=int(arr.shape[0]),
    )
    return LoadedDocument(
        validation=validation,
        raw_bytes=file_bytes,
        is_pdf=False,
        pages=[page],
        pdf_metadata={},
    )


def _load_pdf(validation: ValidationResult, file_bytes: bytes) -> LoadedDocument:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise DocumentLoadError(f"Malformed or unreadable PDF structure: {exc}") from exc

    try:
        if doc.is_encrypted:
            raise DocumentLoadError("Encrypted or password-protected PDFs cannot be analyzed.")
        if doc.page_count == 0:
            raise DocumentLoadError("PDF contains zero pages.")
        if doc.page_count > MAX_PDF_PAGES:
            raise DocumentLoadError(
                f"PDF has {doc.page_count} pages, exceeding the safety cap of {MAX_PDF_PAGES} pages."
            )

        meta = dict(doc.metadata or {})
        eof_count = file_bytes.count(b"%%EOF")
        meta["eof_marker_count"] = eof_count
        meta["page_count"] = doc.page_count

        pages: List[LoadedPage] = []
        zoom = 2.0  # 144 DPI render for sharp OCR & visual forensics
        mat = fitz.Matrix(zoom, zoom)

        for idx in range(doc.page_count):
            page = doc.load_page(idx)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()

            embedded_text = page.get_text("text") or ""
            text_dict = page.get_text("dict")
            spans: List[Dict[str, Any]] = []
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for sp in line.get("spans", []):
                        txt = (sp.get("text") or "").strip()
                        if not txt:
                            continue
                        bx0, by0, bx1, by1 = sp.get("bbox", (0, 0, 0, 0))
                        spans.append(
                            {
                                "text": txt,
                                "font": sp.get("font", ""),
                                "size": round(float(sp.get("size", 0.0)), 2),
                                "color": sp.get("color", 0),
                                "bbox": (
                                    int(bx0 * zoom),
                                    int(by0 * zoom),
                                    int(bx1 * zoom),
                                    int(by1 * zoom),
                                ),
                            }
                        )

            drawings: List[Dict[str, Any]] = []
            try:
                for d in page.get_drawings():
                    rect = d.get("rect")
                    if rect is not None:
                        drawings.append(
                            {
                                "rect": (
                                    int(rect.x0 * zoom),
                                    int(rect.y0 * zoom),
                                    int(rect.x1 * zoom),
                                    int(rect.y1 * zoom),
                                ),
                                "fill": d.get("fill"),
                                "color": d.get("color"),
                            }
                        )
            except Exception:
                pass

            annots: List[Dict[str, Any]] = []
            try:
                for a in page.annots() or []:
                    r = a.rect
                    annots.append(
                        {
                            "type": a.type[1] if a.type else "Annotation",
                            "rect": (
                                int(r.x0 * zoom),
                                int(r.y0 * zoom),
                                int(r.x1 * zoom),
                                int(r.y1 * zoom),
                            ),
                        }
                    )
            except Exception:
                pass

            pages.append(
                LoadedPage(
                    page_number=idx + 1,
                    image_rgb=arr,
                    width=int(arr.shape[1]),
                    height=int(arr.shape[0]),
                    embedded_text=embedded_text,
                    text_spans=spans,
                    drawings=drawings,
                    annotations=annots,
                )
            )
    finally:
        doc.close()

    return LoadedDocument(
        validation=validation,
        raw_bytes=file_bytes,
        is_pdf=True,
        pages=pages,
        pdf_metadata=meta,
    )
