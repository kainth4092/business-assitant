"""
Hybrid Local / Google Cloud Platform abstraction layer for Fixdesk.
"""

from backend.cloud.auth import (
    GcpAuthError,
    ServiceAccountKeyBlockedError,
    check_adc_status,
    load_adc_credentials,
)
from backend.cloud.budget import (
    BudgetExceededError,
    check_budget_available,
    get_budget_status,
    record_ai_usage,
    reset_budget_state,
)
from backend.cloud.factories import (
    get_code_store,
    get_embedding_client,
    get_file_store,
    get_llm_client,
    get_sales_store,
    get_vector_store,
)
from backend.cloud.interfaces import (
    CloudPrivacyError,
    EmbeddingClient,
    FileStore,
    LlmClient,
    SalesStore,
    VectorStore,
)

__all__ = [
    "BudgetExceededError",
    "CloudPrivacyError",
    "EmbeddingClient",
    "FileStore",
    "GcpAuthError",
    "LlmClient",
    "SalesStore",
    "ServiceAccountKeyBlockedError",
    "VectorStore",
    "check_adc_status",
    "check_budget_available",
    "get_budget_status",
    "get_code_store",
    "get_embedding_client",
    "get_file_store",
    "get_llm_client",
    "get_sales_store",
    "get_vector_store",
    "load_adc_credentials",
    "record_ai_usage",
    "reset_budget_state",
]
