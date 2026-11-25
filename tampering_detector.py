"""Defensive visual & PDF structural tampering indicator detector."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from core.document_loader import LoadedDocument, LoadedPage
from core.ocr_extractor import OCRToken


@dataclass
class TamperingIndicator:
    id: str
    page: int
    category: str
    title: str
    description: str
    severity: str  # "Low", "Medium", "High"
    evidence_strength: float  # 0.0 to 1.0
    points: int
    bbox: Optional[Tuple[int, int, int, int]] = None  # x1, y1, x2, y2


@dataclass
class TamperingReport:
    indicators: List[TamperingIndicator] = field(default_factory=list)
    ela_previews_rgb: Dict[int, np.ndarray] = field(default_factory=dict)
    metadata_summary: Dict[str, Any] = field(default_factory=dict)


EDITING_SOFTWARE_KEYWORDS = (
    "photoshop",
    "illustrator",
    "acrobat",
    "foxit",
    "nitro",
    "ilovepdf",
    "smallpdf",
    "sejda",
    "pdfescape",
    "canva",
    "gimp",
    "inkscape",
    "coreldraw",
    "wps",
)


def detect_tampering(doc: LoadedDocument, ocr_tokens: List[OCRToken]) -> TamperingReport:
    """Run defensive visual, typography, and PDF structural forensics."""
    indicators: List[TamperingIndicator] = []
    ela_previews: Dict[int, np.ndarray] = {}
    counter = 1

    # 1. PDF Metadata & Structural Anomalies
    if doc.is_pdf:
        meta_inds = _analyze_pdf_structure(doc, start_idx=counter)
        indicators.extend(meta_inds)
        counter += len(meta_inds)

    # 2. Per-page Visual & Typography Forensics
    for page in doc.pages:
        ela_heatmap, ela_inds = _analyze_ela(page, is_pdf=doc.is_pdf, start_idx=counter)
        ela_previews[page.page_number] = ela_heatmap
        indicators.extend(ela_inds)
        counter += len(ela_inds)

        noise_inds = _analyze_local_noise(page, is_pdf=doc.is_pdf, start_idx=counter)
        indicators.extend(noise_inds)
        counter += len(noise_inds)

        cm_inds = _analyze_copy_move_orb(page, start_idx=counter)
        indicators.extend(cm_inds)
        counter += len(cm_inds)

        if doc.is_pdf and page.text_spans:
            font_inds = _analyze_pdf_font_anomalies(page, start_idx=counter)
            indicators.extend(font_inds)
            counter += len(font_inds)
        else:
            page_tokens = [t for t in ocr_tokens if t.page == page.page_number]
            align_inds = _analyze_ocr_alignment(page, page_tokens, start_idx=counter)
            indicators.extend(align_inds)
            counter += len(align_inds)

    meta_summary = dict(doc.pdf_metadata) if doc.is_pdf else {
        "format": doc.validation.mime_type,
        "width": doc.pages[0].width,
        "height": doc.pages[0].height,
        "size_bytes": doc.validation.size_bytes,
    }

    return TamperingReport(
        indicators=indicators,
        ela_previews_rgb=ela_previews,
        metadata_summary=meta_summary,
    )


def _analyze_pdf_structure(doc: LoadedDocument, start_idx: int) -> List[TamperingIndicator]:
    inds: List[TamperingIndicator] = []
    idx = start_idx
    meta = doc.pdf_metadata

    producer = str(meta.get("producer") or "")
    creator = str(meta.get("creator") or "")
    combined_sw = f"{producer} {creator}".lower()

    for kw in EDITING_SOFTWARE_KEYWORDS:
        if kw in combined_sw:
            inds.append(
                TamperingIndicator(
                    id=f"IND-{idx:02d}",
                    page=1,
                    category="PDF Metadata",
                    title="Interactive PDF/Image Editor Signature",
                    description=f"Metadata Producer/Creator references editing tool ('{producer or creator}').",
                    severity="Medium",
                    evidence_strength=0.72,
                    points=14,
                    bbox=None,
                )
            )
            idx += 1
            break

    c_date = str(meta.get("creationDate") or "")
    m_date = str(meta.get("modDate") or "")
    if c_date and m_date and c_date != m_date:
        inds.append(
            TamperingIndicator(
                id=f"IND-{idx:02d}",
                page=1,
                category="PDF Metadata",
                title="CreationDate vs. ModDate Discrepancy",
                description=f"PDF was modified after initial creation (Created: {c_date}, Modified: {m_date}).",
                severity="Low",
                evidence_strength=0.60,
                points=8,
                bbox=None,
            )
        )
        idx += 1

    eof_count = int(meta.get("eof_marker_count", 1))
    if eof_count > 1:
        inds.append(
            TamperingIndicator(
                id=f"IND-{idx:02d}",
                page=1,
                category="PDF Structure",
                title="Incremental PDF Save Updates Detected",
                description=f"Found {eof_count} '%%EOF' trailers, indicating the PDF was re-saved or appended after creation.",
                severity="Medium" if eof_count >= 3 else "Low",
                evidence_strength=0.68,
                points=12 if eof_count >= 3 else 7,
                bbox=None,
            )
        )
        idx += 1

    # Check for annotations or opaque whiteout rectangles covering text
    for page in doc.pages:
        for annot in page.annotations:
            inds.append(
                TamperingIndicator(
                    id=f"IND-{idx:02d}",
                    page=page.page_number,
                    category="PDF Overlay",
                    title=f"PDF Annotation Layer ({annot['type']})",
                    description="Interactive annotation overlay detected over document content.",
                    severity="Medium",
                    evidence_strength=0.75,
                    points=14,
                    bbox=annot["rect"],
                )
            )
            idx += 1

        # Opaque white rectangles overlapping existing text spans
        for d in page.drawings:
            fill = d.get("fill")
            if fill and len(fill) >= 3 and all(c > 0.96 for c in fill[:3]):
                rx1, ry1, rx2, ry2 = d["rect"]
                rw, rh = rx2 - rx1, ry2 - ry1
                if 15 <= rw <= page.width * 0.6 and 10 <= rh <= page.height * 0.2:
                    overlaps_text = any(
                        not (sp["bbox"][2] < rx1 or sp["bbox"][0] > rx2 or sp["bbox"][3] < ry1 or sp["bbox"][1] > ry2)
                        for sp in page.text_spans
                    )
                    if overlaps_text:
                        inds.append(
                            TamperingIndicator(
                                id=f"IND-{idx:02d}",
                                page=page.page_number,
                                category="PDF Whiteout Overlay",
                                title="Opaque White Rectangle Over Text",
                                description="White-filled vector rectangle overlaps text coordinates (potential cover-up patch).",
                                severity="High",
                                evidence_strength=0.84,
                                points=22,
                                bbox=(rx1, ry1, rx2, ry2),
                            )
                        )
                        idx += 1
                        if idx - start_idx > 8:
                            break

    return inds


def _analyze_ela(page: LoadedPage, is_pdf: bool, start_idx: int) -> Tuple[np.ndarray, List[TamperingIndicator]]:
    """Compute Error Level Analysis (ELA) residual heatmap and localized outlier regions."""
    rgb = page.image_rgb
    pil_img = Image.fromarray(rgb)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    recomp = np.array(Image.open(buf).convert("RGB"), dtype=np.int16)

    diff = np.abs(rgb.astype(np.int16) - recomp).astype(np.uint8)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)

    # Amplified heatmap for visual inspection
    amp = np.clip(gray_diff.astype(np.float32) * 12.0, 0, 255).astype(np.uint8)
    heatmap_bgr = cv2.applyColorMap(amp, cv2.COLORMAP_JET)
    heatmap_rgb = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2RGB)

    inds: List[TamperingIndicator] = []
    # Rendered vector PDFs have uniform synthetic edges; ELA is primarily informative on raster images
    if is_pdf:
        return heatmap_rgb, inds

    mean_val = float(np.mean(gray_diff))
    std_val = float(np.std(gray_diff))
    if std_val < 0.5:
        return heatmap_rgb, inds

    thresh_val = max(mean_val + 4.5 * std_val, 18.0)
    _, mask = cv2.threshold(gray_diff, thresh_val, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray_diff.shape
    page_area = float(h * w)
    idx = start_idx

    # Sort contours by area descending and keep top 3 significant isolated anomalies
    valid_contours = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if 350 <= area <= page_area * 0.25 and cw >= 18 and ch >= 12:
            roi_mean = float(np.mean(gray_diff[y : y + ch, x : x + cw]))
            valid_contours.append((roi_mean, (x, y, x + cw, y + ch)))

    valid_contours.sort(key=lambda item: item[0], reverse=True)
    for roi_mean, bbox in valid_contours[:3]:
        z_score = (roi_mean - mean_val) / (std_val + 1e-6)
        if z_score >= 3.2:
            strength = min(0.92, round(0.45 + z_score * 0.08, 2))
            sev = "High" if z_score >= 5.5 else "Medium"
            pts = 18 if sev == "High" else 12
            inds.append(
                TamperingIndicator(
                    id=f"IND-{idx:02d}",
                    page=page.page_number,
                    category="Compression Anomaly (ELA)",
                    title="Localized JPEG Re-compression Residual Outlier",
                    description=f"Region exhibits elevated ELA residual ({roi_mean:.1f} vs page mean {mean_val:.1f}), suggesting localized paste/edit.",
                    severity=sev,
                    evidence_strength=strength,
                    points=pts,
                    bbox=bbox,
                )
            )
            idx += 1

    return heatmap_rgb, inds


def _analyze_local_noise(page: LoadedPage, is_pdf: bool, start_idx: int) -> List[TamperingIndicator]:
    """Detect localized high-frequency Laplacian noise variance discrepancies across blocks."""
    if is_pdf:
        return []

    gray = cv2.cvtColor(page.image_rgb, cv2.COLOR_RGB2GRAY)
    lap = np.abs(cv2.Laplacian(gray, cv2.CV_64F))

    h, w = gray.shape
    grid = 64
    block_stats: List[Tuple[float, Tuple[int, int, int, int]]] = []

    for y in range(0, h - grid, grid):
        for x in range(0, w - grid, grid):
            patch_g = gray[y : y + grid, x : x + grid]
            # Ignore pure white/blank margins
            if np.std(patch_g) < 4.0:
                continue
            noise_val = float(np.median(lap[y : y + grid, x : x + grid]))
            block_stats.append((noise_val, (x, y, x + grid, y + grid)))

    if len(block_stats) < 8:
        return []

    vals = np.array([b[0] for b in block_stats])
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) + 1e-6

    inds: List[TamperingIndicator] = []
    idx = start_idx
    outliers = [
        (abs(v - med) / mad, v, bbox)
        for v, bbox in block_stats
        if abs(v - med) / mad >= 6.5 and v > med * 2.2
    ]
    outliers.sort(key=lambda item: item[0], reverse=True)

    for z_mad, val, bbox in outliers[:2]:
        inds.append(
            TamperingIndicator(
                id=f"IND-{idx:02d}",
                page=page.page_number,
                category="Noise Floor Anomaly",
                title="Local Sensor/Compression Noise Discrepancy",
                description=f"Block high-frequency noise ({val:.1f}) diverges sharply from document median ({med:.1f}).",
                severity="Medium",
                evidence_strength=min(0.85, round(0.5 + z_mad * 0.03, 2)),
                points=11,
                bbox=bbox,
            )
        )
        idx += 1

    return inds


def _analyze_copy_move_orb(page: LoadedPage, start_idx: int) -> List[TamperingIndicator]:
    """Detect clustered ORB keypoint self-matches indicative of copy-move duplication."""
    gray = cv2.cvtColor(page.image_rgb, cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(nfeatures=900)
    kps, des = orb.detectAndCompute(gray, None)
    if des is None or len(kps) < 20:
        return []

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(des, des, k=3)

    displacements: List[Tuple[int, int, Tuple[float, float], Tuple[float, float]]] = []
    for m_list in matches:
        for m in m_list:
            if m.queryIdx == m.trainIdx or m.distance > 22:
                continue
            pt1 = kps[m.queryIdx].pt
            pt2 = kps[m.trainIdx].pt
            dx = pt2[0] - pt1[0]
            dy = pt2[1] - pt1[1]
            dist = np.hypot(dx, dy)
            # Ignore nearby typography repetition (< 45px)
            if dist < 45:
                continue
            # Quantize displacement vector to 8px bins
            bin_x = int(round(dx / 8.0))
            bin_y = int(round(dy / 8.0))
            displacements.append((bin_x, bin_y, pt1, pt2))

    if not displacements:
        return []

    from collections import Counter

    counts = Counter((d[0], d[1]) for d in displacements)
    most_common_vec, freq = counts.most_common(1)[0]
    # Require a strong cluster of identical displacement vectors (not standard table lines)
    if freq < 14:
        return []

    pts = [d[3] for d in displacements if (d[0], d[1]) == most_common_vec]
    xs = [int(p[0]) for p in pts]
    ys = [int(p[1]) for p in pts]
    bbox = (max(0, min(xs) - 12), max(0, min(ys) - 12), min(page.width, max(xs) + 12), min(page.height, max(ys) + 12))
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if bw < 20 or bh < 20 or (bw * bh) > page.width * page.height * 0.35:
        return []

    return [
        TamperingIndicator(
            id=f"IND-{start_idx:02d}",
            page=page.page_number,
            category="Copy-Move Duplication",
            title="Clustered Keypoint Cloning Pattern (ORB)",
            description=f"Detected {freq} matched keypoint pairs sharing an identical spatial shift vector.",
            severity="High" if freq >= 22 else "Medium",
            evidence_strength=min(0.90, round(0.55 + freq * 0.012, 2)),
            points=18 if freq >= 22 else 12,
            bbox=bbox,
        )
    ]


def _analyze_pdf_font_anomalies(page: LoadedPage, start_idx: int) -> List[TamperingIndicator]:
    """Check for mixed font families/sizes on the same horizontal row in digital PDFs."""
    spans = page.text_spans
    if len(spans) < 4:
        return []

    # Group spans by approximate Y-baseline (within 8px)
    rows: List[List[Dict[str, Any]]] = []
    for sp in sorted(spans, key=lambda s: s["bbox"][1]):
        cy = (sp["bbox"][1] + sp["bbox"][3]) / 2.0
        placed = False
        for r in rows:
            rcy = (r[0]["bbox"][1] + r[0]["bbox"][3]) / 2.0
            if abs(cy - rcy) <= 8:
                r.append(sp)
                placed = True
                break
        if not placed:
            rows.append([sp])

    inds: List[TamperingIndicator] = []
    idx = start_idx
    for r in rows:
        if len(r) < 2:
            continue
        fonts = {re.sub(r"^[A-Z]{6}\+", "", s["font"]) for s in r if s["font"]}
        sizes = [s["size"] for s in r if s["size"] > 0]
        # Flag if numeric/amount span uses a different font family or size on the same line
        has_digits = any(any(ch.isdigit() for ch in s["text"]) for s in r)
        if has_digits and len(fonts) >= 2 and (max(sizes) - min(sizes) >= 1.5):
            x1 = min(s["bbox"][0] for s in r)
            y1 = min(s["bbox"][1] for s in r)
            x2 = max(s["bbox"][2] for s in r)
            y2 = max(s["bbox"][3] for s in r)
            inds.append(
                TamperingIndicator(
                    id=f"IND-{idx:02d}",
                    page=page.page_number,
                    category="Typography Inconsistency",
                    title="Mixed Font Family & Size on Numeric Row",
                    description=f"Row mixes fonts ({', '.join(sorted(fonts))}) and sizes ({min(sizes)}–{max(sizes)} pt).",
                    severity="Medium",
                    evidence_strength=0.76,
                    points=14,
                    bbox=(x1, y1, x2, y2),
                )
            )
            idx += 1
            if idx - start_idx >= 3:
                break

    return inds


def _analyze_ocr_alignment(page: LoadedPage, tokens: List[OCRToken], start_idx: int) -> List[TamperingIndicator]:
    """Detect baseline vertical shifts or height outliers in numeric OCR tokens on scanned images."""
    if len(tokens) < 6:
        return []

    # Group tokens into horizontal lines
    lines: List[List[OCRToken]] = []
    for tok in sorted(tokens, key=lambda t: t.bbox[1]):
        cy = (tok.bbox[1] + tok.bbox[3]) / 2.0
        placed = False
        for ln in lines:
            lcy = (ln[0].bbox[1] + ln[0].bbox[3]) / 2.0
            if abs(cy - lcy) <= 14:
                ln.append(tok)
                placed = True
                break
        if not placed:
            lines.append([tok])

    inds: List[TamperingIndicator] = []
    idx = start_idx
    for ln in lines:
        if len(ln) < 2:
            continue
        heights = [t.bbox[3] - t.bbox[1] for t in ln]
        med_h = float(np.median(heights))
        if med_h < 10:
            continue
        for tok in ln:
            if not any(ch.isdigit() for ch in tok.text):
                continue
            th = tok.bbox[3] - tok.bbox[1]
            if abs(th - med_h) / med_h >= 0.42:
                inds.append(
                    TamperingIndicator(
                        id=f"IND-{idx:02d}",
                        page=page.page_number,
                        category="Typography / Alignment",
                        title="Numeric Token Scale/Baseline Outlier",
                        description=f"Token '{tok.text}' height ({th}px) deviates significantly from row median ({med_h:.0f}px).",
                        severity="Low",
                        evidence_strength=0.62,
                        points=9,
                        bbox=tok.bbox,
                    )
                )
                idx += 1
                break
        if idx - start_idx >= 2:
            break

    return inds
