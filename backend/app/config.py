from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    upload_dir: Path = Path("./uploads")
    max_file_size_mb: int = 50
    max_files_per_batch: int = 500
    workers: int = 4
    ocr_space_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
