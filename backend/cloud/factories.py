"""
Factory selectors for Fixdesk storage, file, vector, LLM, and embedding backends.
Reads environment variables dynamically so runtime changes and tests work cleanly.
"""

from typing import Optional

from backend.cloud.auth import check_adc_status
from backend.cloud.config import (
    get_embedding_backend,
    get_file_store_backend,
    get_gcp_project_id,
    get_llm_backend,
    get_storage_backend,
    get_vector_backend,
    is_valid_gemini_api_key,
)
from backend.cloud.gcp_ai import VertexEmbeddingClient, VertexLlmClient
from backend.cloud.gcp_bigquery import BigQuerySalesStore
from backend.cloud.gcp_storage import GcsFileStore
from backend.cloud.gcp_vector import BigQueryCodeVectorStore, BigQueryVectorStore
from backend.cloud.interfaces import (
    CloudPrivacyError,
    EmbeddingClient,
    FileStore,
    LlmClient,
    SalesStore,
    VectorStore,
)
from backend.cloud.local_impl import (
    GeminiApiEmbeddingClient,
    GeminiApiLlmClient,
    LocalFileStore,
    PgVectorStore,
    PostgresSalesStore,
)


def get_sales_store(backend: Optional[str] = None) -> SalesStore:
    if get_storage_backend(backend) == "gcp":
        return BigQuerySalesStore()
    return PostgresSalesStore()


def get_vector_store(backend: Optional[str] = None) -> VectorStore:
    if get_vector_backend(backend) == "gcp":
        return BigQueryVectorStore()
    return PgVectorStore()


def get_file_store(backend: Optional[str] = None) -> FileStore:
    if get_file_store_backend(backend) == "gcp":
        return GcsFileStore()
    return LocalFileStore()


def get_llm_client(
    backend: Optional[str] = None, cloud_allowed: bool = True
) -> Optional[LlmClient]:
    choice = get_llm_backend(backend)
    if choice == "vertexai":
        if not cloud_allowed:
            raise CloudPrivacyError(
                "Vertex AI LLM call refused: project has `cloud_index_allowed: false` in projects.yaml."
            )
        return VertexLlmClient()
    if choice == "gemini_api":
        if not cloud_allowed:
            return None
        client = GeminiApiLlmClient()
        return client if client.is_configured() else None

    # auto mode: prefer Vertex AI via ADC when configured, else Gemini Developer API key
    if cloud_allowed and get_gcp_project_id():
        adc = check_adc_status()
        if adc.get("adc_ready"):
            return VertexLlmClient()
    if cloud_allowed and is_valid_gemini_api_key():
        return GeminiApiLlmClient()
    return None


def get_embedding_client(
    backend: Optional[str] = None, cloud_allowed: bool = True
) -> EmbeddingClient:
    choice = get_embedding_backend(backend)
    if choice == "vertexai":
        if not cloud_allowed:
            raise CloudPrivacyError(
                "Vertex AI embedding call refused: project has `cloud_index_allowed: false` in projects.yaml."
            )
        return VertexEmbeddingClient()
    if choice == "gemini_api":
        if not cloud_allowed:
            return _LocalOnlyFallbackEmbeddingClient()
        return GeminiApiEmbeddingClient()

    # auto mode: prefer Vertex AI via ADC when configured, else Gemini Developer API key (with local fallback)
    if cloud_allowed and get_gcp_project_id():
        adc = check_adc_status()
        if adc.get("adc_ready"):
            return VertexEmbeddingClient()
    if cloud_allowed:
        return GeminiApiEmbeddingClient()
    return _LocalOnlyFallbackEmbeddingClient()


class _LocalOnlyFallbackEmbeddingClient(EmbeddingClient):
    """Deterministic 768-D local-only embedder used when cloud indexing is disallowed."""

    backend_name = "local_only"

    def is_configured(self) -> bool:
        return False

    def embed_query(self, text: str):
        from backend.cloud.local_impl import VECTOR_DIMENSION, deterministic_fallback_embedding

        return deterministic_fallback_embedding(text, VECTOR_DIMENSION)

    def embed_documents(self, texts):
        from backend.cloud.local_impl import VECTOR_DIMENSION, deterministic_fallback_embedding

        return [deterministic_fallback_embedding(t, VECTOR_DIMENSION) for t in texts]

    def status_summary(self):
        return {"backend": "local_only", "configured": False, "dimension": 768}


def get_code_store(
    project_name: Optional[str] = None,
    config_path: Optional[str] = None,
    backend: Optional[str] = None,
    require_cloud_if_gcp: bool = False,
):
    """
    Return the active Codebase RAG store, strictly enforcing `cloud_index_allowed`
    from `projects.yaml` before allowing BigQuery storage.
    """
    from project_init.store import PostgresCodeStore

    vec_backend = get_vector_backend(backend)
    if vec_backend != "gcp":
        return PostgresCodeStore()

    if project_name:
        from project_init.config import get_project_config

        cfg = get_project_config(project_name, config_path=config_path)
        if not cfg.cloud_index_allowed:
            if require_cloud_if_gcp:
                raise CloudPrivacyError(
                    f"Cloud indexing refused for project '{project_name}': "
                    "`cloud_index_allowed` is false in projects.yaml."
                )
            return PostgresCodeStore()
        return BigQueryCodeVectorStore()

    # Without an explicit project name, check if any configured project permits cloud indexing
    from project_init.config import load_projects_config

    configs = load_projects_config(config_path=config_path)
    if any(c.cloud_index_allowed for c in configs):
        return BigQueryCodeVectorStore()
    return PostgresCodeStore()
