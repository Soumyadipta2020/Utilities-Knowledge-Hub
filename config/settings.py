from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    databricks_host: str = Field(default="")
    databricks_token: str = Field(default="")
    warehouse_id: str = Field(default="")
    snowflake_account: str = Field(default="")
    snowflake_user: str = Field(default="")
    snowflake_password: str = Field(default="")
    duckdb_cache_path: str = Field(default="metadata_cache.duckdb")
    query_timeout_seconds: int = Field(default=30)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
