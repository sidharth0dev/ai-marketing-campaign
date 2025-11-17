from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",  # This tells Pydantic to ignore env vars not defined above
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_name: str = "AI Product API"
    secret_key: str = Field(default="change-me-please")
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"
    database_url: str = "sqlite:///./app.db"
    GOOGLE_PROJECT_ID: str = "windy-gearbox-477912-q3"
    GOOGLE_LOCATION: str = "us-central1"


settings = Settings()

