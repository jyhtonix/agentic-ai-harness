"""
Configuration module.

Purpose: Centralized settings management using pydantic-settings.
Loads from environment variables and .env file with typed validation.
Keeps all environment-dependent values in one place so the rest of
the codebase never reads raw env vars.

Clean architecture: This is the outermost layer — every other module
imports from here rather than from os.environ directly.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM provider configuration
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # Embedding
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # Database
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/agent_harness"

    # Vector store ("memory" or "pgvector")
    vector_store: str = "memory"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    debug: bool = False

    # Security
    api_key: str = ""
    cors_origins: list[str] = ["*"]
    rate_limit_requests: float = 10.0
    rate_limit_burst: float = 20.0
    max_request_size: int = 1_048_576

    # Monitoring
    sentry_dsn: str = ""
    json_logging: bool = False

    # Cache
    llm_cache_size: int = 500
    llm_cache_ttl: int = 3600

    # Skills System
    skills_dir: str = "skills"
    skill_cache_ttl: int = 3600
    skill_auto_load: bool = True
    skill_index_auto_build: bool = True
    skill_injection_budget: int = 2048

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
