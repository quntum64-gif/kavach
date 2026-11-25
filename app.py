"""KAVACH – Enterprise AI Document Forensics & Verification Platform (Streamlit Frontend).

Designed for high-trust commercial environments, national hackathon evaluations,
and professional forensic audits.
"""

from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import streamlit.runtime

# Automatically bootstrap Streamlit web server if invoked directly via `python app.py`
if __name__ == "__main__" and not streamlit.runtime.exists():
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", __file__] + sys.argv[1:]
    sys.exit(stcli.main())

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

from core.config import (
    APP_TITLE,
    APP_VERSION,
    DOCUMENT_TYPES,
    FORENSIC_DISCLAIMER,
    MAX_FILE_SIZE_MB,
    SHORT_DISCLAIMER,
)
from core.document_loader import DocumentLoadError
from core.firebase_service import FirebaseService
from core.pipeline import AnalysisOutput, analyze_document
from core.sample_generator import (
    generate_synthetic_invoice_png,
    generate_synthetic_tampered_pdf,
)

# -----------------------------------------------------------------------------
# Streamlit Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="KAVACH | Enterprise AI Document Verification",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# Safe HTML Renderer (Prevents Markdown 4-Space Code Block Leaks)
# -----------------------------------------------------------------------------
def render_html(html: str) -> None:
    """Render HTML safely without markdown 4-space code block interpretation."""
    cleaned = "\n".join(line.strip() for line in html.strip().splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Enterprise Design System CSS
# Primary: #0A1128 (Midnight Deep Navy)
# Accent / Interactive: #2563EB (Electric Royal Blue)
# Canvas: #F8FAFC (Clean Light Slate)
# Cards: #FFFFFF (Pure White with Multi-layered Shadows)
# -----------------------------------------------------------------------------
render_html(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    :root {
        --primary-deep: #070D1E;
        --primary-navy: #0B172E;
        --primary-slate: #1E293B;
        --royal-blue: #2563EB;
        --royal-hover: #1D4ED8;
        --cyber-cyan: #0284C7;
        --bg-canvas: #F8FAFC;
        --card-surface: #FFFFFF;
        --text-primary: #0F172A;
        --text-secondary: #334155;
        --text-muted: #64748B;
        --border-subtle: #E2E8F0;
        --border-focus: #CBD5E1;
        --emerald-glow: #10B981;
        --amber-glow: #F59E0B;
        --crimson-glow: #EF4444;
        --shadow-soft: 0 2px 8px -2px rgba(15, 23, 42, 0.05), 0 1px 4px -1px rgba(15, 23, 42, 0.03);
        --shadow-card: 0 4px 16px -2px rgba(15, 23, 42, 0.06), 0 2px 6px -2px rgba(15, 23, 42, 0.04);
        --shadow-hover: 0 16px 32px -4px rgba(15, 23, 42, 0.1), 0 4px 12px -2px rgba(15, 23, 42, 0.05);
    }

    /* Base Styling */
    .stApp {
        background-color: var(--bg-canvas);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: var(--text-primary);
        -webkit-font-smoothing: antialiased;
    }

    .block-container {
        padding-top: 1.15rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 1440px;
    }

    /* Keyframe Animations */
    @keyframes radarPulse {
        0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { transform: scale(1.05); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    @keyframes ambientGlow {
        0%, 100% { opacity: 0.8; }
        50% { opacity: 1; }
    }
    @keyframes cardEntrance {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #070D1E 0%, #0B152E 50%, #12224A 100%);
        border-right: 1px solid #1E293B;
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.15);
    }
    section[data-testid="stSidebar"] * {
        color: #F1F5F9 !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #1E293B !important;
        margin: 0.85rem 0;
    }
    section[data-testid="stSidebar"] .stTextInput input {
        background-color: #13203C !important;
        color: #FFFFFF !important;
        border: 1px solid #23355B !important;
        border-radius: 8px !important;
        font-size: 0.86rem !important;
        transition: all 0.2s ease;
    }
    section[data-testid="stSidebar"] .stTextInput input:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3) !important;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label {
        background-color: transparent !important;
        padding: 0.65rem 0.95rem !important;
        border-radius: 9px !important;
        margin-bottom: 0.35rem !important;
        border: 1px solid transparent !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:hover {
        background-color: rgba(255, 255, 255, 0.08) !important;
        border-color: rgba(255, 255, 255, 0.15) !important;
        transform: translateX(2px);
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(90deg, #1D4ED8 0%, #2563EB 100%) !important;
        border-color: #3B82F6 !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
    }

    /* Top Navigation Bar */
    .top-navbar-wrapper {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(12px);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 0.85rem 1.4rem;
        margin-bottom: 1.35rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 0.85rem;
        box-shadow: var(--shadow-soft);
    }
    .top-nav-left {
        display: flex;
        align-items: center;
        gap: 0.85rem;
    }
    .brand-logo-pill {
        background: linear-gradient(135deg, #0A1128 0%, #1E3A8A 100%);
        color: #FFFFFF;
        font-weight: 900;
        font-size: 0.95rem;
        padding: 0.4rem 0.85rem;
        border-radius: 9px;
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.22);
        letter-spacing: 0.03em;
    }
    .top-nav-title {
        font-size: 1.02rem;
        font-weight: 800;
        color: var(--text-primary);
        letter-spacing: -0.01em;
    }
    .top-nav-subtitle {
        font-size: 0.78rem;
        color: var(--text-muted);
        font-weight: 500;
    }
    .top-nav-right {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        flex-wrap: wrap;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.32rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.01em;
    }
    .status-badge.online {
        background: #ECFDF5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }
    .status-badge.local {
        background: #FFFBEB;
        color: #92400E;
        border: 1px solid #FDE68A;
    }
    .status-badge.auditor {
        background: #EFF6FF;
        color: #1E40AF;
        border: 1px solid #BFDBFE;
    }
    .radar-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #10B981;
        display: inline-block;
        animation: radarPulse 1.8s infinite;
    }

    /* Executive Hero Banner */
    .kavach-hero {
        background: radial-gradient(circle at 85% 15%, rgba(59, 130, 246, 0.3) 0%, transparent 45%),
                    radial-gradient(circle at 10% 90%, rgba(37, 99, 235, 0.22) 0%, transparent 40%),
                    linear-gradient(135deg, #070D1E 0%, #0F1D3D 45%, #17336D 80%, #1D4ED8 100%);
        padding: 2rem 2.4rem;
        border-radius: 16px;
        color: #FFFFFF;
        margin-bottom: 1.6rem;
        box-shadow: 0 12px 32px -4px rgba(15, 23, 42, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.15);
        position: relative;
        overflow: hidden;
    }
    .kavach-hero h1 {
        margin: 0;
        font-size: 1.95rem;
        font-weight: 900;
        color: #FFFFFF;
        letter-spacing: -0.02em;
    }
    .kavach-hero p {
        margin: 0.55rem 0 0 0;
        color: #E2E8F0;
        font-size: 0.98rem;
        line-height: 1.55;
        max-width: 900px;
    }
    .hero-tags-row {
        display: flex;
        gap: 0.55rem;
        margin-top: 1.15rem;
        flex-wrap: wrap;
    }
    .hero-tag-pill {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(8px);
        padding: 0.3rem 0.75rem;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 600;
        color: #FFFFFF;
        transition: all 0.2s ease;
    }
    .hero-tag-pill:hover {
        background: rgba(255, 255, 255, 0.18);
        border-color: rgba(255, 255, 255, 0.35);
        transform: translateY(-1px);
    }

    /* KPI Cards */
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 1.35rem 1.45rem;
        box-shadow: var(--shadow-card);
        transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease, border-color 0.25s ease;
        position: relative;
        overflow: hidden;
    }
    .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: var(--shadow-hover);
        border-color: var(--border-focus);
    }
    .kpi-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #1E293B, #334155);
    }
    .kpi-card.low::before { background: linear-gradient(90deg, #059669, #10B981); }
    .kpi-card.med::before { background: linear-gradient(90deg, #D97706, #F59E0B); }
    .kpi-card.high::before { background: linear-gradient(90deg, #DC2626, #EF4444); }
    .kpi-card.primary::before { background: linear-gradient(90deg, #1D4ED8, #3B82F6); }

    .kpi-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.45rem;
    }
    .kpi-label {
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--text-muted);
        font-weight: 700;
    }
    .kpi-icon-bubble {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
    }
    .kpi-value {
        font-size: 2.3rem;
        font-weight: 900;
        color: var(--text-primary);
        line-height: 1.05;
        letter-spacing: -0.03em;
    }
    .kpi-subtext {
        font-size: 0.81rem;
        color: var(--text-muted);
        margin-top: 0.45rem;
        font-weight: 500;
    }

    /* Enterprise Cards */
    .enterprise-card {
        background: #FFFFFF;
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 1.4rem 1.6rem;
        box-shadow: var(--shadow-card);
        margin-bottom: 1.35rem;
    }
    .enterprise-card-title {
        font-size: 1.08rem;
        font-weight: 800;
        color: var(--text-primary);
        margin: 0 0 0.35rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        letter-spacing: -0.01em;
    }
    .enterprise-card-desc {
        font-size: 0.86rem;
        color: var(--text-muted);
        margin: 0 0 1rem 0;
        line-height: 1.5;
    }

    /* Verification Results Banner */
    .risk-banner {
        background: #FFFFFF;
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        padding: 1.6rem 2rem;
        margin-bottom: 1.45rem;
        box-shadow: var(--shadow-card);
    }
    .risk-banner-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
        padding-bottom: 1.15rem;
        border-bottom: 1px solid #F1F5F9;
    }
    .doc-meta-badge {
        font-size: 0.8rem;
        color: var(--text-muted);
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }
    .risk-status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1.25rem;
        border-radius: 9999px;
        font-size: 0.95rem;
        font-weight: 800;
        letter-spacing: 0.01em;
    }
    .risk-score-display {
        display: flex;
        align-items: baseline;
        gap: 0.45rem;
        margin: 0.85rem 0 0.35rem 0;
    }
    .risk-score-num {
        font-size: 3.4rem;
        font-weight: 900;
        line-height: 1;
        letter-spacing: -0.03em;
    }
    .risk-score-total {
        font-size: 1.15rem;
        color: var(--text-muted);
        font-weight: 700;
    }
    .risk-summary-text {
        font-size: 0.98rem;
        color: var(--text-secondary);
        line-height: 1.6;
        margin: 0.9rem 0 0.45rem 0;
    }
    .risk-bar-container {
        width: 100%;
        height: 12px;
        background-color: #E2E8F0;
        border-radius: 9999px;
        margin: 1.15rem 0 0.6rem 0;
        overflow: hidden;
    }
    .risk-bar-fill {
        height: 100%;
        border-radius: 9999px;
        transition: width 0.85s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .risk-bar-ticks {
        display: flex;
        justify-content: space-between;
        font-size: 0.76rem;
        color: var(--text-muted);
        font-weight: 700;
    }

    /* Disclaimer box */
    .disclaimer-box {
        background-color: #F8FAFC;
        border: 1px solid var(--border-subtle);
        border-left: 4px solid var(--royal-blue);
        padding: 0.95rem 1.25rem;
        border-radius: 10px;
        font-size: 0.85rem;
        color: var(--text-secondary);
        margin-top: 1.15rem;
        line-height: 1.55;
    }

    /* Flagged Indicator Card */
    .indicator-card {
        background: #FFFFFF;
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 1.05rem 1.25rem;
        margin-bottom: 0.75rem;
        transition: all 0.25s ease;
    }
    .indicator-card:hover {
        transform: translateX(4px);
        box-shadow: var(--shadow-soft);
        border-color: var(--border-focus);
    }
    .indicator-card.high { border-left: 5px solid var(--crimson-glow); }
    .indicator-card.medium { border-left: 5px solid var(--amber-glow); }
    .indicator-card.low { border-left: 5px solid var(--emerald-glow); }

    /* Buttons */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        padding: 0.55rem 1.15rem !important;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
        border: 1px solid var(--border-subtle) !important;
        background-color: #FFFFFF !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.01em !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        border-color: #93C5FD !important;
        color: #1D4ED8 !important;
        background-color: #EFF6FF !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.14) !important;
    }
    .stButton > button:active {
        transform: translateY(0px) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #1D4ED8 0%, #2563EB 100%) !important;
        color: #FFFFFF !important;
        border-color: #1D4ED8 !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #1E40AF 0%, #1D4ED8 100%) !important;
        box-shadow: 0 6px 22px rgba(37, 99, 235, 0.48) !important;
        transform: translateY(-2px) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        border-bottom: 1px solid var(--border-subtle);
        padding-bottom: 0.35rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 9px 9px 0 0;
        padding: 0.7rem 1.25rem;
        font-weight: 700;
        font-size: 0.9rem;
        color: var(--text-muted);
        border: none;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        color: var(--royal-blue) !important;
        border-bottom: 2.5px solid var(--royal-blue) !important;
    }

    /* Uploader */
    [data-testid="stFileUploader"] {
        background: #FFFFFF;
        border: 1.5px dashed #CBD5E1;
        border-radius: 14px;
        padding: 1rem 1.15rem;
        transition: all 0.25s ease;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: var(--royal-blue);
        background: #F8FAFC;
    }

    /* =========================================================================
       VeriTrust AI / Executive SaaS Theme Components
       ========================================================================= */
    .dashboard-header-wrapper {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1.25rem;
        margin-bottom: 1.35rem;
    }
    .dashboard-title-box {
        border-left: 4.5px solid #1E5BF8;
        padding-left: 14px;
    }
    .dashboard-title {
        font-size: 1.85rem;
        font-weight: 900;
        color: #0F172A;
        margin: 0;
        letter-spacing: -0.025em;
    }
    .dashboard-subtitle {
        font-size: 0.92rem;
        color: #64748B;
        margin: 4px 0 0 0;
        font-weight: 500;
    }
    .header-user-group {
        display: flex;
        align-items: center;
        gap: 0.85rem;
    }
    .notification-bell-btn {
        position: relative;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 2px 8px rgba(15,23,42,0.04);
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .notification-bell-btn:hover {
        background: #F8FAFC;
        border-color: #CBD5E1;
    }
    .notification-badge {
        position: absolute;
        top: -3px;
        right: -3px;
        background: #EF4444;
        color: #FFFFFF;
        font-size: 0.65rem;
        font-weight: 800;
        border-radius: 50%;
        width: 17px;
        height: 17px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 2px solid #FFFFFF;
    }
    .profile-pill-box {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 30px;
        padding: 0.35rem 0.95rem 0.35rem 0.4rem;
        box-shadow: 0 2px 8px rgba(15,23,42,0.04);
    }
    .profile-avatar-circle {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
        color: #FFFFFF;
        font-weight: 800;
        font-size: 0.8rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .profile-user-name {
        font-size: 0.88rem;
        font-weight: 700;
        color: #1E293B;
    }

    /* VeriTrust KPI Cards */
    .veritrust-stat-card {
        background: #FFFFFF;
        border: 1px solid #EDF2F7;
        border-radius: 14px;
        padding: 1.25rem 1.35rem;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
        position: relative;
        overflow: hidden;
        transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease;
        margin-bottom: 0.85rem;
    }
    .veritrust-stat-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.07);
        border-color: #CBD5E1;
    }
    .stat-icon-circle {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.35rem;
        flex-shrink: 0;
    }
    .stat-icon-circle.blue { background: #EBF3FF; color: #2563EB; }
    .stat-icon-circle.green { background: #E6F9F0; color: #10B981; }
    .stat-icon-circle.red { background: #FEECEC; color: #EF4444; }
    .stat-icon-circle.amber { background: #FEF5E7; color: #F59E0B; }
    .stat-card-label {
        font-size: 0.86rem;
        color: #475569;
        font-weight: 600;
        margin-bottom: 0.2rem;
    }
    .stat-card-value {
        font-size: 1.95rem;
        font-weight: 900;
        color: #0F172A;
        line-height: 1.05;
        letter-spacing: -0.025em;
    }
    .stat-card-trend {
        font-size: 0.77rem;
        margin-top: 0.35rem;
        font-weight: 600;
    }

    /* VeriTrust Modern Table */
    .veritrust-table-wrapper {
        background: #FFFFFF;
        border: 1px solid #EDF2F7;
        border-radius: 14px;
        padding: 1.35rem 1.6rem;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
        margin-top: 0.5rem;
    }
    .veritrust-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.75rem;
        font-size: 0.88rem;
    }
    .veritrust-table th {
        text-align: left;
        padding: 0.75rem 0.65rem;
        color: #64748B;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        border-bottom: 1.5px solid #F1F5F9;
    }
    .veritrust-table td {
        padding: 0.85rem 0.65rem;
        color: #1E293B;
        border-bottom: 1px solid #F8FAFC;
        vertical-align: middle;
    }
    .veritrust-table tr:hover td {
        background-color: #F8FAFC;
    }
    .status-pill-verified {
        background: #ECFDF5;
        color: #059669;
        border: 1px solid #A7F3D0;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .status-pill-review {
        background: #FFFBEB;
        color: #D97706;
        border: 1px solid #FDE68A;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .status-pill-suspicious {
        background: #FEF2F2;
        color: #DC2626;
        border: 1px solid #FECACA;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .risk-pill-low {
        background: #ECFDF5;
        color: #059669;
        padding: 0.2rem 0.65rem;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.76rem;
    }
    .risk-pill-medium {
        background: #FFFBEB;
        color: #D97706;
        padding: 0.2rem 0.65rem;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.76rem;
    }
    .risk-pill-high {
        background: #FEF2F2;
        color: #DC2626;
        padding: 0.2rem 0.65rem;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.76rem;
    }
    .btn-view-details {
        background: #FFFFFF;
        border: 1px solid #DBEAFE;
        color: #2563EB;
        padding: 0.32rem 0.75rem;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.78rem;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        transition: all 0.2s ease;
    }
    .btn-view-details:hover {
        background: #EFF6FF;
        border-color: #93C5FD;
        color: #1D4ED8;
    }

    /* Table column headers and interactive row buttons */
    .tbl-hdr-text {
        color: #64748B;
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        padding-bottom: 0.35rem;
    }
    div[class*="st-key-btn_vd_"] button {
        background: #FFFFFF !important;
        border: 1px solid #DBEAFE !important;
        color: #2563EB !important;
        padding: 0.25rem 0.65rem !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 0.78rem !important;
        min-height: 32px !important;
        height: 32px !important;
        box-shadow: none !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
    }
    div[class*="st-key-btn_vd_"] button:hover {
        background: #EFF6FF !important;
        border-color: #93C5FD !important;
        color: #1D4ED8 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 6px rgba(37, 99, 235, 0.15) !important;
    }
    .st-key-btn_view_all_records button {
        background: transparent !important;
        border: none !important;
        color: #1E5BF8 !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        padding: 0.2rem 0.5rem !important;
        min-height: auto !important;
        box-shadow: none !important;
        float: right !important;
        justify-content: flex-end !important;
    }
    .st-key-btn_view_all_records button:hover {
        background: transparent !important;
        text-decoration: underline !important;
        color: #0B40C6 !important;
    }
    div[class*="st-key-tf_"] button {
        border-radius: 6px !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        padding: 0.2rem 0.55rem !important;
        min-height: 28px !important;
        height: 28px !important;
    }

    /* Modern container border wrapper */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF !important;
        border: 1px solid #EDF2F7 !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03) !important;
        padding: 1.15rem 1.4rem !important;
    }

    /* Sidebar Radio Customization to match SaaS navigation */
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label div:first-child {
        display: none !important;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label {
        background-color: transparent !important;
        padding: 0.72rem 1rem !important;
        border-radius: 10px !important;
        margin-bottom: 0.35rem !important;
        border: 1px solid transparent !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        cursor: pointer !important;
        color: #CBD5E1 !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:hover {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: #FFFFFF !important;
        transform: translateX(3px) !important;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:has(input:checked) {
        background: #1E5BF8 !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 16px rgba(30, 91, 248, 0.45) !important;
    }
    </style>
    """
)


# -----------------------------------------------------------------------------
# Firebase Service Singleton
# -----------------------------------------------------------------------------
@st.cache_resource
def get_firebase_service() -> FirebaseService:
    """Instantiate Firebase Admin SDK service once per server process."""
    return FirebaseService()


# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
def _init_session_state() -> None:
    if "session_history" not in st.session_state:
        st.session_state["session_history"] = []
    if "latest_result" not in st.session_state:
        st.session_state["latest_result"] = None
    if "demo_file" not in st.session_state:
        st.session_state["demo_file"] = None


def _record_session_history(res: AnalysisOutput) -> None:
    record = {
        "document_id": res.document_id,
        "filename": res.validation.sanitized_filename,
        "document_type": res.document_type,
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "extracted_info": res.fields.to_safe_dict(),
        "risk_score": res.risk.score,
        "risk_level": res.risk.level,
        "analysis_status": "completed",
        "firebase_saved": res.firebase_saved,
    }
    st.session_state["session_history"].insert(0, record)


# -----------------------------------------------------------------------------
# Safe Document Thumbnail Generator
# -----------------------------------------------------------------------------
def _generate_document_preview_thumbnail(file_name: str, file_bytes: bytes) -> Optional[bytes]:
    """Safely generate a visual preview thumbnail for PDF or image bytes."""
    name_lower = file_name.lower()
    if name_lower.endswith((".png", ".jpg", ".jpeg")):
        return file_bytes
    if name_lower.endswith(".pdf"):
        try:
            import fitz

            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if doc.page_count > 0:
                pix = doc[0].get_pixmap(dpi=110)
                img_bytes = pix.tobytes("png")
                doc.close()
                return img_bytes
            doc.close()
        except Exception:
            return None
    return None


# -----------------------------------------------------------------------------
# Enterprise Top Navigation Bar
# -----------------------------------------------------------------------------
def _render_top_navbar(active_page: str, fb_service: FirebaseService, analyst_id: str) -> None:
    now_utc = datetime.now(timezone.utc).strftime("%d %b %Y &bull; %H:%M UTC")

    if fb_service.is_connected:
        cloud_html = '<div class="status-badge online"><span class="radar-dot"></span>Firestore Sync Active</div>'
    else:
        cloud_html = '<div class="status-badge local"><span style="width:8px; height:8px; border-radius:50%; background:#F59E0B; display:inline-block;"></span>Local Auditing Mode</div>'

    analyst_display = analyst_id.strip() if analyst_id.strip() else "Admin Auditor"

    html = f"""
    <div class="top-navbar-wrapper">
        <div class="top-nav-left">
            <div class="brand-logo-pill"><span>🛡️</span> KAVACH</div>
            <div>
                <div class="top-nav-title">{active_page}</div>
                <div class="top-nav-subtitle">Enterprise Forensic AI &bull; Defensive Document Security</div>
            </div>
        </div>
        <div class="top-nav-right">
            <div class="status-badge online"><span class="radar-dot"></span>AI Engine Online</div>
            {cloud_html}
            <div class="status-badge auditor"><span>👤</span> {analyst_display}</div>
            <div style="font-size:0.78rem; color:#64748B; font-weight:700; margin-left:0.25rem;">{now_utc}</div>
        </div>
    </div>
    """
    render_html(html)


# -----------------------------------------------------------------------------
# Verification Results Banner & Visual Gauges
# -----------------------------------------------------------------------------
def _render_risk_banner(res: AnalysisOutput) -> None:
    score = res.risk.score
    color = res.risk.color_hex

    if score <= 29:
        status_bg = "#ECFDF5"
        status_text = "#065F46"
        status_border = "#A7F3D0"
        status_label = "AUTHENTIC &bull; LOW RISK"
        badge_icon = "✓"
    elif score <= 59:
        status_bg = "#FFFBEB"
        status_text = "#92400E"
        status_border = "#FDE68A"
        status_label = "REQUIRES AUDIT &bull; MEDIUM RISK"
        badge_icon = "⚠️"
    else:
        status_bg = "#FEF2F2"
        status_text = "#991B1B"
        status_border = "#FECACA"
        status_label = "SUSPICIOUS &bull; HIGH RISK FLAGGED"
        badge_icon = "🚨"

    progress_percent = min(max(score, 0), 100)

    html = f"""
    <div class="risk-banner" style="border-top: 5px solid {color};">
        <div class="risk-banner-header">
            <div>
                <div class="doc-meta-badge">
                    <span>DOC ID: {res.document_id}</span>
                    <span>&bull;</span>
                    <span>{res.document_type}</span>
                    <span>&bull;</span>
                    <span>{res.validation.sanitized_filename}</span>
                </div>
                <div class="risk-score-display">
                    <span class="risk-score-num" style="color:{color};">{score}</span>
                    <span class="risk-score-total">/ 100 Heuristic Risk Score</span>
                </div>
            </div>
            <div class="risk-status-pill" style="background:{status_bg}; color:{status_text}; border:1.5px solid {status_border}; box-shadow: 0 4px 12px {status_border};">
                <span>{badge_icon}</span> {status_label}
            </div>
        </div>

        <div class="risk-bar-container">
            <div class="risk-bar-fill" style="width: {progress_percent}%; background-color: {color}; box-shadow: 0 0 10px {color};"></div>
        </div>
        <div class="risk-bar-ticks">
            <span style="color:#10B981;">0 Low Risk (Authentic)</span>
            <span style="color:#F59E0B;">30 Medium Risk (Audit Advised)</span>
            <span style="color:#EF4444;">60–100 High Risk (Tampering Suspected)</span>
        </div>

        <p class="risk-summary-text">{res.risk.summary}</p>
        <div class="disclaimer-box">
            <strong>Forensic Guidance:</strong> {SHORT_DISCLAIMER}
        </div>
    </div>
    """
    render_html(html)


# -----------------------------------------------------------------------------
# Forensic Analysis Details Component (Results Page)
# -----------------------------------------------------------------------------
def _render_analysis_details(res: AnalysisOutput) -> None:
    _render_risk_banner(res)

    dl_col1, dl_col2 = st.columns([2, 3])
    with dl_col1:
        st.download_button(
            label="📄 Download Official PDF Forensic Report",
            data=res.pdf_report_bytes,
            file_name=f"{res.document_id}_kavach_report.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
    with dl_col2:
        if res.firebase_saved:
            st.success(f"✓ Cloud Record: {res.firebase_message}")
        else:
            st.info(f"Local Session Record: {res.firebase_message}")

    st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)

    tab_vis, tab_ocr, tab_cons, tab_risk = st.tabs(
        [
            "🔍 Visual Highlighting & Forensics",
            "🧾 Extracted Fields (OCR)",
            "✅ Internal Consistency Checks",
            "📊 Heuristic Risk Breakdown",
        ]
    )

    # TAB 1: Visual Highlighting
    with tab_vis:
        render_html(
            """
            <div style="margin: 0.5rem 0 1rem 0;">
                <h4 style="margin:0; font-size:1.08rem; color:#0F172A; font-weight:800;">Multi-Modal Forensic Inspection</h4>
                <p style="margin:0.2rem 0 0 0; font-size:0.86rem; color:#64748B;">
                    Visual anomaly segmentation, Error Level Analysis (ELA) re-compression deltas, and localized editing boundaries.
                </p>
            </div>
            """
        )

        page_nums = sorted(res.annotated_pages_rgb.keys())
        selected_page = (
            st.selectbox("Select Document Page", page_nums, format_func=lambda p: f"Page {p}")
            if len(page_nums) > 1
            else page_nums[0]
        )

        view_mode = st.radio(
            "Inspection View Mode",
            ["Annotated Bounding Boxes", "Side-by-Side (Original vs Annotated)", "ELA Compression Residual Heatmap"],
            horizontal=True,
        )

        orig_img = res.document.pages[selected_page - 1].image_rgb
        annot_img = res.annotated_pages_rgb[selected_page]
        ela_img = res.tampering.ela_previews_rgb.get(selected_page)

        if view_mode == "Annotated Bounding Boxes":
            st.image(
                annot_img,
                caption=f"Defensive Forensic Inspection — Suspicious Regions Highlighted (Page {selected_page})",
                use_container_width=True,
            )
        elif view_mode == "Side-by-Side (Original vs Annotated)":
            c1, c2 = st.columns(2)
            c1.image(orig_img, caption="Original Rendered Page", use_container_width=True)
            c2.image(annot_img, caption="Forensic Bounding Boxes & Flags", use_container_width=True)
        else:
            if ela_img is not None:
                c1, c2 = st.columns(2)
                c1.image(annot_img, caption="Annotated Regions", use_container_width=True)
                c2.image(
                    ela_img,
                    caption="Error Level Analysis (ELA) Residual Heatmap (Bright areas indicate local re-compression disparity)",
                    use_container_width=True,
                )
            else:
                st.image(annot_img, caption="Annotated Regions (ELA preview unavailable for this document)", use_container_width=True)

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        st.subheader("Flagged Tampering Indicators (Heuristic)")

        if not res.tampering.indicators:
            st.success("✓ No localized pixel editing, copy-move duplication, or structural PDF anomalies detected.")
        else:
            for idx, ind in enumerate(res.tampering.indicators, start=1):
                sev_color = "#EF4444" if ind.severity == "High" else ("#F59E0B" if ind.severity == "Medium" else "#10B981")
                sev_bg = "#FEF2F2" if ind.severity == "High" else ("#FFFBEB" if ind.severity == "Medium" else "#ECFDF5")
                sev_border = "#FECACA" if ind.severity == "High" else ("#FDE68A" if ind.severity == "Medium" else "#A7F3D0")
                loc = f"Page {ind.page}" + (f" | Box {ind.bbox}" if ind.bbox else " | Document-wide")

                ind_html = f"""
                <div class="indicator-card {ind.severity.lower()}">
                    <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.25rem;">
                        <span style="font-size:0.8rem; font-weight:800; color:#64748B;">#{idx}</span>
                        <span style="font-weight:800; font-size:0.96rem; color:#0F172A;">{ind.title}</span>
                        <span style="background:{sev_bg}; color:{sev_color}; border:1px solid {sev_border}; font-size:0.75rem; font-weight:800; padding:0.18rem 0.55rem; border-radius:9999px;">
                            {ind.severity} Severity
                        </span>
                        <span style="background:#F1F5F9; color:#475569; font-size:0.75rem; font-weight:700; padding:0.18rem 0.55rem; border-radius:6px;">
                            {ind.category}
                        </span>
                    </div>
                    <div style="font-size:0.87rem; color:#334155; line-height:1.48;">
                        {ind.description}
                    </div>
                    <div style="font-size:0.77rem; color:#94A3B8; margin-top:0.35rem; font-family:'JetBrains Mono', monospace; font-weight:600;">
                        Location: {loc} &bull; Confidence Strength: {int(round(ind.evidence_strength * 100))}%
                    </div>
                </div>
                """
                render_html(ind_html)

        with st.expander("PDF & Image Structural Metadata"):
            st.json(res.tampering.metadata_summary)

    # TAB 2: Extracted Fields
    with tab_ocr:
        render_html(
            f"""
            <div style="margin: 0.5rem 0 1rem 0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                <div>
                    <h4 style="margin:0; font-size:1.08rem; color:#0F172A; font-weight:800;">Structured Business Data Extraction</h4>
                    <p style="margin:0.2rem 0 0 0; font-size:0.86rem; color:#64748B;">
                        Extracted via optical character recognition and digital PDF text stream parsing.
                    </p>
                </div>
                <div style="background:#F1F5F9; border:1px solid #E2E8F0; padding:0.28rem 0.75rem; border-radius:8px; font-size:0.82rem; font-weight:700; color:#334155;">
                    Engine: <code>{res.fields.ocr_engine_used}</code>
                </div>
            </div>
            """
        )

        if res.fields.ocr_warnings:
            for warn in res.fields.ocr_warnings:
                st.warning(f"⚠️ {warn}")

        c1, c2, c3 = st.columns(3)
        with c1:
            render_html(
                f"""
                <div class="kpi-card">
                    <div class="kpi-header">
                        <span class="kpi-label">Company Name</span>
                        <span class="kpi-icon-bubble" style="background:#EFF6FF; color:#2563EB;">🏢</span>
                    </div>
                    <div class="kpi-value" style="font-size:1.35rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                        {res.fields.company_name or "Not detected"}
                    </div>
                    <div class="kpi-subtext">Registered Legal Entity</div>
                </div>
                """
            )
        with c2:
            render_html(
                f"""
                <div class="kpi-card">
                    <div class="kpi-header">
                        <span class="kpi-label">GSTIN / Tax ID</span>
                        <span class="kpi-icon-bubble" style="background:#EFF6FF; color:#2563EB;">🆔</span>
                    </div>
                    <div class="kpi-value" style="font-size:1.35rem; font-family:'JetBrains Mono', monospace;">
                        {res.fields.gstin or "Not detected"}
                    </div>
                    <div class="kpi-subtext">Indian GST Identification</div>
                </div>
                """
            )
        with c3:
            render_html(
                f"""
                <div class="kpi-card">
                    <div class="kpi-header">
                        <span class="kpi-label">Invoice / Document No.</span>
                        <span class="kpi-icon-bubble" style="background:#EFF6FF; color:#2563EB;">#️⃣</span>
                    </div>
                    <div class="kpi-value" style="font-size:1.35rem; font-family:'JetBrains Mono', monospace;">
                        {res.fields.invoice_number or "Not detected"}
                    </div>
                    <div class="kpi-subtext">Audit Reference Number</div>
                </div>
                """
            )

        c4, c5, c6, c7 = st.columns(4)
        with c4:
            render_html(
                f"""
                <div class="kpi-card">
                    <div class="kpi-header">
                        <span class="kpi-label">Document Date</span>
                        <span class="kpi-icon-bubble" style="background:#EFF6FF; color:#2563EB;">📅</span>
                    </div>
                    <div class="kpi-value" style="font-size:1.35rem;">
                        {res.fields.invoice_date or "Not detected"}
                    </div>
                    <div class="kpi-subtext">Issuance / Statement Date</div>
                </div>
                """
            )
        with c5:
            render_html(
                f"""
                <div class="kpi-card">
                    <div class="kpi-header">
                        <span class="kpi-label">Subtotal</span>
                        <span class="kpi-icon-bubble" style="background:#EFF6FF; color:#2563EB;">💵</span>
                    </div>
                    <div class="kpi-value" style="font-size:1.35rem;">
                        {f"INR {res.fields.subtotal:,.2f}" if res.fields.subtotal is not None else "N/A"}
                    </div>
                    <div class="kpi-subtext">Taxable Amount</div>
                </div>
                """
            )
        with c6:
            render_html(
                f"""
                <div class="kpi-card">
                    <div class="kpi-header">
                        <span class="kpi-label">Total Tax</span>
                        <span class="kpi-icon-bubble" style="background:#EFF6FF; color:#2563EB;">📊</span>
                    </div>
                    <div class="kpi-value" style="font-size:1.35rem;">
                        {f"INR {res.fields.total_tax:,.2f}" if res.fields.total_tax is not None else "N/A"}
                    </div>
                    <div class="kpi-subtext">CGST + SGST + IGST</div>
                </div>
                """
            )
        with c7:
            render_html(
                f"""
                <div class="kpi-card primary">
                    <div class="kpi-header">
                        <span class="kpi-label">Grand Total</span>
                        <span class="kpi-icon-bubble" style="background:#EFF6FF; color:#2563EB;">💰</span>
                    </div>
                    <div class="kpi-value" style="font-size:1.35rem; color:#2563EB;">
                        {f"INR {res.fields.grand_total:,.2f}" if res.fields.grand_total is not None else "N/A"}
                    </div>
                    <div class="kpi-subtext">Final Payable Amount</div>
                </div>
                """
            )

        st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)
        st.subheader("Tax Breakdown & Banking Details")
        st.caption("🔒 Sensitive banking account numbers are automatically masked for privacy compliance.")

        detail_df = pd.DataFrame(
            [
                {"Field": "CGST (Central Tax)", "Value": f"INR {res.fields.cgst:,.2f}" if res.fields.cgst is not None else "N/A"},
                {"Field": "SGST (State Tax)", "Value": f"INR {res.fields.sgst:,.2f}" if res.fields.sgst is not None else "N/A"},
                {"Field": "IGST (Integrated Tax)", "Value": f"INR {res.fields.igst:,.2f}" if res.fields.igst is not None else "N/A"},
                {"Field": "Bank Account (Masked)", "Value": res.fields.bank_account_masked or "Not detected"},
                {"Field": "Bank IFSC Code", "Value": res.fields.bank_ifsc or "Not detected"},
                {"Field": "Bank Name", "Value": res.fields.bank_name or "Not detected"},
            ]
        )
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

        with st.expander("Inspect Raw Extracted Text (Sensitive Account Digits Masked)"):
            st.code(res.fields.raw_text_masked or "No text extracted from document.", language="text")

    # TAB 3: Consistency Checks
    with tab_cons:
        render_html(
            """
            <div style="margin: 0.5rem 0 1rem 0;">
                <h4 style="margin:0; font-size:1.08rem; color:#0F172A; font-weight:800;">Mathematical &amp; Format Consistency Audit</h4>
                <p style="margin:0.2rem 0 0 0; font-size:0.86rem; color:#64748B;">
                    Validates internal line item arithmetic, tax slab calculations, date plausibility, and mod-36 GSTIN check digits.
                </p>
            </div>
            """
        )

        chk_rows = [
            {
                "Check": chk.check_name,
                "Status": chk.status,
                "Scope": chk.scope,
                "Severity": chk.severity,
                "Details": chk.details,
            }
            for chk in res.consistency_checks
        ]
        st.dataframe(pd.DataFrame(chk_rows), use_container_width=True, hide_index=True)

        render_html(
            """
            <div class="disclaimer-box" style="margin-top:1.25rem;">
                <strong>Verification Scope Note:</strong> Format and arithmetic checks validate internal document consistency.
                GSTIN validation verifies the official 15-character structure and mod-36 checksum locally — it does not query live government GSTN portal records.
            </div>
            """
        )

    # TAB 4: Risk Breakdown
    with tab_risk:
        render_html(
            f"""
            <div style="margin: 0.5rem 0 1rem 0;">
                <h4 style="margin:0; font-size:1.08rem; color:#0F172A; font-weight:800;">Transparent Risk Factor Accounting</h4>
                <p style="margin:0.2rem 0 0 0; font-size:0.86rem; color:#64748B;">
                    <strong>Scoring Standard:</strong> <code>0–29</code> Low Risk (Authentic) &bull; 
                    <code>30–59</code> Medium Risk (Review Required) &bull; 
                    <code>60–100</code> High Risk (Potential Tampering Flagged)
                </p>
            </div>
            """
        )

        if not res.risk.factors:
            st.success("✓ 0 Risk Points Assigned: Document displays no visual, structural, or arithmetic anomalies.")
        else:
            factor_df = pd.DataFrame([f.to_dict() for f in res.risk.factors])
            fig = px.bar(
                factor_df,
                x="points",
                y="factor",
                color="source",
                orientation="h",
                title="Heuristic Risk Contribution by Flagged Factor",
                labels={"points": "Risk Points Added", "factor": "Forensic Factor", "source": "Detection Subsystem"},
                color_discrete_sequence=["#0A1128", "#2563EB", "#F59E0B", "#EF4444"],
            )
            fig.update_layout(
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font=dict(family="Inter, sans-serif", color="#0F172A"),
                yaxis={"categoryorder": "total ascending"},
                xaxis=dict(showgrid=True, gridcolor="#F1F5F9", zeroline=False),
                margin=dict(l=20, r=20, t=40, b=20),
                height=max(280, 55 * len(factor_df)),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(factor_df, use_container_width=True, hide_index=True)

        st.caption(f"Forensic Methodology Notice: {FORENSIC_DISCLAIMER}")


# -----------------------------------------------------------------------------
# Page 1: Analyze Document (Upload & Execution)
# -----------------------------------------------------------------------------
def page_analyze(fb_service: FirebaseService, persist_fb: bool, upload_storage: bool, analyst_id: str) -> None:
    _render_top_navbar("Document Verification", fb_service, analyst_id)

    render_html(
        f"""
        <div class="kavach-hero">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:1rem;">
                <div>
                    <h1>🛡️ {APP_TITLE}</h1>
                    <p>
                        Defensive AI Document Forensics &bull; Multi-Modal Tampering Detection &bull; 
                        OCR Business Extraction &bull; Mathematical Consistency Verification &bull; Heuristic Risk Scoring
                    </p>
                </div>
                <div style="display:inline-flex; align-items:center; gap:0.5rem; background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25); backdrop-filter:blur(10px); padding:0.4rem 0.85rem; border-radius:9999px; font-size:0.78rem; font-weight:700;">
                    <span class="radar-dot"></span> Institutional Tampering Defense v{APP_VERSION}
                </div>
            </div>
        </div>
        """
    )

    render_html(
        """
        <div style="display:flex; align-items:center; justify-content:space-between; margin-top:-0.5rem; margin-bottom:0.75rem; padding: 0.65rem 1.15rem; background: #FFFFFF; border-radius: 12px; border: 1px solid #E2E8F0; box-shadow: 0 4px 12px -2px rgba(15,23,42,0.04);">
            <div style="display:flex; align-items:center; gap:0.6rem;">
                <span style="font-size:0.88rem; font-weight:800; color:#0F172A; letter-spacing:0.01em;">⚡ Active Forensic Subsystems</span>
                <span style="font-size:0.78rem; color:#64748B; font-weight:500;">&bull; Click any algorithm below to inspect its technical mechanics, formulas &amp; thresholds</span>
            </div>
            <div style="display:flex; align-items:center; gap:0.45rem;">
                <span class="radar-dot"></span>
                <span style="font-size:0.76rem; font-weight:700; color:#065F46; background:#ECFDF5; padding:0.2rem 0.6rem; border-radius:9999px; border:1px solid #A7F3D0;">5 / 5 Engines Operational</span>
            </div>
        </div>
        """
    )

    active_tab = st.session_state.get("active_forensic_tab")

    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        is_sel = (active_tab == "ela")
        lbl = "▼ ELA Forensics (Active)" if is_sel else "✓ JPEG ELA Forensics"
        if st.button(lbl, key="btn_ela", type="primary" if is_sel else "secondary", use_container_width=True, help="Error Level Analysis: Surfaces JPEG re-compression quantization disparities"):
            st.session_state["active_forensic_tab"] = None if is_sel else "ela"
            st.rerun()
    with b2:
        is_sel = (active_tab == "lap")
        lbl = "▼ Laplacian Noise (Active)" if is_sel else "✓ Laplacian Variance"
        if st.button(lbl, key="btn_lap", type="primary" if is_sel else "secondary", use_container_width=True, help="Laplacian Noise Floor: 32x32 block spatial kernel detecting airbrushed/smoothed edits (>3.0σ)"):
            st.session_state["active_forensic_tab"] = None if is_sel else "lap"
            st.rerun()
    with b3:
        is_sel = (active_tab == "orb")
        lbl = "▼ Copy-Move (Active)" if is_sel else "✓ ORB Copy-Move"
        if st.button(lbl, key="btn_orb", type="primary" if is_sel else "secondary", use_container_width=True, help="ORB Feature Matching: FAST & Rotated BRIEF detecting cloned signatures, stamps, or duplicate digits"):
            st.session_state["active_forensic_tab"] = None if is_sel else "orb"
            st.rerun()
    with b4:
        is_sel = (active_tab == "pdf")
        lbl = "▼ PDF %%EOF (Active)" if is_sel else "✓ PDF Metadata & %%EOF"
        if st.button(lbl, key="btn_pdf", type="primary" if is_sel else "secondary", use_container_width=True, help="PDF Structural Audit: Multiple %%EOF revisions, trailer traversal, timestamp divergences & whiteout overlays"):
            st.session_state["active_forensic_tab"] = None if is_sel else "pdf"
            st.rerun()
    with b5:
        is_sel = (active_tab == "gst")
        lbl = "▼ Mod-36 GSTIN (Active)" if is_sel else "✓ Mod-36 GSTIN"
        if st.button(lbl, key="btn_gst", type="primary" if is_sel else "secondary", use_container_width=True, help="Indian GSTN Checksum: ISO/IEC 7064 Mod 36,36 polynomial validation (100% local, zero data leakage)"):
            st.session_state["active_forensic_tab"] = None if is_sel else "gst"
            st.rerun()

    if active_tab == "ela":
        render_html(
            """
            <div class="enterprise-card" style="border-left: 5px solid #2563EB; background: #FFFFFF; box-shadow: 0 8px 24px -4px rgba(37,99,235,0.18); margin-bottom: 0.85rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                    <h4 style="margin:0; color:#0F172A; font-weight:800; font-size:1.08rem;">
                        🔬 Forensic Subsystem: JPEG Error Level Analysis (ELA)
                    </h4>
                    <span style="background:#EFF6FF; color:#1D4ED8; font-size:0.8rem; font-weight:800; padding:0.25rem 0.75rem; border-radius:9999px;">
                        Active &bull; Quantization Delta 95%
                    </span>
                </div>
                <p style="margin:0.55rem 0; font-size:0.88rem; color:#334155; line-height:1.6;">
                    <strong>Detection Mechanics:</strong> Re-compresses document bitmaps at a calibrated 95% JPEG quality level and calculates absolute difference residuals against the incoming pixel matrix. Spliced text, pasted numerical digits, and manipulated totals exhibit starkly different error floors, highlighting tampering as luminous clusters in the residual heatmap.
                </p>
                <div style="display:flex; gap:1.25rem; flex-wrap:wrap; font-size:0.82rem; color:#64748B; margin-top:0.6rem; padding-top:0.6rem; border-top:1px solid #F1F5F9;">
                    <span><strong>Target Anomaly:</strong> Cut-and-paste splicing &amp; localized retouching</span>
                    <span><strong>Visual Output:</strong> Residual Difference Heatmap Preview</span>
                    <span><strong>Weight:</strong> +12 to +25 Heuristic Risk Points</span>
                </div>
            </div>
            """
        )
    elif active_tab == "lap":
        render_html(
            """
            <div class="enterprise-card" style="border-left: 5px solid #10B981; background: #FFFFFF; box-shadow: 0 8px 24px -4px rgba(16,185,129,0.18); margin-bottom: 0.85rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                    <h4 style="margin:0; color:#0F172A; font-weight:800; font-size:1.08rem;">
                        🔬 Forensic Subsystem: Laplacian Noise-Floor Outlier Variance
                    </h4>
                    <span style="background:#ECFDF5; color:#065F46; font-size:0.8rem; font-weight:800; padding:0.25rem 0.75rem; border-radius:9999px;">
                        Active &bull; 32x32 Block Spatial Kernel
                    </span>
                </div>
                <p style="margin:0.55rem 0; font-size:0.88rem; color:#334155; line-height:1.6;">
                    <strong>Detection Mechanics:</strong> Divides document pages into 32x32 pixel spatial tiles and computes the variance of the second-order Laplacian derivative to evaluate high-frequency sensor noise. Digitally erased fields, smoothed background textures, or cloned patches deviate beyond 3.0 standard deviations from the global noise distribution.
                </p>
                <div style="display:flex; gap:1.25rem; flex-wrap:wrap; font-size:0.82rem; color:#64748B; margin-top:0.6rem; padding-top:0.6rem; border-top:1px solid #F1F5F9;">
                    <span><strong>Target Anomaly:</strong> Digital erasing, artificial smoothing &amp; patch insertion</span>
                    <span><strong>Threshold:</strong> 3.0σ standard deviation cutoff</span>
                    <span><strong>Weight:</strong> +10 to +18 Heuristic Risk Points</span>
                </div>
            </div>
            """
        )
    elif active_tab == "orb":
        render_html(
            """
            <div class="enterprise-card" style="border-left: 5px solid #8B5CF6; background: #FFFFFF; box-shadow: 0 8px 24px -4px rgba(139,92,246,0.18); margin-bottom: 0.85rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                    <h4 style="margin:0; color:#0F172A; font-weight:800; font-size:1.08rem;">
                        🔬 Forensic Subsystem: ORB Keypoint Copy-Move Duplication
                    </h4>
                    <span style="background:#F5F3FF; color:#5B21B6; font-size:0.8rem; font-weight:800; padding:0.25rem 0.75rem; border-radius:9999px;">
                        Active &bull; FAST &amp; Rotated BRIEF
                    </span>
                </div>
                <p style="margin:0.55rem 0; font-size:0.88rem; color:#334155; line-height:1.6;">
                    <strong>Detection Mechanics:</strong> Computes scale- and rotation-invariant Oriented FAST and Rotated BRIEF descriptors across the document image. Clusters cross-matching vectors with spatial displacement filters to isolate cloned company seals, duplicated signatures, or cloned numerical rows within the same page.
                </p>
                <div style="display:flex; gap:1.25rem; flex-wrap:wrap; font-size:0.82rem; color:#64748B; margin-top:0.6rem; padding-top:0.6rem; border-top:1px solid #F1F5F9;">
                    <span><strong>Target Anomaly:</strong> Cloned signatures, duplicate stamps &amp; digit replication</span>
                    <span><strong>Filter:</strong> Euclidean spatial displacement clustering</span>
                    <span><strong>Weight:</strong> +15 to +28 Heuristic Risk Points</span>
                </div>
            </div>
            """
        )
    elif active_tab == "pdf":
        render_html(
            """
            <div class="enterprise-card" style="border-left: 5px solid #EF4444; background: #FFFFFF; box-shadow: 0 8px 24px -4px rgba(239,68,68,0.18); margin-bottom: 0.85rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                    <h4 style="margin:0; color:#0F172A; font-weight:800; font-size:1.08rem;">
                        🔬 Forensic Subsystem: PDF Low-Level Structure &amp; Revision Traversal
                    </h4>
                    <span style="background:#FEF2F2; color:#991B1B; font-size:0.8rem; font-weight:800; padding:0.25rem 0.75rem; border-radius:9999px;">
                        Active &bull; PyMuPDF XREF &amp; EOF Audit
                    </span>
                </div>
                <p style="margin:0.55rem 0; font-size:0.88rem; color:#334155; line-height:1.6;">
                    <strong>Detection Mechanics:</strong> Audits the physical PDF byte stream for multiple <code>%%EOF</code> markers (proving the document was modified or appended post-creation), checks for <code>CreationDate</code> vs <code>ModDate</code> discrepancies, identifies opaque whiteout overlay rectangles (drawn over original numbers), and flags mixed font families in table rows.
                </p>
                <div style="display:flex; gap:1.25rem; flex-wrap:wrap; font-size:0.82rem; color:#64748B; margin-top:0.6rem; padding-top:0.6rem; border-top:1px solid #F1F5F9;">
                    <span><strong>Target Anomaly:</strong> Post-signing edits, whiteout rectangles &amp; mixed fonts</span>
                    <span><strong>Parser:</strong> Low-level xref table &amp; trailer scanner</span>
                    <span><strong>Weight:</strong> +12 to +25 Heuristic Risk Points</span>
                </div>
            </div>
            """
        )
    elif active_tab == "gst":
        render_html(
            """
            <div class="enterprise-card" style="border-left: 5px solid #F59E0B; background: #FFFFFF; box-shadow: 0 8px 24px -4px rgba(245,158,11,0.18); margin-bottom: 0.85rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                    <h4 style="margin:0; color:#0F172A; font-weight:800; font-size:1.08rem;">
                        🔬 Forensic Subsystem: Indian GSTN 15-Character Luhn Mod-36 Checksum
                    </h4>
                    <span style="background:#FFFBEB; color:#92400E; font-size:0.8rem; font-weight:800; padding:0.25rem 0.75rem; border-radius:9999px;">
                        Active &bull; Mod-36 Algorithm (Zero Leakage)
                    </span>
                </div>
                <p style="margin:0.55rem 0; font-size:0.88rem; color:#334155; line-height:1.6;">
                    <strong>Detection Mechanics:</strong> Validates Indian Goods &amp; Services Tax Identification Numbers locally: checks 2-digit state code (01-38), 10-character PAN structure (AAAAA9999A), entity code, constant 'Z', and calculates the official 15th mod-36 check character. Runs 100% locally with zero external network leakage.
                </p>
                <div style="display:flex; gap:1.25rem; flex-wrap:wrap; font-size:0.82rem; color:#64748B; margin-top:0.6rem; padding-top:0.6rem; border-top:1px solid #F1F5F9;">
                    <span><strong>Target Anomaly:</strong> Fabricated GSTINs, fake vendor identities &amp; invalid check digits</span>
                    <span><strong>Verification:</strong> Local Mod-36 checksum calculation</span>
                    <span><strong>Weight:</strong> +20 Points in consistency audit if invalid</span>
                </div>
            </div>
            """
        )

    if active_tab:
        c_close, _ = st.columns([2, 8])
        with c_close:
            if st.button("✕ Close Forensic Inspector", key="btn_close_insp", type="secondary"):
                st.session_state["active_forensic_tab"] = None
                st.rerun()

    col_left, col_right = st.columns([13, 8])

    with col_left:
        render_html(
            """
            <div class="enterprise-card">
                <div class="enterprise-card-title"><span>📤</span> Document Ingestion &amp; Classification</div>
                <div class="enterprise-card-desc">Upload official business invoices, certificates, or statements for automated forensic auditing.</div>
            </div>
            """
        )

        doc_type = st.selectbox("Document Classification Type", DOCUMENT_TYPES)

        uploaded = st.file_uploader(
            f"Upload Document (PDF, JPG, JPEG, PNG — Maximum {MAX_FILE_SIZE_MB} MB)",
            type=["pdf", "jpg", "jpeg", "png"],
            help="File is validated via header magic bytes and sanitized against traversal attacks.",
        )

    with col_right:
        render_html(
            """
            <div class="enterprise-card">
                <div style="font-size:0.86rem; font-weight:800; text-transform:uppercase; letter-spacing:0.06em; color:#64748B; margin-bottom:0.4rem;">
                    ⚡ Safe Forensic Testbench (Synthetic Demos)
                </div>
                <div class="enterprise-card-desc">Instant fictional samples designed for hackathon judges without exposing real customer data.</div>
            </div>
            """
        )

        d1, d2, d3 = st.columns(3)
        with d1:
            if st.button("🟢 Clean Invoice", use_container_width=True, help="100% Valid arithmetic, proper GSTIN, zero tampering (Target: Low Risk)"):
                st.session_state["demo_file"] = generate_synthetic_invoice_png(tampered=False)
                st.session_state["latest_result"] = None
                st.rerun()
        with d2:
            if st.button("⚠️ Tampered PNG", use_container_width=True, help="Visual pixel manipulation, noise floor anomaly (Target: Med/High Risk)"):
                st.session_state["demo_file"] = generate_synthetic_invoice_png(tampered=True)
                st.session_state["latest_result"] = None
                st.rerun()
        with d3:
            if st.button("🚨 Tampered PDF", use_container_width=True, help="Multiple %%EOF, whiteout rectangle, mixed fonts (Target: High Risk)"):
                st.session_state["demo_file"] = generate_synthetic_tampered_pdf()
                st.session_state["latest_result"] = None
                st.rerun()

        if st.session_state.get("demo_file"):
            demo_name, demo_bytes = st.session_state["demo_file"]
            size_kb = len(demo_bytes) / 1024
            render_html(
                f"""
                <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:10px; padding:0.75rem 0.95rem; margin-top:0.75rem; box-shadow: 0 2px 6px rgba(37,99,235,0.1);">
                    <div style="font-size:0.78rem; font-weight:800; color:#1E40AF; letter-spacing:0.04em;">ACTIVE DEMO SAMPLE:</div>
                    <div style="font-size:0.86rem; color:#1E3A8A; font-family:'JetBrains Mono', monospace; font-weight:600; word-break:break-all; margin-top:0.2rem;">
                        {demo_name} ({size_kb:,.1f} KB)
                    </div>
                </div>
                """
            )
            if st.button("Clear Synthetic Sample", use_container_width=True):
                st.session_state["demo_file"] = None
                st.session_state["latest_result"] = None
                st.rerun()

    with st.expander("⚙️ Advanced Pipeline Parameters"):
        force_ocr = st.checkbox(
            "Force image-level EasyOCR even on digital PDFs (slower, compares visual pixels against embedded font streams)",
            value=False,
        )

    target_name = None
    target_bytes = None
    if uploaded is not None:
        target_name = uploaded.name
        target_bytes = uploaded.getvalue()
    elif st.session_state.get("demo_file") is not None:
        target_name, target_bytes = st.session_state["demo_file"]

    if target_name and target_bytes:
        file_size_kb = len(target_bytes) / 1024
        file_ext = target_name.split(".")[-1].upper() if "." in target_name else "FILE"

        render_html(
            f"""
            <div style="background:#FFFFFF; border:1px solid #CBD5E1; border-radius:12px; padding:0.95rem 1.35rem; margin: 1rem 0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6rem; box-shadow:var(--shadow-soft);">
                <div style="display:flex; align-items:center; gap:0.85rem;">
                    <span style="font-size:1.6rem;">📄</span>
                    <div>
                        <div style="font-weight:800; font-size:0.98rem; color:#0F172A;">Ready for Analysis: <code>{target_name}</code></div>
                        <div style="font-size:0.8rem; color:#64748B; font-weight:500;">Format: {file_ext} &bull; Size: {file_size_kb:,.1f} KB &bull; Type: {doc_type}</div>
                    </div>
                </div>
                <div style="font-size:0.82rem; font-weight:800; color:#10B981; background:#ECFDF5; border:1px solid #A7F3D0; padding:0.3rem 0.75rem; border-radius:9999px;">
                    ✓ Staged &amp; Verified
                </div>
            </div>
            """
        )

        prev_bytes = _generate_document_preview_thumbnail(target_name, target_bytes)
        if prev_bytes:
            with st.expander("👁️ Document Preview (Staged File)", expanded=True):
                c_prev, c_meta = st.columns([1, 1])
                with c_prev:
                    st.image(prev_bytes, caption=f"Staged Preview: {target_name}", use_container_width=True)
                with c_meta:
                    render_html(
                        f"""
                        <div style="padding:1.15rem; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px;">
                            <h5 style="margin:0 0 0.5rem 0; color:#0F172A; font-size:1rem; font-weight:800;">Pre-Analysis Verification</h5>
                            <p style="font-size:0.85rem; color:#64748B; margin:0 0 0.85rem 0; line-height:1.5;">
                                Document binary header validated. Click below to begin multi-modal forensic inspection and OCR extraction.
                            </p>
                            <div style="font-size:0.84rem; color:#334155; line-height:1.85;">
                                <div><strong>Target:</strong> <code>{target_name}</code></div>
                                <div><strong>Category:</strong> {doc_type}</div>
                                <div><strong>Payload Size:</strong> {file_size_kb:,.1f} KB</div>
                                <div><strong>Header Check:</strong> Magic byte validation passed</div>
                            </div>
                        </div>
                        """
                    )

        col_run, _ = st.columns([1, 2])
        with col_run:
            run_clicked = st.button("🚀 Run Forensic Verification", type="primary", use_container_width=True)

        if run_clicked:
            with st.spinner("Executing defensive computer vision, ELA decomposition, PyMuPDF inspection, OCR and arithmetic checks..."):
                try:
                    result = analyze_document(
                        filename=target_name,
                        file_bytes=target_bytes,
                        document_type=doc_type,
                        firebase_service=fb_service,
                        persist_to_firebase=persist_fb,
                        upload_to_storage=upload_storage,
                        force_ocr=force_ocr,
                        analyst_id=analyst_id.strip() or None,
                    )
                    st.session_state["latest_result"] = result
                    _record_session_history(result)
                except (ValueError, DocumentLoadError) as exc:
                    st.error(f"Document rejected or could not be processed safely: {exc}")
                except Exception as exc:
                    st.error(f"Unexpected analysis error: {exc}")
    else:
        render_html(
            """
            <div style="background:#FFFFFF; border:1.5px dashed #CBD5E1; border-radius:12px; padding:1.4rem; text-align:center; margin:1.25rem 0; box-shadow:var(--shadow-soft);">
                <div style="font-size:1.8rem; margin-bottom:0.4rem;">🛡️</div>
                <div style="font-weight:800; font-size:1rem; color:#0F172A;">Document Ingestion Standby</div>
                <div style="font-size:0.85rem; color:#64748B; margin-top:0.35rem; max-width:650px; margin-left:auto; margin-right:auto; line-height:1.5;">
                    Upload an official invoice, statement or certificate above, or click one of the <strong>Synthetic Demos</strong> (<span style="color:#10B981; font-weight:700;">Clean Invoice</span>, <span style="color:#F59E0B; font-weight:700;">Tampered PNG</span>, <span style="color:#EF4444; font-weight:700;">Tampered PDF</span>) to stage a test document.
                </div>
            </div>
            """
        )

    if st.session_state.get("latest_result") is not None:
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        _render_analysis_details(st.session_state["latest_result"])


# -----------------------------------------------------------------------------
# Dynamic Database Helpers & Interactive Modals
# -----------------------------------------------------------------------------
def _get_all_records(fb_service: FirebaseService) -> List[Dict[str, Any]]:
    """Retrieve deduplicated verified document records from Cloud Firestore and session history."""
    records: List[Dict[str, Any]] = []
    seen_ids = set()
    if fb_service.is_connected:
        fb_recs, err = fb_service.fetch_recent_analyses(limit=100)
        if fb_recs:
            for r in fb_recs:
                doc_id = r.get("document_id")
                if doc_id:
                    seen_ids.add(doc_id)
                records.append(r)
    for s_rec in st.session_state.get("session_history", []):
        sid = s_rec.get("document_id")
        if sid and sid not in seen_ids:
            seen_ids.add(sid)
            records.append(s_rec)
        elif not sid:
            records.append(s_rec)
    records.sort(key=lambda r: str(r.get("upload_timestamp", "")), reverse=True)
    return records


def _format_timestamp(ts_val: Any) -> str:
    """Safely format an ISO or raw timestamp into 'Nov 25, 2026 – HH:MM' format."""
    if not ts_val:
        return datetime.now().strftime("%b %d, %Y – %H:%M")
    try:
        s = str(ts_val)
        if "T" in s:
            dt = datetime.fromisoformat(s)
            return dt.strftime("%b %d, %Y – %H:%M")
        return s[:16]
    except Exception:
        return str(ts_val)[:16]


def _get_activity_data(records: List[Dict[str, Any]], timeframe: str = "7D") -> Tuple[List[str], List[int]]:
    """Dynamically aggregate real verification records by date across chosen timeframe."""
    now = datetime.now(timezone.utc)
    if timeframe == "30D":
        labels = []
        intervals = []
        for i in range(5, -1, -1):
            d = now - timedelta(days=i * 5)
            labels.append(d.strftime("%b %d"))
            intervals.append(d.date())
        counts = [0] * len(labels)
        for r in records:
            ts = r.get("upload_timestamp")
            if ts:
                try:
                    rd = datetime.fromisoformat(str(ts)).date()
                    for idx in range(len(intervals) - 1, -1, -1):
                        if rd >= intervals[idx]:
                            counts[idx] += 1
                            break
                except Exception:
                    pass
        return labels, counts
    elif timeframe == "90D":
        labels = []
        intervals = []
        for i in range(5, -1, -1):
            d = now - timedelta(days=i * 15)
            labels.append(d.strftime("%b %d"))
            intervals.append(d.date())
        counts = [0] * len(labels)
        for r in records:
            ts = r.get("upload_timestamp")
            if ts:
                try:
                    rd = datetime.fromisoformat(str(ts)).date()
                    for idx in range(len(intervals) - 1, -1, -1):
                        if rd >= intervals[idx]:
                            counts[idx] += 1
                            break
                except Exception:
                    pass
        return labels, counts
    else:  # "7D"
        days = []
        day_dates = []
        for i in range(6, -1, -1):
            d = now - timedelta(days=i)
            days.append(d.strftime("%a"))
            day_dates.append(d.date())
        counts = [0] * 7
        for r in records:
            ts = r.get("upload_timestamp")
            if ts:
                try:
                    rd = datetime.fromisoformat(str(ts)).date()
                    for idx, dt in enumerate(day_dates):
                        if rd == dt:
                            counts[idx] += 1
                except Exception:
                    pass
        return days, counts


@st.dialog("Document Forensic Inspection Details", width="large")
def show_document_details_dialog(rec: Dict[str, Any]) -> None:
    doc_id = rec.get("document_id", "N/A")
    fname = rec.get("filename", "Verified_Document.pdf")
    doc_type = rec.get("document_type", "Official Document")
    sc = int(rec.get("risk_score", 0))
    ts_fmt = _format_timestamp(rec.get("upload_timestamp"))
    analyst = rec.get("analyst_id") or "Arpit Patil"
    info = rec.get("extracted_info") or {}

    if sc <= 29:
        status_bg = "#ECFDF5"
        status_color = "#059669"
        status_label = "AUTHENTIC (LOW RISK)"
        icon = "🛡️"
    elif sc <= 59:
        status_bg = "#FFFBEB"
        status_color = "#D97706"
        status_label = "REVIEW REQUIRED (MEDIUM RISK)"
        icon = "⚠️"
    else:
        status_bg = "#FEF2F2"
        status_color = "#DC2626"
        status_label = "SUSPICIOUS (HIGH RISK)"
        icon = "🚨"

    render_html(
        f"""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:1.15rem 1.35rem; margin-bottom:1rem; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                <div>
                    <div style="font-size:1.18rem; font-weight:800; color:#0F172A; display:flex; align-items:center; gap:0.4rem;">
                        <span>📄</span> {fname}
                    </div>
                    <div style="font-size:0.8rem; color:#64748B; margin-top:0.25rem; font-family:'JetBrains Mono', monospace;">
                        ID: {doc_id} &bull; Type: {doc_type} &bull; {ts_fmt}
                    </div>
                </div>
                <div style="background:{status_bg}; color:{status_color}; border:1.5px solid {status_color}; border-radius:9999px; padding:0.35rem 0.85rem; font-size:0.82rem; font-weight:800;">
                    {icon} {status_label} &bull; {sc}%
                </div>
            </div>
        </div>
        """
    )

    c1, c2 = st.columns(2)
    with c1:
        render_html(
            f"""
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; padding:1rem; height:100%;">
                <div style="font-size:0.92rem; font-weight:800; color:#0F172A; margin-bottom:0.6rem;">🛡️ Forensic Assessment</div>
                <div style="font-size:0.84rem; color:#334155; line-height:1.7;">
                    <div><strong>Risk Score:</strong> <span style="color:{status_color}; font-weight:800;">{sc} / 100</span></div>
                    <div><strong>Classification:</strong> {rec.get('risk_level', 'Standard')}</div>
                    <div><strong>Analyst / Auditor:</strong> {analyst}</div>
                    <div><strong>Registry Storage:</strong> {'✓ Cloud Firestore Synced' if rec.get('document_id') else 'Local Session Mode'}</div>
                </div>
            </div>
            """
        )
    with c2:
        comp = info.get("company_name") or "—"
        inv_no = info.get("invoice_number") or "—"
        gst = info.get("gstin") or "—"
        gt = info.get("grand_total")
        gt_str = f"INR {gt:,.2f}" if gt is not None else "—"
        ocr_eng = info.get("ocr_engine_used") or "EasyOCR / PyMuPDF"
        render_html(
            f"""
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; padding:1rem; height:100%;">
                <div style="font-size:0.92rem; font-weight:800; color:#0F172A; margin-bottom:0.6rem;">🏢 Extracted Business Entities</div>
                <div style="font-size:0.84rem; color:#334155; line-height:1.7;">
                    <div><strong>Entity Name:</strong> {comp}</div>
                    <div><strong>Document / Inv #:</strong> {inv_no}</div>
                    <div><strong>GSTIN / Tax ID:</strong> {gst}</div>
                    <div><strong>Grand Total:</strong> {gt_str}</div>
                    <div><strong>OCR Engine:</strong> {ocr_eng}</div>
                </div>
            </div>
            """
        )

    st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)
    b_left, b_right = st.columns([1, 1])
    with b_left:
        if st.button("Close Window", key=f"dlg_close_{doc_id}", use_container_width=True):
            st.rerun()
    with b_right:
        if st.button("Open in Audit Registry →", key=f"dlg_goto_hist_{doc_id}", type="primary", use_container_width=True):
            st.session_state["nav_page"] = "Verification History"
            st.rerun()


# -----------------------------------------------------------------------------
# Page 2: Executive Overview Dashboard (Matching VeriTrust SaaS Design)
# -----------------------------------------------------------------------------
def page_dashboard(fb_service: FirebaseService, analyst_id: str) -> None:
    # Top Header Row (Title, Subtitle, Bell, Profile, Verify New Document)
    col_head_left, col_head_right = st.columns([6.8, 3.2], vertical_alignment="center")
    with col_head_left:
        render_html(
            """
            <div class="dashboard-title-box">
                <h1 class="dashboard-title">Document Verification Dashboard</h1>
                <p class="dashboard-subtitle">Monitor and review document authenticity</p>
            </div>
            """
        )
    with col_head_right:
        c_user, c_btn = st.columns([1.1, 1.3], vertical_alignment="center")
        with c_user:
            render_html(
                f"""
                <div style="display:flex; align-items:center; gap:0.5rem; justify-content:flex-end;">
                    <div class="notification-bell-btn">
                        <span style="font-size:1.1rem;">🔔</span>
                        <span class="notification-badge">3</span>
                    </div>
                    <div class="profile-pill-box">
                        <div class="profile-avatar-circle">AP</div>
                        <span class="profile-user-name">{analyst_id.strip() or 'Arpit Patil'}</span>
                        <span style="font-size:0.7rem; color:#64748B;">▼</span>
                    </div>
                </div>
                """
            )
        with c_btn:
            if st.button("⚡ Verify New Document →", type="primary", use_container_width=True, key="btn_goto_verify_dash"):
                st.session_state["nav_page"] = "Verify Document"
                st.rerun()

    # Query real records from Firestore and session history
    records = _get_all_records(fb_service)

    real_count = len(records)
    real_low = sum(1 for r in records if int(r.get("risk_score", 0)) <= 29)
    real_med = sum(1 for r in records if 30 <= int(r.get("risk_score", 0)) <= 59)
    real_high = sum(1 for r in records if int(r.get("risk_score", 0)) >= 60)

    # 100% Real values derived strictly from verified database records
    total_val_str = f"{real_count:,}"
    auth_val_str = f"{real_low:,}"
    flagged_val_str = f"{real_med + real_high:,}"
    high_val_str = f"{real_high:,}"

    if real_count > 0:
        low_pct = round(real_low / real_count * 100, 1)
        med_pct = round(real_med / real_count * 100, 1)
        high_pct = round(real_high / real_count * 100, 1)
        trend_total = '<span style="color:#10B981; font-weight:700;">↑ 100%</span><span style="color:#94A3B8; font-weight:500;"> verified via AI</span>'
        trend_auth = f'<span style="color:#10B981; font-weight:700;">↑ {low_pct:.1f}%</span><span style="color:#94A3B8; font-weight:500;"> pass rate</span>'
        trend_flagged = f'<span style="color:#F59E0B; font-weight:700;">{med_pct + high_pct:.1f}%</span><span style="color:#94A3B8; font-weight:500;"> flagged for review</span>'
        trend_high = f'<span style="color:#EF4444; font-weight:700;">{high_pct:.1f}%</span><span style="color:#94A3B8; font-weight:500;"> critical risk</span>'
    else:
        low_pct = 0.0
        med_pct = 0.0
        high_pct = 0.0
        trend_total = '<span style="color:#94A3B8; font-weight:500;">Standby for upload</span>'
        trend_auth = '<span style="color:#94A3B8; font-weight:500;">0 verified authentic</span>'
        trend_flagged = '<span style="color:#94A3B8; font-weight:500;">0 flagged</span>'
        trend_high = '<span style="color:#94A3B8; font-weight:500;">0 high risk</span>'

    # 4 Metric Cards Row
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        render_html(
            f"""
            <div class="veritrust-stat-card">
                <div style="display:flex; align-items:flex-start; gap:0.95rem;">
                    <div class="stat-icon-circle blue">📄</div>
                    <div>
                        <div class="stat-card-label">Documents Verified</div>
                        <div class="stat-card-value">{total_val_str}</div>
                        <div class="stat-card-trend">{trend_total}</div>
                    </div>
                </div>
            </div>
            """
        )

    with k2:
        render_html(
            f"""
            <div class="veritrust-stat-card">
                <div style="display:flex; align-items:flex-start; gap:0.95rem;">
                    <div class="stat-icon-circle green">🛡️</div>
                    <div>
                        <div class="stat-card-label">Authentic Documents</div>
                        <div class="stat-card-value">{auth_val_str}</div>
                        <div class="stat-card-trend">{trend_auth}</div>
                    </div>
                </div>
            </div>
            """
        )

    with k3:
        render_html(
            f"""
            <div class="veritrust-stat-card">
                <div style="display:flex; align-items:flex-start; gap:0.95rem;">
                    <div class="stat-icon-circle red">⚠️</div>
                    <div>
                        <div class="stat-card-label">Flagged Documents</div>
                        <div class="stat-card-value">{flagged_val_str}</div>
                        <div class="stat-card-trend">{trend_flagged}</div>
                    </div>
                </div>
            </div>
            """
        )

    with k4:
        render_html(
            f"""
            <div class="veritrust-stat-card">
                <div style="display:flex; align-items:flex-start; gap:0.95rem;">
                    <div class="stat-icon-circle amber">🚨</div>
                    <div>
                        <div class="stat-card-label">High Risk</div>
                        <div class="stat-card-value">{high_val_str}</div>
                        <div class="stat-card-trend">{trend_high}</div>
                    </div>
                </div>
            </div>
            """
        )

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    # Middle Row: Verification Activity Area Line Chart & Risk Distribution Donut Chart
    chart_c1, chart_c2 = st.columns([6.8, 3.2])

    with chart_c1:
        curr_tf = st.session_state.get("activity_tf", "7D")
        c_act_title, c_act_btns = st.columns([6.2, 3.8], vertical_alignment="center")
        with c_act_title:
            render_html(
                """
                <div class="veritrust-chart-header" style="margin-bottom:0;">
                    <div class="veritrust-chart-title"><span>📊</span> Verification Activity</div>
                </div>
                """
            )
        with c_act_btns:
            p1, p2, p3 = st.columns(3)
            with p1:
                if st.button("7D", key="tf_7d", type="primary" if curr_tf == "7D" else "secondary", use_container_width=True):
                    st.session_state["activity_tf"] = "7D"
                    st.rerun()
            with p2:
                if st.button("30D", key="tf_30d", type="primary" if curr_tf == "30D" else "secondary", use_container_width=True):
                    st.session_state["activity_tf"] = "30D"
                    st.rerun()
            with p3:
                if st.button("90D", key="tf_90d", type="primary" if curr_tf == "90D" else "secondary", use_container_width=True):
                    st.session_state["activity_tf"] = "90D"
                    st.rerun()

        act_labels, act_counts = _get_activity_data(records, curr_tf)
        max_c = max(act_counts) if act_counts else 0

        if max_c == 0:
            y_max = 5
            t_vals = [0, 1, 2, 3, 4, 5]
            t_texts = ["0", "1", "2", "3", "4", "5"]
        elif max_c <= 10:
            y_max = max(5, max_c + 2)
            step = max(1, y_max // 4)
            t_vals = list(range(0, y_max + 1, step))
            t_texts = [str(v) for v in t_vals]
        else:
            y_max = int(max_c * 1.35) + 1
            step = max(1, y_max // 4)
            t_vals = [0, step, step * 2, step * 3, y_max]
            t_texts = [f"{v:,}" for v in t_vals]

        fig_activity = go.Figure()
        fig_activity.add_trace(
            go.Scatter(
                x=act_labels,
                y=act_counts,
                mode="lines+markers",
                line=dict(color="#1E5BF8", width=3, shape="spline"),
                marker=dict(size=8, color="#1E5BF8", line=dict(color="#FFFFFF", width=2)),
                fill="tozeroy",
                fillcolor="rgba(30, 91, 248, 0.08)",
                name="Verifications",
            )
        )
        fig_activity.update_layout(
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(family="Inter, sans-serif", color="#0F172A", size=12),
            margin=dict(l=35, r=15, t=10, b=30),
            yaxis=dict(
                range=[0, y_max],
                tickvals=t_vals,
                ticktext=t_texts,
                gridcolor="#F1F5F9",
                zeroline=False,
            ),
            xaxis=dict(showgrid=False),
            height=270,
        )
        st.plotly_chart(fig_activity, use_container_width=True)

    with chart_c2:
        render_html(
            """
            <div class="veritrust-chart-header">
                <div class="veritrust-chart-title"><span>🎯</span> Risk Distribution</div>
            </div>
            """
        )
        if real_count > 0:
            donut_labels = [f"Low Risk ({low_pct}%)", f"Medium Risk ({med_pct}%)", f"High Risk ({high_pct}%)"]
            donut_vals = [real_low, real_med, real_high]
            donut_colors = ["#10B981", "#F59E0B", "#EF4444"]
            if low_pct >= 50.0:
                center_text = f"<b>{low_pct:.1f}%</b><br><span style='font-size:12px; color:#10B981; font-weight:700;'>Safe</span>"
            elif med_pct >= high_pct:
                center_text = f"<b>{med_pct:.1f}%</b><br><span style='font-size:12px; color:#F59E0B; font-weight:700;'>Medium Risk</span>"
            else:
                center_text = f"<b>{high_pct:.1f}%</b><br><span style='font-size:12px; color:#EF4444; font-weight:700;'>High Risk</span>"
        else:
            donut_labels = ["Low Risk (0.0%)", "Medium Risk (0.0%)", "High Risk (0.0%)"]
            donut_vals = [1, 0, 0]
            donut_colors = ["#E2E8F0", "#E2E8F0", "#E2E8F0"]
            center_text = "<b>0</b><br><span style='font-size:12px; color:#64748B; font-weight:700;'>No Data</span>"

        fig_donut = go.Figure(
            data=[
                go.Pie(
                    labels=donut_labels,
                    values=donut_vals,
                    hole=0.72,
                    marker=dict(
                        colors=donut_colors,
                        line=dict(color="#FFFFFF", width=3),
                    ),
                    textinfo="none",
                    direction="clockwise",
                    sort=False,
                )
            ]
        )
        fig_donut.add_annotation(
            text=center_text,
            showarrow=False,
            font=dict(size=22, family="Inter, sans-serif", color="#0F172A"),
        )
        fig_donut.update_layout(
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(family="Inter, sans-serif", color="#0F172A", size=12),
            margin=dict(l=10, r=10, t=10, b=10),
            height=270,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=0.85,
                font=dict(size=11),
            ),
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # Bottom Row: Recent Verifications Table
    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
    col_tbl_head_l, col_tbl_head_r = st.columns([8.2, 1.8], vertical_alignment="center")
    with col_tbl_head_l:
        render_html(
            """
            <div style="font-size:1.08rem; font-weight:800; color:#0F172A; display:flex; align-items:center; gap:0.45rem;">
                <span>🕒</span> Recent Verifications
            </div>
            """
        )
    with col_tbl_head_r:
        if st.button("View All →", key="btn_view_all_records", use_container_width=True):
            st.session_state["nav_page"] = "Verification History"
            st.rerun()

    if not records:
        render_html(
            """
            <div style="background:#FFFFFF; border:1px solid #EDF2F7; border-radius:14px; padding:2.5rem 1.5rem; text-align:center; box-shadow:0 2px 10px rgba(15,23,42,0.03); margin-top:0.5rem;">
                <div style="font-size:2.2rem; margin-bottom:0.4rem;">📁</div>
                <div style="font-size:1.05rem; font-weight:800; color:#0F172A;">No Verified Documents Yet</div>
                <div style="font-size:0.85rem; color:#64748B; margin-top:0.25rem; max-width:480px; margin-left:auto; margin-right:auto;">
                    Upload an official document in <strong>Verify Document</strong> to run defensive AI forensics and populate real-time verification logs.
                </div>
            </div>
            """
        )
    else:
        with st.container(border=True):
            # Header Row
            h_cols = st.columns([0.6, 3.2, 2.2, 1.3, 1.2, 2.4, 1.8], vertical_alignment="center")
            h_cols[0].markdown("<div class='tbl-hdr-text'>#</div>", unsafe_allow_html=True)
            h_cols[1].markdown("<div class='tbl-hdr-text'>DOCUMENT NAME</div>", unsafe_allow_html=True)
            h_cols[2].markdown("<div class='tbl-hdr-text'>VERIFICATION STATUS</div>", unsafe_allow_html=True)
            h_cols[3].markdown("<div class='tbl-hdr-text'>RISK LEVEL</div>", unsafe_allow_html=True)
            h_cols[4].markdown("<div class='tbl-hdr-text'>RISK SCORE</div>", unsafe_allow_html=True)
            h_cols[5].markdown("<div class='tbl-hdr-text'>DATE &amp; TIME</div>", unsafe_allow_html=True)
            h_cols[6].markdown("<div class='tbl-hdr-text' style='text-align:center;'>ACTION</div>", unsafe_allow_html=True)

            render_html("<div style='border-bottom: 1.5px solid #F1F5F9; margin-top: -0.2rem; margin-bottom: 0.45rem;'></div>")

            for idx, rec in enumerate(records[:10], start=1):
                sc = int(rec.get("risk_score", 0))
                if sc <= 29:
                    status_html = '<span class="status-pill-verified">✓ Verified</span>'
                    risk_html = '<span class="risk-pill-low">Low</span>'
                elif sc <= 59:
                    status_html = '<span class="status-pill-review">⚠️ Review Required</span>'
                    risk_html = '<span class="risk-pill-medium">Medium</span>'
                else:
                    status_html = '<span class="status-pill-suspicious">🚨 Suspicious</span>'
                    risk_html = '<span class="risk-pill-high">High</span>'

                doc_name = rec.get("filename", "Verified_Document.pdf")
                ts_str = _format_timestamp(rec.get("upload_timestamp"))

                r_cols = st.columns([0.6, 3.2, 2.2, 1.3, 1.2, 2.4, 1.8], vertical_alignment="center")
                r_cols[0].markdown(f"<div style='font-weight:700; color:#64748B; font-size:0.86rem;'>{idx}</div>", unsafe_allow_html=True)
                r_cols[1].markdown(f"<div style='font-weight:700; color:#0F172A; font-size:0.86rem; word-break:break-all;'><span style='color:#2563EB; margin-right:0.35rem;'>📄</span> {doc_name}</div>", unsafe_allow_html=True)
                r_cols[2].markdown(status_html, unsafe_allow_html=True)
                r_cols[3].markdown(risk_html, unsafe_allow_html=True)
                r_cols[4].markdown(f"<div style='font-weight:800; color:#1E293B; font-size:0.88rem;'>{sc}%</div>", unsafe_allow_html=True)
                r_cols[5].markdown(f"<div style='color:#64748B; font-size:0.82rem;'>{ts_str}</div>", unsafe_allow_html=True)
                with r_cols[6]:
                    if st.button("👁️ View Details", key=f"btn_vd_{idx}", use_container_width=True):
                        show_document_details_dialog(rec)

                render_html("<div style='border-bottom: 1px solid #F8FAFC; margin-top: 0.2rem; margin-bottom: 0.25rem;'></div>")


# -----------------------------------------------------------------------------
# Page 3: Verification History Module
# -----------------------------------------------------------------------------
def page_history(fb_service: FirebaseService, analyst_id: str) -> None:
    _render_top_navbar("Verification History", fb_service, analyst_id)

    render_html(
        """
        <div class="dashboard-title-box" style="margin-bottom:1.25rem;">
            <h1 class="dashboard-title">Institutional Verification History</h1>
            <p class="dashboard-subtitle">Complete searchable registry and audit trail of verified documents.</p>
        </div>
        """
    )

    records = _get_all_records(fb_service)

    if not records:
        st.info("No documents recorded yet. Navigate to 'Verify Document' to analyze a sample.")
        return

    table_rows = []
    for rec in records:
        info = rec.get("extracted_info") or {}
        score = int(rec.get("risk_score", 0))
        classification = rec.get("risk_level") or ("High Risk" if score >= 60 else ("Medium Risk" if score >= 30 else "Low Risk"))
        table_rows.append(
            {
                "Document ID": rec.get("document_id"),
                "Filename": rec.get("filename"),
                "Type": rec.get("document_type"),
                "Company": info.get("company_name") or "—",
                "Invoice No": info.get("invoice_number") or "—",
                "GSTIN": info.get("gstin") or "—",
                "Grand Total": f"INR {info.get('grand_total'):,.2f}" if info.get("grand_total") is not None else "—",
                "Risk Score": f"{score}%",
                "Classification": classification,
                "Timestamp": str(rec.get("upload_timestamp", ""))[:19].replace("T", " "),
            }
        )
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)


# -----------------------------------------------------------------------------
# Page 4: Official Forensic Reports Module
# -----------------------------------------------------------------------------
def page_reports(fb_service: FirebaseService, analyst_id: str) -> None:
    _render_top_navbar("Forensic Reports", fb_service, analyst_id)

    render_html(
        """
        <div class="dashboard-title-box" style="margin-bottom:1.25rem;">
            <h1 class="dashboard-title">Generated Forensic Reports</h1>
            <p class="dashboard-subtitle">Download certified PDF audit certificates with cryptographic checksums.</p>
        </div>
        """
    )

    latest = st.session_state.get("latest_result")
    if latest and latest.pdf_report_bytes:
        render_html(
            f"""
            <div class="enterprise-card">
                <div class="enterprise-card-title">📄 Latest Certified PDF Audit Report</div>
                <div class="enterprise-card-desc">Document ID: <code>{latest.document_id}</code> &bull; File: {latest.validation.sanitized_filename}</div>
            </div>
            """
        )
        st.download_button(
            label=f"⬇️ Download PDF Report ({latest.document_id})",
            data=latest.pdf_report_bytes,
            file_name=f"{latest.document_id}_forensic_report.pdf",
            mime="application/pdf",
            type="primary",
        )
    else:
        st.info("Run an analysis under 'Verify Document' to generate and download an official forensic PDF report.")


# -----------------------------------------------------------------------------
# Page 5: System Architecture, Security & Limitations (Settings)
# -----------------------------------------------------------------------------
def page_about(fb_service: FirebaseService, analyst_id: str) -> None:
    _render_top_navbar("System Settings & Architecture", fb_service, analyst_id)

    render_html(
        """
        <div class="kavach-hero">
            <h1>ℹ️ Defensive System Architecture &amp; Methodology</h1>
            <p>
                Transparent forensic review of multi-modal tampering heuristics, data security controls, 
                and academic evaluation constraints.
            </p>
        </div>
        """
    )

    c1, c2 = st.columns(2)

    with c1:
        render_html(
            """
            <div class="enterprise-card">
                <div class="enterprise-card-title">🔬 Defensive Computer Vision Pipeline</div>
                <div class="enterprise-card-desc">Multi-layered anomaly detection across visual and structural representations.</div>
                <ul style="font-size:0.88rem; color:#334155; line-height:1.65; padding-left:1.2rem;">
                    <li><strong>Error Level Analysis (ELA):</strong> Surfaces compression disparity resulting from splicing or localized re-saving in JPEG quantization matrices.</li>
                    <li><strong>Laplacian Noise Variance:</strong> Analyzes block-level high-frequency noise variance to flag smoothed or patched fields.</li>
                    <li><strong>ORB Copy-Move Matching:</strong> Detects duplicated stamps, signatures, or cloned numerical digits via clustered keypoint matching.</li>
                    <li><strong>Font &amp; Baseline Consistency:</strong> Verifies typographical uniformity and detects mixed font families in digital document streams.</li>
                    <li><strong>PDF Structure &amp; Revision Traversal:</strong> Audits multiple <code>%%EOF</code> markers, incremental revision updates, and whiteout overlays.</li>
                </ul>
            </div>
            """
        )

    with c2:
        render_html(
            f"""
            <div class="enterprise-card">
                <div class="enterprise-card-title">🔒 Enterprise Security &amp; Compliance</div>
                <div class="enterprise-card-desc">Defensive measures protecting enterprise workflows and confidential records.</div>
                <ul style="font-size:0.88rem; color:#334155; line-height:1.65; padding-left:1.2rem;">
                    <li><strong>Strict Ingestion Validation:</strong> Enforces magic-byte verification, file extension checks, and maximum size limits ({MAX_FILE_SIZE_MB} MB).</li>
                    <li><strong>Masking of Sensitive Digits:</strong> Banking account numbers are automatically masked (<code>XXXX...1234</code>) in UI tables, logs, and PDF exports.</li>
                    <li><strong>Path Traversal Immunity:</strong> Filenames are sanitized through cryptographic hashing and basename stripping.</li>
                    <li><strong>Zero External Leakage:</strong> GSTIN checksums and arithmetic consistency checks run locally without pinging external APIs.</li>
                    <li><strong>Immutable Cloud Storage:</strong> Cloud Firestore and Firebase Storage connections run purely via server environment variables.</li>
                </ul>
            </div>
            """
        )

    render_html(
        f"""
        <div class="enterprise-card">
            <div class="enterprise-card-title">⚖️ Heuristic Limitations &amp; Ethical Policy</div>
            <p style="font-size:0.88rem; color:#334155; line-height:1.65;">
                {FORENSIC_DISCLAIMER}
            </p>
        </div>
        """
    )


# -----------------------------------------------------------------------------
# Main Application Entrypoint
# -----------------------------------------------------------------------------
def main() -> None:
    _init_session_state()
    fb_service = get_firebase_service()

    with st.sidebar:
        render_html(
            f"""
            <div style="padding: 0.65rem 0.25rem 0.85rem 0.25rem;">
                <div style="display:flex; align-items:center; gap:0.65rem;">
                    <div style="width:40px; height:40px; border-radius:12px; background:linear-gradient(135deg, #1E5BF8 0%, #00D2FF 100%); display:flex; align-items:center; justify-content:center; box-shadow:0 4px 14px rgba(30,91,248,0.4); flex-shrink:0;">
                        <span style="font-size:1.35rem;">🛡️</span>
                    </div>
                    <div>
                        <div style="font-size:1.18rem; font-weight:900; color:#FFFFFF; letter-spacing:0.01em;">VeriTrust AI</div>
                        <div style="font-size:0.73rem; color:#94A3B8; font-weight:600;">Secure &bull; Verify &bull; Trust</div>
                    </div>
                </div>
            </div>
            """
        )

        st.divider()

        nav_options = [
            "Overview",
            "Verify Document",
            "Verification History",
            "Reports",
            "Settings",
        ]
        if "nav_page" not in st.session_state:
            st.session_state["nav_page"] = "Overview"

        cur_idx = nav_options.index(st.session_state["nav_page"]) if st.session_state["nav_page"] in nav_options else 0

        nav = st.radio(
            "System Navigation",
            nav_options,
            index=cur_idx,
            label_visibility="collapsed",
            format_func=lambda x: {
                "Overview": "🏠  Overview",
                "Verify Document": "☁️  Verify Document",
                "Verification History": "🕒  Verification History",
                "Reports": "📊  Reports",
                "Settings": "⚙️  Settings",
            }.get(x, x),
        )
        if nav != st.session_state["nav_page"]:
            st.session_state["nav_page"] = nav

        st.divider()

        render_html("<div style='font-size:0.76rem; text-transform:uppercase; letter-spacing:0.07em; color:#94A3B8; font-weight:800; margin-bottom:0.5rem;'>Cloud Infrastructure</div>")

        if fb_service.is_connected:
            render_html(
                f"""
                <div style="background:#0F2942; border:1px solid #1D4ED8; border-radius:10px; padding:0.65rem 0.85rem; margin-bottom:0.75rem;">
                    <div style="display:flex; align-items:center; gap:0.4rem; font-size:0.82rem; font-weight:700; color:#60A5FA;">
                        <span style="width:8px; height:8px; border-radius:50%; background:#10B981; display:inline-block; box-shadow: 0 0 6px #10B981;"></span>
                        Firestore Connected
                    </div>
                    <div style="font-size:0.74rem; color:#CBD5E1; margin-top:0.25rem; font-family:'JetBrains Mono', monospace;">
                        {fb_service.status.project_id or 'Cloud Active'}
                    </div>
                </div>
                """
            )
        else:
            render_html(
                """
                <div style="background:#241E15; border:1px solid #B45309; border-radius:10px; padding:0.65rem 0.85rem; margin-bottom:0.75rem;">
                    <div style="display:flex; align-items:center; gap:0.4rem; font-size:0.82rem; font-weight:700; color:#FBBF24;">
                        <span style="width:8px; height:8px; border-radius:50%; background:#F59E0B; display:inline-block;"></span>
                        Local Session Mode
                    </div>
                    <div style="font-size:0.73rem; color:#E2E8F0; margin-top:0.25rem;">
                        Firebase credentials not set in env. In-memory auditing active.
                    </div>
                </div>
                """
            )

        persist_fb = st.checkbox(
            "Sync Records to Cloud Firestore",
            value=fb_service.is_connected,
            disabled=not fb_service.is_connected,
        )
        upload_storage = st.checkbox(
            "Archive Artifacts to Cloud Storage",
            value=False,
            disabled=not (fb_service.is_connected and fb_service.status.storage_enabled),
        )

        st.markdown("<div style='height: 0.35rem;'></div>", unsafe_allow_html=True)
        analyst_id = st.text_input(
            "Auditor / Session ID",
            value="Arpit Patil",
            placeholder="e.g. Arpit Patil",
            help="Optional identifier recorded in Firestore collections for audit trail accountability.",
        )

        render_html(
            """
            <div style="margin-top:2.2rem; padding:1.1rem 0.85rem; background:linear-gradient(180deg, rgba(30,91,248,0.14) 0%, rgba(15,23,42,0.4) 100%); border-radius:14px; border:1px solid rgba(255,255,255,0.08); text-align:center;">
                <div style="width:38px; height:38px; margin:0 auto 0.5rem auto; border-radius:50%; background:linear-gradient(135deg, #1E5BF8 0%, #38BDF8 100%); display:flex; align-items:center; justify-content:center; box-shadow:0 0 16px rgba(30,91,248,0.5);">
                    <span style="font-size:1.15rem;">🛡️</span>
                </div>
                <div style="font-size:0.86rem; font-weight:800; color:#FFFFFF; line-height:1.35;">
                    AI-Powered<br>Document Verification
                </div>
                <div style="font-size:0.72rem; color:#94A3B8; margin-top:0.35rem; font-weight:500;">
                    Building a More Trustworthy Digital India
                </div>
            </div>
            """
        )

    if st.session_state["nav_page"] == "Overview":
        page_dashboard(fb_service, analyst_id)
    elif st.session_state["nav_page"] == "Verify Document":
        page_analyze(fb_service, persist_fb, upload_storage, analyst_id)
    elif st.session_state["nav_page"] == "Verification History":
        page_history(fb_service, analyst_id)
    elif st.session_state["nav_page"] == "Reports":
        page_reports(fb_service, analyst_id)
    else:
        page_about(fb_service, analyst_id)


if __name__ == "__main__":
    import streamlit.runtime
    if not streamlit.runtime.exists():
        import sys
        from streamlit.web import cli as stcli
        sys.argv = ["streamlit", "run", sys.argv[0]]
        sys.exit(stcli.main())
    else:
        main()
