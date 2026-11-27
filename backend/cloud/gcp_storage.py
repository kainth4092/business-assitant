"""
Google Cloud Storage (`FileStore`) implementation for Fixdesk (`FILE_STORE_BACKEND=gcp`).
Stores raw CSVs (`raw/`), cleaned Parquet (`clean/`), and policy docs (`docs/`) in a US bucket
using Application Default Credentials (ADC).
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.cloud.auth import load_adc_credentials
from backend.cloud.config import get_gcp_multi_region, get_gcp_project_id, get_gcs_bucket
from backend.cloud.interfaces import FileStore

logger = logging.getLogger("FixdeskGCS")


def parse_gcs_uri(uri: str) -> Tuple[str, str]:
    """Split `gs://bucket/path/to/blob` into `(bucket_name, blob_path)`."""
    if not uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI, got '{uri}'")
    stripped = uri[len("gs://"):]
    parts = stripped.split("/", 1)
    bucket_name = parts[0].strip()
    blob_path = parts[1].strip("/") if len(parts) > 1 else ""
    if not bucket_name:
        raise ValueError(f"Missing bucket name in GCS URI '{uri}'")
    return bucket_name, blob_path


class GcsFileStore(FileStore):
    """Google Cloud Storage FileStore supporting `raw/`, `clean/`, and `docs/` prefixes."""

    backend_name = "gcp"

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        project_id: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        self.bucket_name = (bucket_name or get_gcs_bucket()).strip()
        if not self.bucket_name:
            raise ValueError(
                "GCS_BUCKET is not set. Configure GCS_BUCKET in .env when FILE_STORE_BACKEND=gcp."
            )
        self._explicit_project = (project_id or get_gcp_project_id()).strip()
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        from google.cloud import storage

        creds, resolved_project = load_adc_credentials(require_project=False)
        project = self._explicit_project or resolved_project
        self._client = storage.Client(project=project or None, credentials=creds)
        return self._client

    def _get_bucket(self):
        client = self._get_client()
        return client.bucket(self.bucket_name)

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        clean = prefix.strip("/")
        if clean == "data":
            return "raw"
        return clean

    def _object_name(self, prefix: str, filename: str) -> str:
        clean_prefix = self._normalize_prefix(prefix)
        clean_name = os.path.basename(filename) if "/" not in filename else filename.strip("/")
        return f"{clean_prefix}/{clean_name}" if clean_prefix else clean_name

    def save_bytes(self, prefix: str, filename: str, data: bytes) -> str:
        blob_name = self._object_name(prefix, filename)
        bucket = self._get_bucket()
        blob = bucket.blob(blob_name)
        blob.upload_from_string(data)
        return f"gs://{self.bucket_name}/{blob_name}"

    def read_bytes(self, uri_or_path: str) -> bytes:
        if not uri_or_path.startswith("gs://"):
            return Path(uri_or_path).read_bytes()
        bucket_name, blob_name = parse_gcs_uri(uri_or_path)
        client = self._get_client()
        blob = client.bucket(bucket_name).blob(blob_name)
        return blob.download_as_bytes()

    def download_to_local(self, uri_or_path: str, dest_path: str) -> str:
        if not uri_or_path.startswith("gs://"):
            src = Path(uri_or_path)
            dst = Path(dest_path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.resolve() != dst.resolve():
                dst.write_bytes(src.read_bytes())
            return str(dst)

        bucket_name, blob_name = parse_gcs_uri(uri_or_path)
        client = self._get_client()
        bucket = client.bucket(bucket_name)
        dst = Path(dest_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(str(dst))
        return str(dst)

    def upload_from_local(
        self, local_path: str, prefix: str, remote_name: Optional[str] = None
    ) -> str:
        src = Path(local_path)
        clean_prefix = self._normalize_prefix(prefix)
        bucket = self._get_bucket()

        if src.is_dir():
            folder_name = remote_name or src.name
            base_blob = f"{clean_prefix}/{folder_name}" if clean_prefix else folder_name
            uploaded_any = False
            for file_path in sorted(src.rglob("*")):
                if not file_path.is_file():
                    continue
                # Skip Spark _SUCCESS or CRC metadata files when uploading Parquet parts
                if file_path.name.startswith(".") or file_path.name == "_SUCCESS":
                    continue
                rel = file_path.relative_to(src).as_posix()
                blob_name = f"{base_blob}/{rel}"
                bucket.blob(blob_name).upload_from_filename(str(file_path))
                uploaded_any = True
            if not uploaded_any:
                raise FileNotFoundError(f"No data files found in directory '{local_path}' to upload.")
            return f"gs://{self.bucket_name}/{base_blob}"

        name = remote_name or src.name
        blob_name = f"{clean_prefix}/{name}" if clean_prefix else name
        bucket.blob(blob_name).upload_from_filename(str(src))
        return f"gs://{self.bucket_name}/{blob_name}"

    def list_files(self, prefix: str, extensions: Optional[tuple] = None) -> List[str]:
        clean_prefix = self._normalize_prefix(prefix)
        prefix_filter = f"{clean_prefix}/" if clean_prefix else ""
        client = self._get_client()
        blobs = client.list_blobs(self.bucket_name, prefix=prefix_filter)
        uris: List[str] = []
        for blob in blobs:
            name = getattr(blob, "name", "")
            if not name or name.endswith("/"):
                continue
            base = os.path.basename(name)
            if base.startswith("."):
                continue
            if extensions and not base.lower().endswith(extensions):
                continue
            uris.append(f"gs://{self.bucket_name}/{name}")
        return sorted(uris)

    def exists(self, uri_or_path: str) -> bool:
        if not uri_or_path.startswith("gs://"):
            return Path(uri_or_path).exists()
        bucket_name, blob_name = parse_gcs_uri(uri_or_path)
        client = self._get_client()
        return bool(client.bucket(bucket_name).blob(blob_name).exists())

    def ensure_local_copy(self, uri_or_path: str, cache_dir: Optional[str] = None) -> str:
        if not uri_or_path.startswith("gs://"):
            return str(Path(uri_or_path))
        _, blob_name = parse_gcs_uri(uri_or_path)
        base_cache = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "fixdesk_gcs_cache"
        dest = base_cache / blob_name
        return self.download_to_local(uri_or_path, str(dest))

    def ensure_bucket_exists(self) -> Dict[str, Any]:
        """Verify bucket exists and report location (prefers US multi-region)."""
        client = self._get_client()
        bucket = client.lookup_bucket(self.bucket_name)
        if bucket is not None:
            return {
                "bucket": self.bucket_name,
                "exists": True,
                "location": getattr(bucket, "location", get_gcp_multi_region()),
            }
        return {
            "bucket": self.bucket_name,
            "exists": False,
            "recommended_location": get_gcp_multi_region(),
        }
