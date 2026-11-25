"""Synthetic fictional document generators for safe demonstrations and testing."""

from __future__ import annotations

import io
from typing import Tuple

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def generate_synthetic_invoice_png(tampered: bool = False) -> Tuple[str, bytes]:
    """Create a 100% synthetic fictional business invoice PNG (clean or tampered)."""
    w, h = 900, 1150
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_title = _load_font(28)
    f_head = _load_font(18)
    f_body = _load_font(16)

    # Header bar
    draw.rectangle([40, 40, 860, 115], fill=(11, 29, 58))
    draw.text((60, 62), "SYNTHETIC DEMO ENTERPRISES PVT LTD", fill=(255, 255, 255), font=f_title)

    # Valid mod-36 GSTIN: 29AABCS1429B1Z5
    draw.text((50, 140), "GSTIN: 29AABCS1429B1Z5", fill=(15, 23, 42), font=f_head)
    draw.text((50, 170), "Invoice Number: DEMO-INV-2026-001", fill=(15, 23, 42), font=f_body)
    draw.text((50, 200), "Invoice Date: 15-10-2026", fill=(15, 23, 42), font=f_body)
    draw.text((50, 230), "Bank Name: Fictional Commercial Bank", fill=(15, 23, 42), font=f_body)
    draw.text((50, 260), "Account No: 123456789012  |  IFSC: FICT0001234", fill=(15, 23, 42), font=f_body)

    # Line items table
    draw.line([50, 310, 850, 310], fill=(100, 116, 139), width=2)
    draw.text((60, 325), "Item Description", fill=(11, 29, 58), font=f_head)
    draw.text((680, 325), "Amount (INR)", fill=(11, 29, 58), font=f_head)
    draw.line([50, 355, 850, 355], fill=(100, 116, 139), width=2)

    draw.text((60, 380), "Industrial Sensor Module Pack", fill=(15, 23, 42), font=f_body)
    draw.text((690, 380), "6000.00", fill=(15, 23, 42), font=f_body)

    draw.text((60, 420), "Calibration & Testing Service", fill=(15, 23, 42), font=f_body)
    draw.text((690, 420), "4000.00", fill=(15, 23, 42), font=f_body)

    draw.line([50, 470, 850, 470], fill=(100, 116, 139), width=2)

    # Totals
    draw.text((480, 500), "Subtotal:", fill=(15, 23, 42), font=f_head)
    draw.text((690, 500), "10000.00", fill=(15, 23, 42), font=f_head)

    draw.text((480, 535), "CGST @ 9%:", fill=(15, 23, 42), font=f_body)
    draw.text((690, 535), "900.00", fill=(15, 23, 42), font=f_body)

    draw.text((480, 565), "SGST @ 9%:", fill=(15, 23, 42), font=f_body)
    draw.text((690, 565), "900.00", fill=(15, 23, 42), font=f_body)

    draw.text((480, 600), "Total Tax:", fill=(15, 23, 42), font=f_body)
    draw.text((690, 600), "1800.00", fill=(15, 23, 42), font=f_body)

    draw.text((480, 645), "Grand Total:", fill=(11, 29, 58), font=f_title)
    draw.text((685, 645), "11800.00", fill=(11, 29, 58), font=f_title)

    # Save baseline JPEG first so ELA has realistic compression context
    base_buf = io.BytesIO()
    img.save(base_buf, format="JPEG", quality=88)
    base_buf.seek(0)
    working = Image.open(base_buf).convert("RGB")

    if tampered:
        # Simulate localized post-compression splice on Grand Total + altered amount (mismatch!)
        patch = Image.new("RGB", (180, 48), color=(252, 252, 255))
        p_draw = ImageDraw.Draw(patch)
        p_draw.text((8, 6), "91800.00", fill=(220, 20, 20), font=_load_font(32))
        working.paste(patch, (680, 640))

        out_buf = io.BytesIO()
        working.save(out_buf, format="PNG")
        return "synthetic_tampered_invoice.png", out_buf.getvalue()

    out_buf = io.BytesIO()
    working.save(out_buf, format="PNG")
    return "synthetic_clean_invoice.png", out_buf.getvalue()


def generate_synthetic_tampered_pdf() -> Tuple[str, bytes]:
    """Generate a synthetic PDF exhibiting mixed fonts, whiteout overlay, and arithmetic tampering."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    page.insert_text((50, 65), "FICTIONAL LOGISTICS & SUPPLY LTD", fontsize=18, fontname="helv")
    page.insert_text((50, 95), "GSTIN: 29AABCS1429B1Z9", fontsize=11, fontname="helv")  # Invalid check digit
    page.insert_text((50, 115), "Invoice No: DEMO-PDF-904", fontsize=11, fontname="helv")
    page.insert_text((50, 135), "Invoice Date: 18-10-2026", fontsize=11, fontname="helv")

    page.insert_text((50, 185), "Cloud Storage Rack Lease", fontsize=11, fontname="helv")
    page.insert_text((420, 185), "5000.00", fontsize=11, fontname="helv")

    page.insert_text((310, 235), "Subtotal:", fontsize=11, fontname="helv")
    page.insert_text((420, 235), "5000.00", fontsize=11, fontname="helv")

    page.insert_text((310, 255), "Total Tax:", fontsize=11, fontname="helv")
    page.insert_text((420, 255), "900.00", fontsize=11, fontname="helv")

    # Original text covered by an opaque whiteout rectangle + mixed font replacement
    page.insert_text((310, 285), "Grand Total:", fontsize=12, fontname="helv")
    page.insert_text((420, 285), "5900.00", fontsize=12, fontname="helv")
    page.draw_rect(fitz.Rect(415, 270, 505, 292), color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_text((420, 286), "25900.00", fontsize=15, fontname="cour")

    doc.set_metadata(
        {
            "title": "Synthetic Tampered Invoice",
            "creator": "Adobe Photoshop / PDF Editor Demo",
            "producer": "Sejda PDF Editor Simulator",
            "creationDate": "D:20261018100000Z",
            "modDate": "D:20261019184500Z",
        }
    )

    first_save = doc.tobytes()
    doc.close()

    # Re-open and save incrementally to generate a second %%EOF marker
    try:
        doc2 = fitz.open(stream=first_save, filetype="pdf")
        p2 = doc2.load_page(0)
        p2.add_text_annot((460, 265), "Manual override check")
        final_bytes = doc2.tobytes(incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        doc2.close()
    except Exception:
        final_bytes = first_save + b"\n% Manual override revision\n%%EOF\n"

    return "synthetic_tampered_invoice.pdf", final_bytes
