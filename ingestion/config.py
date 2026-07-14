from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str
    postgres_password: str
    postgres_db: str

    ontario511_api_base_url: str = "https://511on.ca/api/v2/get/"
    fetch_interval_minutes: int = 120


settings = Settings()
