from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ExpertiseGraph"
    api_prefix: str = "/api"

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "fulcrumgraph"
    neo4j_database: str = "neo4j"

    # xAI Grok — also accepts GROK_API_KEY
    xai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("XAI_API_KEY", "GROK_API_KEY", "xai_api_key"),
    )
    llm_model: str = "grok-3-mini"

    token_chunk_size: int = 400
    chunk_overlap: int = 40
    max_chunks_per_doc: int = 40
    vector_top_k: int = 8
    graph_hop_depth: int = 2

    chunks_to_combine: int = 1
    upload_dir: Path = Path("/app/uploads")
    sample_docs_dir: Path = Path("/app/sample_docs")


@lru_cache
def get_settings() -> Settings:
    return Settings()
