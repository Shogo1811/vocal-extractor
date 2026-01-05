"""Job management service for handling processing tasks."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable
from collections import deque
import threading

from app.config import settings
from app.logging_config import logger
from app.models.job import Job, JobStatus, JobType
from app.services.file_processor import file_processor, FileProcessorError
from app.services.youtube_downloader import youtube_downloader, YouTubeDownloaderError
from app.services.vocal_extractor import vocal_extractor, VocalExtractorError


class JobManagerError(Exception):
    """Custom exception for job manager errors."""
    pass


class JobManager:
    """Service for managing processing jobs with queuing support."""

    def __init__(self):
        """Initialize job manager."""
        self._jobs: dict[str, Job] = {}
        self._processing_queue: deque = deque()
        self._active_jobs: int = 0
        self._max_concurrent = settings.max_concurrent_jobs
        self._lock = threading.Lock()

    def create_job(self, job_type: JobType, **kwargs) -> Job:
        """
        Create a new processing job.

        Args:
            job_type: Type of job (file upload or YouTube download)
            **kwargs: Additional job parameters

        Returns:
            Created Job object
        """
        job = Job(job_type=job_type, **kwargs)
        with self._lock:
            self._jobs[job.job_id] = job
        logger.info(f"Created job: {job.job_id} ({job_type.value})")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID.

        Args:
            job_id: Job ID to retrieve

        Returns:
            Job object or None if not found
        """
        return self._jobs.get(job_id)

    def update_job_progress(self, job_id: str, progress: float) -> None:
        """
        Update job progress.

        Args:
            job_id: Job ID to update
            progress: Progress percentage (0-100)
        """
        job = self.get_job(job_id)
        if job:
            job.progress = min(max(progress, 0), 100)
            job.updated_at = datetime.now()

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[float] = None
    ) -> None:
        """
        Update job status.

        Args:
            job_id: Job ID to update
            status: New job status
            progress: Optional progress percentage
        """
        job = self.get_job(job_id)
        if job:
            job.update_status(status, progress)
            logger.info(f"Job {job_id} status: {status.value}")

    def set_job_error(
        self,
        job_id: str,
        message: str,
        details: Optional[str] = None
    ) -> None:
        """
        Set job to error state.

        Args:
            job_id: Job ID to update
            message: Error message
            details: Optional error details
        """
        job = self.get_job(job_id)
        if job:
            job.set_error(message, details)
            logger.error(f"Job {job_id} failed: {message}")

    def set_job_output(self, job_id: str, output_path: str) -> None:
        """
        Set job output file path.

        Args:
            job_id: Job ID to update
            output_path: Path to output file
        """
        job = self.get_job(job_id)
        if job:
            job.output_file_path = output_path
            job.output_filename = output_path.split("/")[-1]

    def get_queue_position(self, job_id: str) -> int:
        """
        Get job position in queue.

        Args:
            job_id: Job ID to check

        Returns:
            Queue position (0 if not in queue or processing)
        """
        try:
            return list(self._processing_queue).index(job_id) + 1
        except ValueError:
            return 0

    def get_estimated_wait_time(self, job_id: str) -> Optional[float]:
        """
        Get estimated wait time for queued job.

        Args:
            job_id: Job ID to check

        Returns:
            Estimated wait time in seconds or None
        """
        position = self.get_queue_position(job_id)
        if position > 0:
            # Rough estimate: 3 minutes per job
            return position * 180
        return None

    def can_start_job(self) -> bool:
        """Check if a new job can be started."""
        with self._lock:
            return self._active_jobs < self._max_concurrent

    def _increment_active(self) -> None:
        """Increment active job count."""
        with self._lock:
            self._active_jobs += 1

    def _decrement_active(self) -> None:
        """Decrement active job count."""
        with self._lock:
            self._active_jobs = max(0, self._active_jobs - 1)

    async def process_file_upload(
        self,
        job_id: str,
        file_path: str
    ) -> str:
        """
        Process uploaded file for vocal extraction.

        Args:
            job_id: Job ID
            file_path: Path to uploaded file

        Returns:
            Path to extracted vocal file
        """
        try:
            self._increment_active()
            self.update_job_status(job_id, JobStatus.PROCESSING, 0)

            def progress_callback(progress: float):
                self.update_job_progress(job_id, progress)

            # Run vocal extraction in thread pool
            loop = asyncio.get_event_loop()
            output_path = await loop.run_in_executor(
                None,
                vocal_extractor.extract_vocals,
                file_path,
                job_id,
                progress_callback
            )

            self.set_job_output(job_id, output_path)
            self.update_job_status(job_id, JobStatus.COMPLETED, 100)

            # Set processing time
            job = self.get_job(job_id)
            if job:
                job.processing_time = (
                    datetime.now() - job.created_at
                ).total_seconds()

            return output_path

        except VocalExtractorError as e:
            self.set_job_error(job_id, str(e))
            raise JobManagerError(str(e))
        except Exception as e:
            self.set_job_error(job_id, "Processing failed", str(e))
            raise JobManagerError(f"Processing failed: {e}")
        finally:
            self._decrement_active()

    async def process_youtube_download(
        self,
        job_id: str,
        url: str
    ) -> str:
        """
        Process YouTube URL for vocal extraction.

        Args:
            job_id: Job ID
            url: YouTube video URL

        Returns:
            Path to extracted vocal file
        """
        try:
            self._increment_active()
            self.update_job_status(job_id, JobStatus.DOWNLOADING, 0)

            # Download progress callback
            def download_progress(progress: float):
                # Download is 0-40% of total progress
                self.update_job_progress(job_id, progress * 0.4)

            # Download audio
            loop = asyncio.get_event_loop()
            file_path, video_info = await loop.run_in_executor(
                None,
                youtube_downloader.download_audio,
                url,
                job_id,
                download_progress
            )

            # Update job with input info
            job = self.get_job(job_id)
            if job:
                job.input_file_path = file_path
                job.input_filename = video_info.get("title", "youtube_audio")

            # Now process for vocal extraction
            self.update_job_status(job_id, JobStatus.PROCESSING, 40)

            def extraction_progress(progress: float):
                # Extraction is 40-100% of total progress
                total_progress = 40 + (progress * 0.6)
                self.update_job_progress(job_id, total_progress)

            output_path = await loop.run_in_executor(
                None,
                vocal_extractor.extract_vocals,
                file_path,
                job_id,
                extraction_progress
            )

            self.set_job_output(job_id, output_path)
            self.update_job_status(job_id, JobStatus.COMPLETED, 100)

            # Set processing time
            job = self.get_job(job_id)
            if job:
                job.processing_time = (
                    datetime.now() - job.created_at
                ).total_seconds()

            return output_path

        except YouTubeDownloaderError as e:
            self.set_job_error(job_id, str(e))
            raise JobManagerError(str(e))
        except VocalExtractorError as e:
            self.set_job_error(job_id, str(e))
            raise JobManagerError(str(e))
        except Exception as e:
            self.set_job_error(job_id, "Processing failed", str(e))
            raise JobManagerError(f"Processing failed: {e}")
        finally:
            self._decrement_active()

    def cleanup_expired_jobs(self) -> int:
        """
        Clean up expired jobs and their files.

        Returns:
            Number of jobs cleaned up
        """
        expiry_threshold = datetime.now() - timedelta(
            hours=settings.file_expiry_hours
        )
        cleaned_count = 0

        with self._lock:
            expired_jobs = [
                job_id for job_id, job in self._jobs.items()
                if job.created_at < expiry_threshold
                and job.status in [JobStatus.COMPLETED, JobStatus.FAILED]
            ]

            for job_id in expired_jobs:
                # Clean up files
                file_processor.cleanup_job_files(job_id)
                # Remove job from memory
                del self._jobs[job_id]
                cleaned_count += 1
                logger.info(f"Cleaned up expired job: {job_id}")

        return cleaned_count

    def get_stats(self) -> dict:
        """Get job manager statistics."""
        with self._lock:
            status_counts = {}
            for job in self._jobs.values():
                status = job.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "total_jobs": len(self._jobs),
                "active_jobs": self._active_jobs,
                "queued_jobs": len(self._processing_queue),
                "max_concurrent": self._max_concurrent,
                "status_counts": status_counts,
            }


# Singleton instance
job_manager = JobManager()
