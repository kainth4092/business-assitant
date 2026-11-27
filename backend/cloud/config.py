"""
Environment-driven configuration helpers for Fixdesk hybrid local/GCP backends.
Reads environment variables dynamically so runtime and test overrides take effect immediately.
"""

import contextlib
import contextvars
import os
from typing import Iterator, Optional

_CLOUD_ALLOWED_CTX: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "fixdesk_cloud_allowed", default=True
)


@contextlib.contextmanager
def cloud_allowed_scope(allowed: bool) -> Iterator[None]:
    """Temporarily scope whether cloud LLM/embedding calls are permitted for a project."""
    token = _CLOUD_ALLOWED_CTX.set(bool(allowed))
    try:
        yield
    finally:
        _CLOUD_ALLOWED_CTX.reset(token)


def is_cloud_allowed_in_context() -> bool:
    return bool(_CLOUD_ALLOWED_CTX.get())


def _env_lower(name: str, default: str) -> str:
    return os.environ.get(name, default).strip().lower() or default


def get_storage_backend(override: Optional[str] = None) -> str:
    val = (override or _env_lower("STORAGE_BACKEND", "local")).strip().lower()
    return val if val in ("local", "gcp") else "local"


def get_vector_backend(override: Optional[str] = None) -> str:
    val = (override or _env_lower("VECTOR_BACKEND", "local")).strip().lower()
    return val if val in ("local", "gcp") else "local"


def get_file_store_backend(override: Optional[str] = None) -> str:
    val = (override or _env_lower("FILE_STORE_BACKEND", "local")).strip().lower()
    return val if val in ("local", "gcp") else "local"


def get_llm_backend(override: Optional[str] = None) -> str:
    val = (override or _env_lower("LLM_BACKEND", "auto")).strip().lower()
    return val if val in ("auto", "vertexai", "gemini_api") else "auto"


def get_embedding_backend(override: Optional[str] = None) -> str:
    val = (override or _env_lower("EMBEDDING_BACKEND", "auto")).strip().lower()
    return val if val in ("auto", "vertexai", "gemini_api") else "auto"


def get_document_rag_backend(override: Optional[str] = None) -> str:
    val = (override or _env_lower("DOCUMENT_RAG_BACKEND", "default")).strip().lower()
    return val if val in ("default", "vertex_rag_engine") else "default"


def get_gcp_project_id() -> str:
    return os.environ.get("GCP_PROJECT_ID", "").strip()


def get_gcp_region() -> str:
    return os.environ.get("GCP_REGION", "us-central1").strip() or "us-central1"


def get_gcp_multi_region() -> str:
    return os.environ.get("GCP_MULTI_REGION", "US").strip() or "US"


def get_gcs_bucket() -> str:
    return os.environ.get("GCS_BUCKET", "").strip()


def get_bq_dataset() -> str:
    return os.environ.get("BQ_DATASET", "fixdesk").strip() or "fixdesk"


def get_bq_sandbox_dataset() -> str:
    return os.environ.get("BQ_SANDBOX_DATASET", "fixdesk_sandbox").strip() or "fixdesk_sandbox"


def get_bq_vector_dataset() -> str:
    return os.environ.get("BQ_VECTOR_DATASET", "fixdesk_vectors").strip() or "fixdesk_vectors"


def get_bq_max_bytes_billed() -> int:
    raw = os.environ.get("BQ_MAX_BYTES_BILLED", "104857600").strip()
    try:
        val = int(raw)
        return max(1024 * 1024, val)
    except ValueError:
        return 104857600


def is_valid_gemini_api_key() -> bool:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    return bool(key and not key.startswith("your_") and not key.startswith("test_placeholder_"))
