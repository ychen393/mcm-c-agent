from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore', case_sensitive=False)
    app_env: str = 'development'
    app_name: str = 'MCM C Research Lab'
    log_level: str = 'INFO'
    llm_provider: Literal['openai', 'deepseek', 'anthropic'] = 'deepseek'
    llm_model: str = 'replace-with-model-id'
    llm_base_url: str | None = 'https://api.deepseek.com'
    llm_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    deepseek_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    database_url: str = 'postgresql+psycopg://mcm:mcm_dev_password@localhost:5432/mcm_research'
    checkpoint_database_url: str | None = None
    # ``auto`` prefers Postgres and falls back to local; ``local`` / ``postgres`` force a backend.
    project_store_backend: Literal['auto', 'local', 'postgres'] = 'auto'
    # Phase 2 Problem Analyst: keep LLM extraction off by default for CI.
    problem_analyst_use_llm: bool = False
    upload_dir: Path = Path('./data/uploads')
    output_dir: Path = Path('./outputs')
    @model_validator(mode='after')
    def normalize_paths(self):
        self.upload_dir.mkdir(parents=True, exist_ok=True); self.output_dir.mkdir(parents=True, exist_ok=True); return self
    def provider_api_key(self) -> SecretStr | None:
        if self.llm_api_key: return self.llm_api_key
        return {'openai': self.openai_api_key, 'deepseek': self.deepseek_api_key, 'anthropic': self.anthropic_api_key}[self.llm_provider]

@lru_cache
def get_settings() -> Settings: return Settings()
