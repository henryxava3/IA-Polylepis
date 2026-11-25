from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://polylepis:polylepis_local@127.0.0.1:54329/polylepis"
    database_extensions: bool = False
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    openalex_api_key: str = ""
    contact_email: str = ""
    gbif_username: str = ""
    gbif_password: str = ""
    data_dir: Path = Path("../data")
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embeddings_enabled: bool = True
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")


settings = Settings()
