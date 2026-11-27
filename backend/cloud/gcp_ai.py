"""
Vertex AI Gemini LLM & Embedding Clients via Application Default Credentials (ADC).
Uses `langchain-google-genai` 4.5+ (`vertexai=True`) and `google-genai` 3.6+
with exponential backoff retries, timeouts, and daily request/token budget enforcement.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from backend.cloud.auth import GcpAuthError, check_adc_status, load_adc_credentials
from backend.cloud.budget import BudgetExceededError, check_budget_available, record_ai_usage
from backend.cloud.config import get_gcp_project_id, get_gcp_region
from backend.cloud.interfaces import EmbeddingClient, LlmClient
from backend.cloud.local_impl import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_LLM_MODEL,
    VECTOR_DIMENSION,
    deterministic_fallback_embedding,
    normalize_vector,
)

logger = logging.getLogger("FixdeskVertexAI")


def _extract_usage_tokens(response: Any) -> Optional[int]:
    meta = getattr(response, "usage_metadata", None)
    if isinstance(meta, dict):
        total = meta.get("total_token_count") or meta.get("total_tokens")
        if total is not None:
            return int(total)
        in_tok = meta.get("input_tokens") or meta.get("prompt_token_count") or 0
        out_tok = meta.get("output_tokens") or meta.get("candidates_token_count") or 0
        if in_tok or out_tok:
            return int(in_tok) + int(out_tok)
    return None


class VertexLlmClient(LlmClient):
    """Vertex AI Gemini chat model client authenticated strictly via ADC."""

    backend_name = "vertexai"

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._project_id = (project_id or get_gcp_project_id()).strip()
        self._location = (location or get_gcp_region()).strip()
        self._default_model = (
            (model_name or os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL)).strip()
            or DEFAULT_LLM_MODEL
        )

    def is_configured(self) -> bool:
        status = check_adc_status()
        return bool(status.get("adc_ready") and (self._project_id or status.get("project_id")))

    def get_genai_client(self):
        """Return a `google.genai.Client(vertexai=True, ...)` configured via ADC."""
        from google import genai

        creds, project_id = load_adc_credentials(require_project=True)
        project = self._project_id or project_id
        return genai.Client(
            vertexai=True,
            project=project,
            location=self._location,
            credentials=creds,
        )

    def get_chat_model(
        self, model_name: Optional[str] = None, temperature: Optional[float] = None
    ) -> Any:
        try:
            creds, detected_project = load_adc_credentials(require_project=True)
        except GcpAuthError as exc:
            logger.warning(f"Vertex AI ADC unavailable: {exc}")
            return None

        from langchain_google_genai import ChatGoogleGenerativeAI

        project = self._project_id or detected_project
        resolved_model = (model_name or self._default_model).strip() or DEFAULT_LLM_MODEL
        kwargs: Dict[str, Any] = {
            "model": resolved_model,
            "vertexai": True,
            "project": project,
            "location": self._location,
            "credentials": creds,
            "max_retries": 2,
            "timeout": 30.0,
        }
        if not ("gemini-3" in resolved_model or "gemini-4" in resolved_model):
            kwargs["temperature"] = 0.0 if temperature is None else temperature
        return ChatGoogleGenerativeAI(**kwargs)

    def invoke_messages(
        self,
        messages: Any,
        model_name: Optional[str] = None,
        tools: Optional[List[Any]] = None,
    ) -> Any:
        model = self.get_chat_model(model_name=model_name)
        if model is None:
            return None
        check_budget_available()
        runnable = model.bind_tools(tools) if tools else model
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = runnable.invoke(messages)
                in_chars = (
                    sum(len(str(m)) for m in messages)
                    if isinstance(messages, list)
                    else len(str(messages))
                )
                out_chars = len(str(getattr(resp, "content", resp)))
                tok = _extract_usage_tokens(resp)
                record_ai_usage(
                    requests=1,
                    input_chars=in_chars,
                    output_chars=out_chars,
                    tokens=tok,
                )
                return resp
            except BudgetExceededError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
        if last_exc:
            raise last_exc
        return None

    def status_summary(self) -> Dict[str, Any]:
        adc = check_adc_status()
        return {
            "backend": self.backend_name,
            "configured": bool(adc.get("adc_ready")),
            "project_id": self._project_id or adc.get("project_id"),
            "location": self._location,
            "model": self._default_model,
            "auth_error": adc.get("error"),
        }


class VertexEmbeddingClient(EmbeddingClient):
    """Vertex AI 768-D Embedding client authenticated via ADC with retry & budget tracking."""

    backend_name = "vertexai"

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._project_id = (project_id or get_gcp_project_id()).strip()
        self._location = (location or get_gcp_region()).strip()
        self._default_model = (
            (model_name or os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)).strip()
            or DEFAULT_EMBEDDING_MODEL
        )

    def is_configured(self) -> bool:
        status = check_adc_status()
        return bool(status.get("adc_ready") and (self._project_id or status.get("project_id")))

    def _get_client(self):
        creds, detected_project = load_adc_credentials(require_project=True)
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        project = self._project_id or detected_project
        return GoogleGenerativeAIEmbeddings(
            model=self._default_model,
            vertexai=True,
            project=project,
            location=self._location,
            credentials=creds,
        )

    def embed_query(self, text: str) -> List[float]:
        try:
            if not self.is_configured():
                return deterministic_fallback_embedding(text, VECTOR_DIMENSION)
            check_budget_available()
            client = self._get_client()
            last_exc: Optional[Exception] = None
            for attempt in range(3):
                try:
                    vec = client.embed_query(text, output_dimensionality=VECTOR_DIMENSION)
                    record_ai_usage(requests=1, input_chars=len(text), output_chars=0)
                    if len(vec) == VECTOR_DIMENSION:
                        return normalize_vector(vec)
                    break
                except BudgetExceededError:
                    raise
                except Exception as exc:
                    last_exc = exc
                    if attempt < 2:
                        time.sleep(0.5 * (2 ** attempt))
            if last_exc:
                raise last_exc
        except BudgetExceededError:
            raise
        except Exception as e:
            logger.warning(f"Vertex AI embedding error ({e}). Using deterministic local embedding.")
        return deterministic_fallback_embedding(text, VECTOR_DIMENSION)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            if not self.is_configured():
                return [deterministic_fallback_embedding(t, VECTOR_DIMENSION) for t in texts]
            check_budget_available()
            client = self._get_client()
            last_exc: Optional[Exception] = None
            for attempt in range(3):
                try:
                    vecs = client.embed_documents(texts, output_dimensionality=VECTOR_DIMENSION)
                    record_ai_usage(
                        requests=1, input_chars=sum(len(t) for t in texts), output_chars=0
                    )
                    if len(vecs) == len(texts) and all(len(v) == VECTOR_DIMENSION for v in vecs):
                        return [normalize_vector(v) for v in vecs]
                    break
                except BudgetExceededError:
                    raise
                except Exception as exc:
                    last_exc = exc
                    if attempt < 2:
                        time.sleep(0.5 * (2 ** attempt))
            if last_exc:
                raise last_exc
        except BudgetExceededError:
            raise
        except Exception as e:
            logger.warning(f"Vertex AI batch embedding error ({e}). Using deterministic local embedding.")
        return [deterministic_fallback_embedding(t, VECTOR_DIMENSION) for t in texts]

    def status_summary(self) -> Dict[str, Any]:
        adc = check_adc_status()
        return {
            "backend": self.backend_name if adc.get("adc_ready") else "fallback",
            "configured": bool(adc.get("adc_ready")),
            "project_id": self._project_id or adc.get("project_id"),
            "location": self._location,
            "model": self._default_model,
            "dimension": VECTOR_DIMENSION,
            "auth_error": adc.get("error"),
        }
