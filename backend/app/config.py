from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    upload_dir: Path = Path("./uploads")
    max_file_size_mb: int = 50
    max_files_per_batch: int = 500
    workers: int = 4
    ocr_space_api_key: str = ""
    # LLM gap-fill (optional): set ANTHROPIC_API_KEY in .env to enable
    anthropic_api_key: str = ""
    llm_confidence_threshold: float = 0.83
    llm_model: str = "claude-haiku-4-5-20251001"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
