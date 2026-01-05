"""Vocal extraction service using Demucs."""
import shutil
from pathlib import Path
from typing import Optional, Callable
import subprocess
import threading

from app.config import settings
from app.logging_config import logger


class VocalExtractorError(Exception):
    """Custom exception for vocal extraction errors."""
    pass


class VocalExtractor:
    """Service for extracting vocals from audio using Demucs."""

    def __init__(self):
        """Initialize vocal extractor."""
        self.output_dir = settings.output_dir
        # htdemucs is the recommended model for vocal separation
        self.model = "htdemucs"

    def extract_vocals(
        self,
        input_path: str,
        job_id: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> str:
        """
        Extract vocals from audio file using Demucs.

        Args:
            input_path: Path to input audio file
            job_id: Job ID for output directory naming
            progress_callback: Optional callback for progress updates

        Returns:
            Path to extracted vocal file

        Raises:
            VocalExtractorError: If extraction fails
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise VocalExtractorError(f"Input file not found: {input_path}")

        # Create job-specific output directory
        job_output_dir = self.output_dir / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting vocal extraction with Demucs: {input_path}")
        if progress_callback:
            progress_callback(10)

        try:
            # Run demucs separation
            # --two-stems=vocals extracts only vocals and accompaniment
            cmd = [
                "python", "-m", "demucs",
                "--two-stems", "vocals",
                "-n", self.model,
                "-o", str(job_output_dir),
                str(input_path)
            ]

            logger.debug(f"Running command: {' '.join(cmd)}")

            if progress_callback:
                progress_callback(20)

            # Run demucs
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Monitor progress
            if progress_callback:
                self._simulate_progress(process, progress_callback, 20, 90)

            stdout, stderr = process.communicate(timeout=600)  # 10 minute timeout

            if process.returncode != 0:
                logger.error(f"Demucs error: {stderr}")
                raise VocalExtractorError(f"Demucs failed: {stderr}")

            if progress_callback:
                progress_callback(90)

            # Find the vocal file
            # Demucs output structure: {output_dir}/{model}/{input_stem}/vocals.wav
            input_stem = input_path.stem
            demucs_output_dir = job_output_dir / self.model / input_stem

            vocal_file = demucs_output_dir / "vocals.wav"
            if not vocal_file.exists():
                # Try alternative locations
                possible_files = list(job_output_dir.rglob("vocals.wav"))
                if possible_files:
                    vocal_file = possible_files[0]
                else:
                    raise VocalExtractorError("Vocal file not found in output")

            # Move vocal file to a cleaner location
            final_output_path = job_output_dir / f"{job_id}_vocals.wav"
            shutil.move(str(vocal_file), str(final_output_path))

            # Clean up demucs subdirectories
            model_dir = job_output_dir / self.model
            if model_dir.exists():
                shutil.rmtree(model_dir)

            if progress_callback:
                progress_callback(100)

            logger.info(f"Vocal extraction complete: {final_output_path}")
            return str(final_output_path)

        except subprocess.TimeoutExpired:
            process.kill()
            raise VocalExtractorError("Processing timed out (10 minutes)")
        except VocalExtractorError:
            raise
        except Exception as e:
            logger.error(f"Vocal extraction error: {e}")
            raise VocalExtractorError(f"Extraction failed: {e}")

    def _simulate_progress(
        self,
        process: subprocess.Popen,
        callback: Callable[[float], None],
        start_progress: float,
        end_progress: float
    ):
        """
        Simulate progress updates while demucs is running.

        Args:
            process: Running subprocess
            callback: Progress callback function
            start_progress: Starting progress percentage
            end_progress: Ending progress percentage
        """
        import time

        def update_progress():
            progress = start_progress
            increment = (end_progress - start_progress) / 30  # 30 steps

            while process.poll() is None and progress < end_progress:
                time.sleep(2)
                progress = min(progress + increment, end_progress - 5)
                callback(progress)

        thread = threading.Thread(target=update_progress)
        thread.daemon = True
        thread.start()


# Singleton instance
vocal_extractor = VocalExtractor()
