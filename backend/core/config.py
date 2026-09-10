from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

# Automatically load local .env file if present
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    """Runtime settings read from environment variables, never source secrets."""

    data_mode: str = os.getenv("SOCIALIQ_DATA_MODE", "live").lower()
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "SOCIALIQ_CORS_ORIGINS",
            "*,http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:5501,http://localhost:5501,http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8001,http://localhost:8001,http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    )

    # --- Platform API credentials (read from env, never committed) ---
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8001/api/auth/callback")
    telegram_api_id: str = os.getenv("TELEGRAM_API_ID", "")
    telegram_api_hash: str = os.getenv("TELEGRAM_API_HASH", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    reddit_client_id: str = os.getenv("REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    twitter_bearer_token: str = os.getenv("TWITTER_BEARER_TOKEN", "")
    instagram_access_token: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    instagram_account_id: str = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
    facebook_access_token: str = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
    facebook_page_id: str = os.getenv("FACEBOOK_PAGE_ID", "")

    # --- Supabase PostgreSQL database configuration ---
    supabase_db_url: str = os.getenv("SUPABASE_DB_URL", "")
    supabase_host: str = os.getenv("SUPABASE_HOST", "")
    supabase_port: int = int(os.getenv("SUPABASE_PORT", "5432"))
    supabase_db: str = os.getenv("SUPABASE_DATABASE", "postgres")
    supabase_user: str = os.getenv("SUPABASE_USER", "postgres")
    supabase_password: str = os.getenv("SUPABASE_PASSWORD", "")

    # Configurable storage retention limits (in megabytes)
    storage_soft_limit_mb: float = float(os.getenv("DATABASE_STORAGE_SOFT_LIMIT_MB", "400.0"))
    storage_critical_limit_mb: float = float(os.getenv("DATABASE_STORAGE_CRITICAL_LIMIT_MB", "480.0"))

    # --- Blockchain Audit & Integrity Layer configuration ---
    blockchain_rpc_url: str = os.getenv("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545")
    blockchain_chain_id: int = int(os.getenv("BLOCKCHAIN_CHAIN_ID", "31337"))
    blockchain_network_name: str = os.getenv("BLOCKCHAIN_NETWORK_NAME", "Local EVM (Hardhat Node)")
    blockchain_contract_address: str = os.getenv("BLOCKCHAIN_CONTRACT_ADDRESS", "")
    blockchain_private_key: str = os.getenv("BLOCKCHAIN_PRIVATE_KEY", "")
    blockchain_account_address: str = os.getenv("BLOCKCHAIN_ACCOUNT_ADDRESS", "")
    blockchain_enabled: bool = os.getenv("BLOCKCHAIN_ENABLED", "true").lower() in ("true", "1", "yes")

    def get_database_url(self) -> str:
        """Return the effective PostgreSQL connection URI, or empty string if not configured."""
        if self.supabase_db_url.strip():
            return self.supabase_db_url.strip()
        if self.supabase_host.strip() and self.supabase_password.strip():
            from urllib.parse import quote_plus
            user = quote_plus(self.supabase_user.strip())
            pwd = quote_plus(self.supabase_password.strip())
            host = self.supabase_host.strip()
            port = self.supabase_port
            db = self.supabase_db.strip()
            return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
        return ""


settings = Settings()


