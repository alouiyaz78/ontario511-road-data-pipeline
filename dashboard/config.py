from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str
    postgres_password: str
    postgres_db: str

    dashboard_port: int = 8000


settings = Settings()
