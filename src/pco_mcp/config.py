from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required
    database_url: str
    pco_client_id: str
    pco_client_secret: str
    token_encryption_key: str
    base_url: str

    # Optional with defaults
    pco_api_base: str = "https://api.planningcenteronline.com"
    token_expiry_hours: int = 24
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
