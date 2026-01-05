"""Application configuration settings."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    app_name: str = "Vocal Extractor"
    debug: bool = False

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    temp_dir: Path = base_dir / "temp"
    upload_dir: Path = temp_dir / "uploads"
    output_dir: Path = temp_dir / "outputs"

    # File limits
    max_file_size_mb: int = 50
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50MB
    supported_formats: list[str] = ["mp3", "wav", "m4a", "flac"]

    # Processing
    max_concurrent_jobs: int = 3
    job_timeout_seconds: int = 600  # 10 minutes
    file_expiry_hours: int = 24
    preview_duration_seconds: int = 30

    # Audio output
    output_format: str = "wav"
    output_sample_rate: int = 44100

    # Demucs model
    demucs_model: str = "htdemucs"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
