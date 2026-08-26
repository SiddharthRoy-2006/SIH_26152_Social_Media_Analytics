from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime settings read from environment variables, never source secrets."""

    data_mode: str = os.getenv("SOCIALIQ_DATA_MODE", "empty").lower()
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "SOCIALIQ_CORS_ORIGINS",
            "http://127.0.0.1:5500,http://localhost:5500",
        ).split(",")
        if origin.strip()
    )


settings = Settings()
