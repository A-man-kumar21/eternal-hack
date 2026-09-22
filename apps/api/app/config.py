"""Central configuration for the e-Abhilekh API."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env",), extra="ignore")

    # --- identity / environment ---
    EABHILEKH_ENV: str = "dev"  # dev | prod; dev-only endpoints disabled unless dev
    EABHILEKH_MASTER_KEY: str = ""  # 64 hex chars = 32 bytes AES-256 master key
    EABHILEKH_JWT_SECRET: str = "change-me-in-production"

    # --- database ---
    DATABASE_URL: str = "postgresql+psycopg://eabhilekh:eabhilekh@localhost:5432/eabhilekh"

    # --- object storage (MinIO via boto3; unset MINIO_ENDPOINT => local fs fallback) ---
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "e-abhilekh"
    MINIO_SECURE: bool = False
    EABHILEKH_LOCAL_STORAGE: str = str(Path.home() / "workspace" / "e-abhilekh" / ".storage")

    # --- staging dir for uploads awaiting the worker ---
    EABHILEKH_STAGING_DIR: str = str(Path.home() / "workspace" / "e-abhilekh" / ".staging")

    # --- antivirus (optional) ---
    CLAMAV_HOST: str = ""
    CLAMAV_PORT: int = 3310

    # --- limits ---
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    ALLOWED_EXTENSIONS: frozenset = frozenset({"pdf", "jpg", "jpeg", "png", "txt"})


@lru_cache
def get_settings() -> Settings:
    return Settings()


def master_key_bytes() -> bytes:
    s = get_settings()
    try:
        raw = bytes.fromhex(s.EABHILEKH_MASTER_KEY.strip())
    except ValueError as exc:  # pragma: no cover - config error
        raise RuntimeError("EABHILEKH_MASTER_KEY must be 64 hex chars (32 bytes)") from exc
    if len(raw) != 32:
        raise RuntimeError("EABHILEKH_MASTER_KEY must decode to exactly 32 bytes")
    return raw
