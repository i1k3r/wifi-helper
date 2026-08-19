"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Wi-Fi Helper service."""

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    LOG_LEVEL: str = "INFO"

    # MikroTik HotSpot Configuration
    # Destination HotSpot login URL to which guests are redirected (HTTP 302)
    MIKROTIK_LOGIN_URL: str = "http://10.1.3.1/login"
    
    # Target URL for the server-side probe (must use HTTP GET)
    MIKROTIK_PROBE_URL: str = "http://10.1.3.1/login"

    # Probe timing (seconds)
    PROBE_TIMEOUT_SECONDS: float = 1.5

    # Navigation Mode:
    # False (Default / Experimental): Serves a branded connect page with a user-initiated
    # "İnternete Bağlan" button to test Android Chrome HTTP warning mitigation.
    # True: Performs an immediate HTTP 302 redirect to MIKROTIK_LOGIN_URL.
    AUTO_REDIRECT: bool = False

    # Reverse proxy header trust (Strictly False by default)
    TRUST_PROXY_HEADERS: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
