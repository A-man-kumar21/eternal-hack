"""Object storage abstraction: MinIO (boto3) when MINIO_ENDPOINT is set,
otherwise a local-filesystem directory with the same put/get interface.
Ciphertext only — plaintext is never written to disk."""
from __future__ import annotations

import uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from .config import get_settings


class StorageError(RuntimeError):
    pass


class BaseStorage:
    def put_bytes(self, object_key: str, data: bytes) -> None:
        raise NotImplementedError

    def get_bytes(self, object_key: str) -> bytes:
        raise NotImplementedError

    def delete_bytes(self, object_key: str) -> None:
        raise NotImplementedError

    def clear_all(self) -> None:
        """Wipe everything (dev/reset only)."""
        raise NotImplementedError


class MinioStorage(BaseStorage):
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool):
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
        )
        # Idempotent: the bucket survives restarts on the miniodata volume,
        # and minio-init may have created it already.
        try:
            self.client.create_bucket(Bucket=bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise

    def put_bytes(self, object_key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=object_key, Body=data)

    def get_bytes(self, object_key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=object_key)["Body"].read()
        except Exception as exc:
            raise StorageError(f"object not found: {object_key}") from exc

    def delete_bytes(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def clear_all(self) -> None:
        resp = self.client.list_objects_v2(Bucket=self.bucket)
        for obj in resp.get("Contents", []):
            self.client.delete_object(Bucket=self.bucket, Key=obj["Key"])


class LocalStorage(BaseStorage):
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, object_key: str) -> Path:
        p = (self.root / object_key).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise StorageError("object key escapes storage root")
        return p

    def put_bytes(self, object_key: str, data: bytes) -> None:
        p = self._path(object_key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get_bytes(self, object_key: str) -> bytes:
        p = self._path(object_key)
        if not p.exists():
            raise StorageError(f"object not found: {object_key}")
        return p.read_bytes()

    def delete_bytes(self, object_key: str) -> None:
        p = self._path(object_key)
        if p.exists():
            p.unlink()

    def clear_all(self) -> None:
        for child in self.root.iterdir():
            if child.is_dir():
                for f in child.rglob("*"):
                    if f.is_file():
                        f.unlink()
            elif child.is_file():
                child.unlink()


def get_storage() -> BaseStorage:
    s = get_settings()
    if s.MINIO_ENDPOINT:
        return MinioStorage(
            s.MINIO_ENDPOINT, s.MINIO_ACCESS_KEY, s.MINIO_SECRET_KEY, s.MINIO_BUCKET, s.MINIO_SECURE
        )
    return LocalStorage(s.EABHILEKH_LOCAL_STORAGE)


def new_object_key(prefix: str = "blobs") -> str:
    return f"{prefix}/{uuid.uuid4().hex}"
