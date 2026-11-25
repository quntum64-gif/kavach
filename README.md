# 🛡️ KAVACH – Defensive AI Document Forensics & Verification Platform

> **Defensive AI Document Forensics • Multi-Modal Tampering Detection • OCR Business Extraction • Mathematical Consistency Verification • Heuristic Risk Scoring**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38+-FF4B4B.svg)](https://streamlit.io)
[![Firebase Firestore](https://img.shields.io/badge/Firebase-Firestore-FFCA28.svg)](https://firebase.google.com)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-1.24+-green.svg)](https://pymupdf.readthedocs.io/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.9+-5C3EE8.svg)](https://opencv.org/)

---

## 📌 Executive Overview

**KAVACH** is an enterprise-grade AI-powered forensic document analysis and tamper-detection engine tailored for institutional auditing, banking statements, business invoices, and government certificates (GSTIN).

Designed with a **VeriTrust AI SaaS interface**, KAVACH unifies multi-modal computer vision heuristics, raw byte-level PDF structure traversal, OCR business extraction, and automated cross-field mathematical reconciliation into a centralized audit workflow.

---

## 🔬 Core Forensic Subsystems

1. **Error Level Analysis (ELA) Recompression Disparity**
   - Resaves images at calibrated JPEG quality levels (90-95%) and computes differential residual heatmaps to highlight non-uniform compression artifacts, pasted pixels, and clone insertions.

2. **Laplacian Noise Variance Filtering**
   - Analyzes localized sensor noise consistency using second-order spatial derivatives. Flags copy-pasted or digital text overlays inserted into scanned paper documents.

3. **ORB Keypoint Copy-Move Duplication**
   - Applies scale- and rotation-invariant Oriented FAST and Rotated BRIEF descriptors with spatial displacement clustering to isolate cloned company seals, duplicated signatures, or cloned numerical rows.

4. **PDF Low-Level Byte Stream & Revision Traversal**
   - Audits the physical PDF structure for multiple `%%EOF` markers (proving post-creation modifications), checks `CreationDate` vs `ModDate` discrepancies, flags mixed fonts, and detects whiteout overlay annotations.

5. **Mod-36 Indian GSTIN Checksum & Arithmetic Cross-Verification**
   - Verifies 15-character GSTIN checksums using the standard ISO/IEC 7064 Mod-36,37 algorithm. Cross-checks line item totals, tax slabs (CGST, SGST, IGST), and grand totals for mathematical consistency.

6. **Executive Dashboard & Real-Time Cloud Firestore Registry**
   - Real-time audit history, dynamic activity timelines (7D/30D/90D), risk distribution breakdown, and certified PDF report downloads with cryptographic checksums.

---

## 📂 Project Architecture

```plaintext
SYNAPSE19/
├── .streamlit/
│   └── config.toml           # Streamlit server & SaaS theme configurations
├── core/
│   ├── config.py             # System thresholds, constants & forensic disclaimers
│   ├── consistency_checker.py# GSTIN checksum & mathematical invoice reconciliation
│   ├── document_loader.py    # Multi-format document parser (PDF & images)
│   ├── firebase_service.py   # Cloud Firestore registry & Storage integration
│   ├── ocr_extractor.py      # EasyOCR & PyMuPDF structured entity extractor
│   ├── pipeline.py           # Unified forensic orchestrator
│   ├── report_generator.py   # Cryptographic PDF audit certificate generator
│   ├── risk_scorer.py        # Rule-weighted heuristic risk assessment engine
│   ├── sample_generator.py   # Clean & tampered synthetic document generators
│   ├── security.py           # Magic bytes validation & PII masking
│   ├── tampering_detector.py # ELA, Laplacian noise, ORB copy-move, PDF revision
│   └── visualizer.py         # Forensic bounding box & residual heatmap visualizer
├── tests/
│   └── test_kavach.py        # Automated test suite (security, GSTIN, tampering)
├── app.py                    # Main Streamlit SaaS application frontend
├── requirements.txt          # Python dependency specifications
├── run.bat                   # One-click Windows startup batch script
├── .env.example              # Environment variables template
└── .gitignore                # Security exclusions (keys, env, zips, cache)
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- Git

### 2. Clone Repository
```bash
git clone https://github.com/quntum64-gif/kavach.git
cd kavach
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Copy the example environment file and add your Cloud Firestore credentials:
```bash
cp .env.example .env
```
Edit `.env`:
```env
FIREBASE_CREDENTIALS_PATH=firebase-key.json
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
```
*(Note: If Firebase credentials are not provided, KAVACH automatically runs in Local Session Mode with in-memory caching.)*

### 5. Launch Application
On Windows:
```bash
run.bat
```
Or via command line:
```bash
python -m streamlit run app.py
```
Open **`http://localhost:8501`** in your browser.

---

## 🧪 Running Automated Tests

Run the full forensic test suite using `pytest`:
```bash
python -m pytest tests/test_kavach.py -v
```

---

## ⚖️ Academic & Forensic Disclaimer

KAVACH identifies heuristic visual, structural, and arithmetic anomalies for human review. Findings are assistive forensic indicators and rule-weighted indices, not conclusive legal proof of fraud. Local GSTIN validation evaluates syntactic formatting and Mod-36 checksums locally without querying live government GSTN databases.

---

## 📄 License
This project is developed for institutional and academic document verification defense.
