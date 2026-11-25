"""Transparent, explainable heuristic risk scoring (0-100)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.config import RISK_LOW_MAX, RISK_MEDIUM_MAX
from core.consistency_checker import ConsistencyCheckResult
from core.tampering_detector import TamperingIndicator


@dataclass
class RiskFactor:
    factor: str
    source: str  # "Visual/Structural Forensics" or "Consistency Verification"
    severity: str
    points: int
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor": self.factor,
            "source": self.source,
            "severity": self.severity,
            "points": self.points,
            "rationale": self.rationale,
        }


@dataclass
class RiskAssessment:
    score: int  # 0 to 100
    level: str  # "Low Risk", "Medium Risk", "High Risk"
    color_hex: str
    summary: str
    factors: List[RiskFactor] = field(default_factory=list)


def compute_risk_score(
    indicators: List[TamperingIndicator],
    checks: List[ConsistencyCheckResult],
) -> RiskAssessment:
    """Aggregate heuristic points from tampering indicators and consistency failures."""
    factors: List[RiskFactor] = []

    for ind in indicators:
        if ind.points > 0:
            factors.append(
                RiskFactor(
                    factor=f"[{ind.id}] {ind.title}",
                    source="Visual/Structural Forensics",
                    severity=ind.severity,
                    points=ind.points,
                    rationale=ind.description,
                )
            )

    for chk in checks:
        if chk.points > 0:
            factors.append(
                RiskFactor(
                    factor=chk.check_name,
                    source="Consistency Verification",
                    severity=chk.severity,
                    points=chk.points,
                    rationale=chk.details,
                )
            )

    raw_total = sum(f.points for f in factors)
    score = max(0, min(100, int(round(raw_total))))

    if score <= RISK_LOW_MAX:
        level = "Low Risk"
        color_hex = "#16A34A"
        summary = (
            "No major tampering or arithmetic anomalies were triggered. Standard verification still applies."
        )
    elif score <= RISK_MEDIUM_MAX:
        level = "Medium Risk"
        color_hex = "#D97706"
        summary = (
            "Moderate visual, metadata, or consistency anomalies detected. Manual secondary review is recommended."
        )
    else:
        level = "High Risk"
        color_hex = "#DC2626"
        summary = (
            "Multiple high-weight forensic or arithmetic anomalies detected. Escalate for manual verification before approval."
        )

    return RiskAssessment(
        score=score,
        level=level,
        color_hex=color_hex,
        summary=summary,
        factors=factors,
    )
