from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime settings read from environment variables, never source secrets."""

    data_mode: str = os.getenv("SOCIALIQ_DATA_MODE", "demo").lower()
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "SOCIALIQ_CORS_ORIGINS",
            "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:5501,http://localhost:5501,http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8001,http://localhost:8001,http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    )


settings = Settings()
