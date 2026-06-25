from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse


ARTIFACT_URI_PREFIX = "artifact:"
DEFAULT_ARTIFACT_BUCKET = "tryops-artifacts"


class RuntimeArtifactError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeArtifactStorage:
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    secure: bool

    @property
    def enabled(self) -> bool:
        return bool(self.endpoint and self.bucket and self.access_key and self.secret_key)

    def put_file(self, *, object_key: str, path: str | Path, content_type: str) -> dict[str, Any]:
        source = Path(path)
        if not source.is_file():
            raise RuntimeArtifactError(f"artifact source does not exist: {source}")
        client = self._client()
        self._ensure_bucket(client)
        client.fput_object(self.bucket, object_key, str(source), content_type=content_type)
        stat = client.stat_object(self.bucket, object_key)
        return {
            "backend": "minio",
            "bucket": self.bucket,
            "object_key": object_key,
            "content_type": content_type,
            "size_bytes": int(getattr(stat, "size", source.stat().st_size) or source.stat().st_size),
            "sha256": sha256_file(source),
        }

    def put_bytes(self, *, object_key: str, data: bytes, content_type: str) -> dict[str, Any]:
        from io import BytesIO

        client = self._client()
        self._ensure_bucket(client)
        client.put_object(
            self.bucket,
            object_key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return {
            "backend": "minio",
            "bucket": self.bucket,
            "object_key": object_key,
            "content_type": content_type,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def stream_object(self, *, object_key: str) -> Iterator[bytes]:
        response = self._client().get_object(self.bucket, object_key)
        try:
            for chunk in response.stream(64 * 1024):
                if chunk:
                    yield chunk
        finally:
            response.close()
            response.release_conn()

    def materialize_to_temp(
        self,
        *,
        object_key: str,
        scratch_dir: str | Path,
        filename: str,
    ) -> Path:
        scratch = Path(scratch_dir)
        scratch.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix or ".bin"
        handle = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f"{Path(filename).stem[:64]}-",
            suffix=suffix,
            dir=scratch,
            delete=False,
        )
        destination = Path(handle.name)
        try:
            with handle:
                for chunk in self.stream_object(object_key=object_key):
                    handle.write(chunk)
            return destination
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def stat(self, *, object_key: str) -> dict[str, Any]:
        stat = self._client().stat_object(self.bucket, object_key)
        return {
            "backend": "minio",
            "bucket": self.bucket,
            "object_key": object_key,
            "content_type": getattr(stat, "content_type", None),
            "size_bytes": int(getattr(stat, "size", 0) or 0),
            "etag": getattr(stat, "etag", None),
        }

    def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "reason": "MinIO runtime artifact storage is not configured"}
        try:
            self._client().bucket_exists(self.bucket)
        except Exception as exc:
            return {"status": "unavailable", "reason": str(exc)}
        return {"status": "ready", "bucket": self.bucket, "endpoint": self.endpoint}

    def _ensure_bucket(self, client: Any) -> None:
        if not client.bucket_exists(self.bucket):
            client.make_bucket(self.bucket)

    def _client(self) -> Any:
        if not self.enabled:
            raise RuntimeArtifactError("MinIO runtime artifact storage is not configured")
        try:
            from minio import Minio
        except ImportError as exc:
            raise RuntimeArtifactError("minio package is not installed") from exc
        return Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )


def storage_from_env() -> RuntimeArtifactStorage | None:
    endpoint = os.getenv("TRYOPS_MINIO_ENDPOINT", "").strip()
    access_key = _read_env_or_file(
        "TRYOPS_MINIO_RUNTIME_ACCESS_KEY",
        "TRYOPS_MINIO_RUNTIME_ACCESS_KEY_FILE",
    )
    secret_key = _read_env_or_file(
        "TRYOPS_MINIO_RUNTIME_SECRET_KEY",
        "TRYOPS_MINIO_RUNTIME_SECRET_KEY_FILE",
    )
    bucket = os.getenv("TRYOPS_ARTIFACT_BUCKET", DEFAULT_ARTIFACT_BUCKET).strip() or DEFAULT_ARTIFACT_BUCKET
    if not endpoint or not access_key or not secret_key:
        return None
    parsed = urlparse(endpoint)
    if parsed.scheme and parsed.netloc:
        return RuntimeArtifactStorage(
            endpoint=parsed.netloc,
            bucket=bucket,
            access_key=access_key,
            secret_key=secret_key,
            secure=parsed.scheme == "https",
        )
    secure = os.getenv("TRYOPS_MINIO_SECURE", "0").strip().lower() in {"1", "true", "yes"}
    return RuntimeArtifactStorage(
        endpoint=endpoint,
        bucket=bucket,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )


def artifact_uri(artifact_id: str) -> str:
    return f"{ARTIFACT_URI_PREFIX}{artifact_id}"


def artifact_id_from_ref(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    if not stripped.startswith(ARTIFACT_URI_PREFIX):
        return None
    artifact_id = stripped[len(ARTIFACT_URI_PREFIX) :].strip()
    return artifact_id or None


def account_object_key(account_id: str, *parts: str) -> str:
    clean_parts = [_clean_key_part(part) for part in parts if str(part).strip()]
    return "/".join(["runtime", "vton", "accounts", _clean_key_part(account_id), *clean_parts])


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_env_or_file(env_name: str, file_env_name: str) -> str:
    value = os.getenv(env_name, "").strip()
    if value:
        return value
    path = os.getenv(file_env_name, "").strip()
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _clean_key_part(value: str) -> str:
    cleaned = str(value).strip().replace("\\", "/").strip("/")
    cleaned = cleaned.replace("..", "")
    return cleaned or "unknown"
