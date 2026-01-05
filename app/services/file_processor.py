"""File processing service for audio file handling."""
import os
import shutil
from pathlib import Path
from typing import Optional
import aiofiles
from fastapi import UploadFile
from pydub import AudioSegment

from app.config import settings
from app.logging_config import logger
from app.models.job import AudioFileInfo


class FileProcessorError(Exception):
    """Custom exception for file processing errors."""
    pass


class FileProcessor:
    """Service for processing audio files."""

    SUPPORTED_FORMATS = settings.supported_formats
    MAX_FILE_SIZE = settings.max_file_size_bytes

    def __init__(self):
        """Initialize file processor."""
        self.upload_dir = settings.upload_dir
        self.output_dir = settings.output_dir

    def validate_file_format(self, filename: str) -> bool:
        """
        Validate if file format is supported.

        Args:
            filename: Name of the file to validate

        Returns:
            True if format is supported, False otherwise
        """
        if not filename:
            return False
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return extension in self.SUPPORTED_FORMATS

    def validate_file_size(self, file_size: int) -> bool:
        """
        Validate if file size is within limits.

        Args:
            file_size: Size of file in bytes

        Returns:
            True if size is within limits, False otherwise
        """
        return 0 < file_size <= self.MAX_FILE_SIZE

    def get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    async def save_upload_file(
        self,
        file: UploadFile,
        job_id: str
    ) -> tuple[str, int]:
        """
        Save uploaded file to disk.

        Args:
            file: Uploaded file object
            job_id: Job ID for creating unique filename

        Returns:
            Tuple of (file_path, file_size)

        Raises:
            FileProcessorError: If file validation fails
        """
        # Validate format
        if not self.validate_file_format(file.filename):
            supported = ", ".join(self.SUPPORTED_FORMATS)
            raise FileProcessorError(
                f"Unsupported file format. Supported formats: {supported}"
            )

        # Create unique filename
        extension = self.get_file_extension(file.filename)
        safe_filename = f"{job_id}.{extension}"
        file_path = self.upload_dir / safe_filename

        # Read and validate size
        content = await file.read()
        file_size = len(content)

        if not self.validate_file_size(file_size):
            raise FileProcessorError(
                f"File size exceeds limit of {settings.max_file_size_mb}MB"
            )

        # Save file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        logger.info(f"Saved uploaded file: {file_path} ({file_size} bytes)")
        return str(file_path), file_size

    def get_audio_info(self, file_path: str) -> AudioFileInfo:
        """
        Get audio file information.

        Args:
            file_path: Path to audio file

        Returns:
            AudioFileInfo object with file details
        """
        path = Path(file_path)
        if not path.exists():
            raise FileProcessorError(f"File not found: {file_path}")

        extension = path.suffix.lower().lstrip(".")
        file_size = path.stat().st_size

        # Load audio to get duration and other info
        try:
            audio = AudioSegment.from_file(file_path)
            duration = len(audio) / 1000.0  # Convert ms to seconds
            sample_rate = audio.frame_rate
            channels = audio.channels
        except Exception as e:
            logger.warning(f"Could not read audio metadata: {e}")
            duration = None
            sample_rate = None
            channels = None

        return AudioFileInfo(
            filename=path.name,
            file_path=str(path),
            file_size=file_size,
            duration=duration,
            format=extension,
            sample_rate=sample_rate,
            channels=channels
        )

    def convert_to_wav(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Convert audio file to WAV format.

        Args:
            input_path: Path to input audio file
            output_path: Optional output path (auto-generated if not provided)

        Returns:
            Path to converted WAV file
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileProcessorError(f"Input file not found: {input_path}")

        if output_path is None:
            output_path = input_path.with_suffix(".wav")
        else:
            output_path = Path(output_path)

        try:
            audio = AudioSegment.from_file(str(input_path))
            audio.export(
                str(output_path),
                format="wav",
                parameters=["-ar", str(settings.output_sample_rate)]
            )
            logger.info(f"Converted audio to WAV: {output_path}")
            return str(output_path)
        except Exception as e:
            raise FileProcessorError(f"Failed to convert audio: {e}")

    def create_preview(
        self,
        input_path: str,
        output_path: str,
        duration_seconds: Optional[int] = None
    ) -> str:
        """
        Create a preview clip of audio file.

        Args:
            input_path: Path to input audio file
            output_path: Path for output preview file
            duration_seconds: Preview duration in seconds (default from settings)

        Returns:
            Path to preview file
        """
        if duration_seconds is None:
            duration_seconds = settings.preview_duration_seconds

        input_path = Path(input_path)
        if not input_path.exists():
            raise FileProcessorError(f"Input file not found: {input_path}")

        try:
            audio = AudioSegment.from_file(str(input_path))
            # Get first N seconds
            preview_ms = duration_seconds * 1000
            preview_audio = audio[:preview_ms]
            preview_audio.export(str(output_path), format="wav")
            logger.info(f"Created preview: {output_path} ({duration_seconds}s)")
            return str(output_path)
        except Exception as e:
            raise FileProcessorError(f"Failed to create preview: {e}")

    def cleanup_file(self, file_path: str) -> bool:
        """
        Delete a file from disk.

        Args:
            file_path: Path to file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    def cleanup_job_files(self, job_id: str) -> int:
        """
        Clean up all files associated with a job.

        Args:
            job_id: Job ID to clean up

        Returns:
            Number of files deleted
        """
        deleted_count = 0

        # Clean upload directory
        for file_path in self.upload_dir.glob(f"{job_id}*"):
            if self.cleanup_file(str(file_path)):
                deleted_count += 1

        # Clean output directory
        for file_path in self.output_dir.glob(f"{job_id}*"):
            if self.cleanup_file(str(file_path)):
                deleted_count += 1

        # Clean job-specific output directory if exists
        job_output_dir = self.output_dir / job_id
        if job_output_dir.exists():
            shutil.rmtree(job_output_dir)
            deleted_count += 1
            logger.info(f"Deleted job output directory: {job_output_dir}")

        return deleted_count


# Singleton instance
file_processor = FileProcessor()
