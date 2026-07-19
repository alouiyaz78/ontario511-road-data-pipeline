from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str
    postgres_password: str
    postgres_db: str

    dashboard_port: int = 8000

    ollama_host: str = "http://ollama:11434"
    ollama_model: str = "qwen3:8b"
    ollama_embedding_model: str = "nomic-embed-text"


settings = Settings()