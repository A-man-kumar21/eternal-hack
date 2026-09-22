"""Envelope encryption: AES-256-GCM data keys wrapped by a master key."""
from __future__ import annotations

import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import master_key_bytes


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encrypt_blob(plaintext: bytes, master_key: bytes | None = None) -> dict:
    """Encrypt bytes with a fresh random DEK; wrap DEK with the master key.

    Returns dict with hex-encoded ciphertext, wrapped_dek, dek_nonce,
    gcm_nonce, gcm_tag, and sha256 of the PLAINTEXT (for integrity verify).
    """
    mk = master_key if master_key is not None else master_key_bytes()
    dek = AESGCM.generate_key(bit_length=256)
    gcm_nonce = os.urandom(12)
    aesgcm = AESGCM(dek)
    ct_and_tag = aesgcm.encrypt(gcm_nonce, plaintext, None)
    ciphertext, tag = ct_and_tag[:-16], ct_and_tag[-16:]

    wrap = AESGCM(mk)
    dek_nonce = os.urandom(12)
    wrapped = wrap.encrypt(dek_nonce, dek, None)
    wrapped_dek, wrap_tag = wrapped[:-16], wrapped[-16:]

    return {
        "ciphertext": ciphertext.hex(),
        "wrapped_dek": (wrapped_dek + wrap_tag).hex(),
        "dek_nonce": dek_nonce.hex(),
        "gcm_nonce": gcm_nonce.hex(),
        "gcm_tag": tag.hex(),
        "sha256": sha256_hex(plaintext),
    }


def decrypt_blob(
    ciphertext_hex: str,
    wrapped_dek_hex: str,
    dek_nonce_hex: str,
    gcm_nonce_hex: str,
    gcm_tag_hex: str,
    master_key: bytes | None = None,
) -> bytes:
    """Unwrap the DEK with the master key, then decrypt. Raises on wrong key/tag."""
    mk = master_key if master_key is not None else master_key_bytes()
    wrapped = bytes.fromhex(wrapped_dek_hex)
    wrapped_dek, wrap_tag = wrapped[:-16], wrapped[-16:]
    dek = AESGCM(mk).decrypt(bytes.fromhex(dek_nonce_hex), wrapped_dek + wrap_tag, None)
    ciphertext = bytes.fromhex(ciphertext_hex)
    tag = bytes.fromhex(gcm_tag_hex)
    return AESGCM(dek).decrypt(bytes.fromhex(gcm_nonce_hex), ciphertext + tag, None)
