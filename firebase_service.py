"""Real Firebase Admin SDK integration for Cloud Firestore and Firebase Storage."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()


@dataclass
class FirebaseStatus:
    connected: bool
    project_id: Optional[str]
    storage_enabled: bool
    message: str


class FirebaseService:
    """Wrapper around firebase-admin Firestore & Storage initialized strictly via env vars."""

    def __init__(self) -> None:
        self._db = None
        self._bucket = None
        self.status = self._initialize()

    @property
    def is_connected(self) -> bool:
        return self.status.connected and self._db is not None

    def _initialize(self) -> FirebaseStatus:
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore, storage
        except ImportError as exc:
            return FirebaseStatus(
                connected=False,
                project_id=None,
                storage_enabled=False,
                message=f"firebase-admin package unavailable: {exc}",
            )

        sa_json_str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        sa_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip()
        bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()

        # Automatic fallback resolution for local service account keys
        if not sa_path:
            candidates = [
                "firebase-key.json",
                "firebase_credentials.json",
                "serviceAccountKey.json",
                os.path.join(os.path.dirname(__file__), "..", "firebase-key.json"),
                os.path.join(os.path.dirname(__file__), "..", "..", "firebase-key.json"),
            ]
            for cand in candidates:
                if os.path.isfile(cand):
                    sa_path = os.path.abspath(cand)
                    break
        elif not os.path.isabs(sa_path) and not os.path.isfile(sa_path):
            candidates = [
                os.path.join(os.getcwd(), sa_path),
                os.path.join(os.path.dirname(__file__), "..", sa_path),
                os.path.join(os.path.dirname(__file__), "..", "..", sa_path),
            ]
            for cand in candidates:
                if os.path.isfile(cand):
                    sa_path = os.path.abspath(cand)
                    break

        cred = None
        project_id = None

        try:
            if sa_json_str:
                info = json.loads(sa_json_str)
                project_id = info.get("project_id")
                cred = credentials.Certificate(info)
            elif sa_path and os.path.isfile(sa_path):
                with open(sa_path, "r", encoding="utf-8") as fh:
                    info = json.load(fh)
                    project_id = info.get("project_id")
                cred = credentials.Certificate(sa_path)
            else:
                return FirebaseStatus(
                    connected=False,
                    project_id=None,
                    storage_enabled=False,
                    message="Set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_CREDENTIALS_PATH to enable Cloud Firestore.",
                )

            if not firebase_admin._apps:
                options = {"storageBucket": bucket_name} if bucket_name else {}
                firebase_admin.initialize_app(cred, options=options)

            self._db = firestore.client()
            storage_ok = False
            if bucket_name:
                self._bucket = storage.bucket(bucket_name)
                storage_ok = True

            return FirebaseStatus(
                connected=True,
                project_id=project_id,
                storage_enabled=storage_ok,
                message="Connected to Firebase Cloud Firestore.",
            )
        except Exception as exc:
            self._db = None
            self._bucket = None
            return FirebaseStatus(
                connected=False,
                project_id=None,
                storage_enabled=False,
                message=f"Firebase initialization failed: {exc}",
            )

    def find_duplicate_invoices(self, invoice_number: str) -> List[Dict[str, Any]]:
        """Query Firestore 'documents' collection for matching invoice numbers."""
        if not self.is_connected or not invoice_number:
            return []
        try:
            query = (
                self._db.collection("documents")
                .where("extracted_info.invoice_number", "==", invoice_number)
                .limit(5)
            )
            return [doc.to_dict() for doc in query.stream()]
        except Exception:
            return []

    def persist_analysis(
        self,
        document_id: str,
        doc_record: Dict[str, Any],
        analysis_record: Dict[str, Any],
        analyst_id: Optional[str] = None,
        upload_artifacts: bool = False,
        raw_bytes: Optional[bytes] = None,
        raw_filename: Optional[str] = None,
        pdf_report_bytes: Optional[bytes] = None,
    ) -> Tuple[bool, str]:
        """Save analysis records to Firestore collections ('documents', 'analysis_results', 'users')."""
        if not self.is_connected:
            return False, "Firebase not configured; saved in local browser session only."

        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            storage_urls: Dict[str, str] = {}

            if upload_artifacts and self._bucket is not None:
                if raw_bytes and raw_filename:
                    blob_in = self._bucket.blob(f"kavach/uploads/{document_id}/{raw_filename}")
                    blob_in.upload_from_string(raw_bytes)
                    storage_urls["uploaded_document_path"] = blob_in.name
                if pdf_report_bytes:
                    blob_rep = self._bucket.blob(f"kavach/reports/{document_id}_kavach_report.pdf")
                    blob_rep.upload_from_string(pdf_report_bytes, content_type="application/pdf")
                    storage_urls["forensic_report_path"] = blob_rep.name

            doc_payload = {
                **doc_record,
                "analyst_id": analyst_id,
                "storage_artifacts": storage_urls,
                "updated_at": now_iso,
            }
            analysis_payload = {
                **analysis_record,
                "analyst_id": analyst_id,
                "storage_artifacts": storage_urls,
                "created_at": now_iso,
            }

            self._db.collection("documents").document(document_id).set(doc_payload)
            self._db.collection("analysis_results").document(document_id).set(analysis_payload)

            if analyst_id:
                from firebase_admin import firestore as fb_fs

                self._db.collection("users").document(analyst_id).set(
                    {
                        "analyst_id": analyst_id,
                        "last_active_at": now_iso,
                        "analyses_submitted": fb_fs.Increment(1),
                    },
                    merge=True,
                )

            msg = f"Saved to Cloud Firestore (documents/{document_id} & analysis_results/{document_id})."
            if storage_urls:
                msg += " Artifacts uploaded to Firebase Storage."
            return True, msg
        except Exception as exc:
            return False, f"Firestore write failed (local session preserved): {exc}"

    def fetch_recent_analyses(self, limit: int = 100) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Retrieve recent document records from Firestore for the dashboard."""
        if not self.is_connected:
            return [], "Firebase is not connected."
        try:
            docs = (
                self._db.collection("documents")
                .order_by("upload_timestamp", direction="DESCENDING")
                .limit(limit)
                .stream()
            )
            return [d.to_dict() for d in docs], None
        except Exception as exc:
            return [], f"Failed to fetch Firestore records: {exc}"
