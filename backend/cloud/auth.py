"""
ADC-Only Google Cloud Authentication Helper for Fixdesk.
Strictly uses Application Default Credentials (`google.auth.default()`) and blocks
downloaded service-account JSON key files to prevent local credential leakage.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import google.auth
from google.auth.exceptions import DefaultCredentialsError

from backend.cloud.config import get_gcp_project_id


class GcpAuthError(RuntimeError):
    """Raised when ADC or GCP project configuration is missing or invalid."""


class ServiceAccountKeyBlockedError(GcpAuthError):
    """Raised when a static service-account JSON key file is supplied."""


def _inspect_credentials_file_for_sa_key(file_path: str) -> None:
    """Reject service-account private key JSON files specified via GOOGLE_APPLICATION_CREDENTIALS."""
    path = Path(file_path).expanduser()
    if not path.exists():
        raise GcpAuthError(
            f"GOOGLE_APPLICATION_CREDENTIALS points to missing file '{file_path}'. "
            "Unset GOOGLE_APPLICATION_CREDENTIALS and run `gcloud auth application-default login`."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GcpAuthError(
            f"Could not parse GOOGLE_APPLICATION_CREDENTIALS file '{file_path}': {exc}"
        ) from exc

    cred_type = str(payload.get("type", "")).strip().lower()
    if cred_type == "service_account" or "private_key" in payload:
        raise ServiceAccountKeyBlockedError(
            "Static service-account JSON key files are blocked by Fixdesk security policy. "
            "Unset GOOGLE_APPLICATION_CREDENTIALS, delete the key file, and authenticate using "
            "Application Default Credentials (`gcloud auth application-default login`)."
        )


def _ensure_fast_adc_probe() -> None:
    """Avoid 15s GCE metadata timeouts on developer laptops unless explicitly enabled."""
    if os.environ.get("FIXDESK_ALLOW_GCE_METADATA", "0") != "1":
        os.environ.setdefault("NO_GCE_CHECK", "true")


def load_adc_credentials(
    scopes: Optional[Tuple[str, ...]] = None,
    require_project: bool = True,
) -> Tuple[Any, str]:
    """
    Load Application Default Credentials via `google.auth.default()` without key files.

    Returns:
        `(credentials, project_id)`
    Raises:
        ServiceAccountKeyBlockedError: if a service-account JSON key is detected.
        GcpAuthError: if ADC or GCP_PROJECT_ID is missing.
    """
    _ensure_fast_adc_probe()

    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if gac:
        _inspect_credentials_file_for_sa_key(gac)

    try:
        if scopes:
            credentials, detected_project = google.auth.default(scopes=list(scopes))
        else:
            credentials, detected_project = google.auth.default()
    except DefaultCredentialsError as exc:
        raise GcpAuthError(
            "Application Default Credentials (ADC) not found. Run:\n"
            "  gcloud auth application-default login\n"
            "  gcloud config set project YOUR_GCP_PROJECT_ID\n"
            "  gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID"
        ) from exc
    except Exception as exc:
        raise GcpAuthError(f"Failed to load GCP ADC credentials: {exc}") from exc

    # Block runtime service-account key credentials objects too
    cred_cls_name = type(credentials).__name__.lower()
    cred_module = type(credentials).__module__.lower()
    if "service_account" in cred_module or (
        "serviceaccount" in cred_cls_name and hasattr(credentials, "signer")
    ):
        raise ServiceAccountKeyBlockedError(
            "Service-account private-key credentials are blocked by Fixdesk policy. "
            "Use user ADC (`gcloud auth application-default login`) or short-lived impersonation."
        )

    project_id = get_gcp_project_id() or (detected_project or "").strip()
    if require_project and not project_id:
        raise GcpAuthError(
            "GCP_PROJECT_ID is not set and ADC has no default quota project. "
            "Set GCP_PROJECT_ID in .env and run `gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID`."
        )

    return credentials, project_id


def check_adc_status() -> Dict[str, Any]:
    """
    Non-throwing diagnostic check for `/status` and inventory scripts.
    Never exposes credential tokens or key material.
    """
    project_id = get_gcp_project_id()
    try:
        creds, resolved_project = load_adc_credentials(require_project=False)
        final_project = project_id or resolved_project
        if not final_project:
            return {
                "adc_ready": False,
                "project_id": None,
                "credential_type": type(creds).__name__,
                "error": "GCP_PROJECT_ID is not configured in .env.",
            }
        return {
            "adc_ready": True,
            "project_id": final_project,
            "credential_type": type(creds).__name__,
            "quota_project": getattr(creds, "quota_project_id", None),
            "error": None,
        }
    except GcpAuthError as exc:
        return {
            "adc_ready": False,
            "project_id": project_id or None,
            "credential_type": None,
            "error": str(exc),
        }
