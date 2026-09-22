"""Generate secrets for .env. Prints export-ready KEY=value lines."""
import secrets

print(f"EABHILEKH_MASTER_KEY={secrets.token_hex(32)}")
print(f"EABHILEKH_JWT_SECRET={secrets.token_urlsafe(48)}")
