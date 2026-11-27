"""
Narrow abstract interfaces for Fixdesk storage, file, vector, LLM, and embedding backends.
Allows seamless switching between laptop PostgreSQL/local-disk/Gemini-API and GCP services.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CloudPrivacyError(PermissionError):
    """Raised when a local-only project is prevented from sending data to cloud services."""


class SalesStore(ABC):
    """Structured analytics table, schema metadata, quality report, and Support sandbox store."""

    backend_name: str = "local"

    @abstractmethod
    def sql_dialect(self) -> str:
        """Return 'postgres' or 'bigquery'."""

    @abstractmethod
    def query_sales(self, sql_query: str) -> Dict[str, Any]:
        """Execute a validated single read-only SELECT query with LIMIT <= 100."""

    @abstractmethod
    def get_data_quality_report(self) -> Dict[str, Any]:
        """Fetch latest PySpark data quality report."""

    @abstractmethod
    def get_schema_metadata(self) -> Dict[str, Any]:
        """Fetch discovered schema metadata for the active sales table."""

    @abstractmethod
    def get_sales_count(self) -> int:
        """Return row count of active sales table (0 if unavailable/empty)."""

    @abstractmethod
    def get_top_categorical_values(self, column: str, limit: int = 2) -> List[str]:
        """Return most frequent non-Unknown values for a categorical column."""

    @abstractmethod
    def run_data_quality_checks(self, table_name: str = "sales") -> Dict[str, Any]:
        """Inspect labels, nulls, and numeric outliers on sales or sandbox."""

    @abstractmethod
    def preview_data_fix(self, sql_patch: str, ticket_id: str) -> Dict[str, Any]:
        """Execute remediation SQL strictly inside the isolated sandbox table."""

    @abstractmethod
    def apply_data_fix(self, sql_patch: str) -> Dict[str, Any]:
        """Execute human-approved remediation SQL against the production sales table."""

    @abstractmethod
    def load_sales_from_parquet(
        self,
        parquet_uri_or_path: str,
        schema_metadata: Dict[str, Any],
        quality_report: Dict[str, Any],
        df: Any = None,
    ) -> Dict[str, Any]:
        """Load cleaned Parquet records, sandbox mirror, quality report, and schema metadata."""

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return connectivity and record-count telemetry for /status."""


class VectorStore(ABC):
    """Semantic vector store for policy documents (`document_embeddings`)."""

    backend_name: str = "local"

    @abstractmethod
    def upsert_document_chunks(
        self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]
    ) -> int:
        """Replace/upsert indexed document chunks and their 768-D embeddings."""

    @abstractmethod
    def search_documents(
        self, query_vector: List[float], top_k: int = 3, query_text: str = ""
    ) -> List[Dict[str, Any]]:
        """Return top-k chunks ordered by cosine similarity."""

    @abstractmethod
    def list_indexed_sources(self) -> List[Dict[str, Any]]:
        """List indexed document sources with chunk counts and excerpts."""

    @abstractmethod
    def get_document_chunks(self, source_file: str) -> List[Dict[str, Any]]:
        """Return all ordered chunks for a document."""

    @abstractmethod
    def count_chunks(self) -> int:
        """Return total indexed document chunks."""

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return vector store readiness and chunk count."""


class FileStore(ABC):
    """File storage abstraction for raw CSVs, cleaned Parquet, and policy docs."""

    backend_name: str = "local"

    @abstractmethod
    def save_bytes(self, prefix: str, filename: str, data: bytes) -> str:
        """Persist raw bytes under prefix (raw, clean, docs) and return path or URI."""

    @abstractmethod
    def read_bytes(self, uri_or_path: str) -> bytes:
        """Read bytes from local path or gs:// URI."""

    @abstractmethod
    def download_to_local(self, uri_or_path: str, dest_path: str) -> str:
        """Ensure a local file copy exists at dest_path."""

    @abstractmethod
    def upload_from_local(
        self, local_path: str, prefix: str, remote_name: Optional[str] = None
    ) -> str:
        """Upload a local file (or Parquet directory) under prefix and return path or URI."""

    @abstractmethod
    def list_files(self, prefix: str, extensions: Optional[tuple] = None) -> List[str]:
        """List filenames/URIs under prefix."""

    @abstractmethod
    def exists(self, uri_or_path: str) -> bool:
        """Return True if file/object exists."""

    @abstractmethod
    def ensure_local_copy(self, uri_or_path: str, cache_dir: Optional[str] = None) -> str:
        """Return a readable local path for Spark/pypdf, downloading from GCS if needed."""


class LlmClient(ABC):
    """Unified chat/tool-calling LLM client abstraction."""

    backend_name: str = "unconfigured"

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when credentials and model configuration are ready."""

    @abstractmethod
    def get_chat_model(
        self, model_name: Optional[str] = None, temperature: Optional[float] = None
    ) -> Any:
        """Return a configured LangChain BaseChatModel instance."""

    @abstractmethod
    def invoke_messages(
        self,
        messages: Any,
        model_name: Optional[str] = None,
        tools: Optional[List[Any]] = None,
    ) -> Any:
        """Invoke chat model with retry, timeout, and daily budget accounting."""

    @abstractmethod
    def status_summary(self) -> Dict[str, Any]:
        """Return safe diagnostic status without exposing secret keys."""


class EmbeddingClient(ABC):
    """Unified 768-dimensional text embedding client abstraction."""

    backend_name: str = "fallback"

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when live cloud embedding credentials are ready."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Return a unit-normalized 768-D vector for a single query string."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Return unit-normalized 768-D vectors for a batch of documents."""

    @abstractmethod
    def status_summary(self) -> Dict[str, Any]:
        """Return safe diagnostic status."""
