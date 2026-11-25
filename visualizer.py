"""Render color-coded bounding-box annotations on document page images."""

from __future__ import annotations

from typing import Dict, List

import cv2
import numpy as np

from core.document_loader import LoadedDocument
from core.tampering_detector import TamperingIndicator

SEVERITY_COLORS_RGB = {
    "High": (220, 38, 38),     # Red
    "Medium": (217, 119, 6),   # Amber
    "Low": (37, 99, 235),      # Blue
}


def render_annotated_pages(
    doc: LoadedDocument,
    indicators: List[TamperingIndicator],
) -> Dict[int, np.ndarray]:
    """Draw severity-coded bounding boxes and ID badges onto each page."""
    annotated: Dict[int, np.ndarray] = {}

    for page in doc.pages:
        canvas = page.image_rgb.copy()
        overlay = canvas.copy()
        page_inds = [ind for ind in indicators if ind.page == page.page_number and ind.bbox is not None]

        for ind in page_inds:
            x1, y1, x2, y2 = ind.bbox
            x1 = max(0, min(page.width - 1, x1))
            y1 = max(0, min(page.height - 1, y1))
            x2 = max(x1 + 1, min(page.width, x2))
            y2 = max(y1 + 1, min(page.height, y2))

            color = SEVERITY_COLORS_RGB.get(ind.severity, (217, 119, 6))
            # Semi-transparent fill
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, thickness=-1)

        cv2.addWeighted(overlay, 0.16, canvas, 0.84, 0, canvas)

        for ind in page_inds:
            x1, y1, x2, y2 = ind.bbox
            x1 = max(0, min(page.width - 1, x1))
            y1 = max(0, min(page.height - 1, y1))
            x2 = max(x1 + 1, min(page.width, x2))
            y2 = max(y1 + 1, min(page.height, y2))

            color = SEVERITY_COLORS_RGB.get(ind.severity, (217, 119, 6))
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness=3)

            label = f"{ind.id} ({ind.severity})"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.55
            thickness = 2
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
            badge_y1 = max(0, y1 - th - 10)
            badge_y2 = badge_y1 + th + 10
            badge_x2 = min(page.width, x1 + tw + 12)

            cv2.rectangle(canvas, (x1, badge_y1), (badge_x2, badge_y2), color, thickness=-1)
            cv2.putText(
                canvas,
                label,
                (x1 + 6, badge_y2 - 4),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
                lineType=cv2.LINE_AA,
            )

        annotated[page.page_number] = canvas

    return annotated
