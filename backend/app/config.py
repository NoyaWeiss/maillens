"""Runtime configuration, read once from the environment.

The API key is the only secret. It is never logged and never has a default:
the service refuses to start without a sufficiently long key.
"""

import os
from dataclasses import dataclass

MIN_KEY_LENGTH = 32


@dataclass(frozen=True)
class Settings:
    api_key: str
    max_body_bytes: int = 1024 * 1024  # hard cap on request size
    rate_limit_per_minute: int = 60


def load_settings() -> Settings:
    key = os.environ.get("MAILLENS_API_KEY", "")
    if len(key) < MIN_KEY_LENGTH:
        raise RuntimeError(
            f"MAILLENS_API_KEY must be set and at least {MIN_KEY_LENGTH} characters"
        )
    return Settings(api_key=key)
