"""File cleanup service for automatic file expiration."""
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
import os

from app.config import settings
from app.logging_config import logger


class CleanupService:
    """Service for cleaning up expired files automatically."""

    def __init__(self):
        """Initialize cleanup service."""
        self.upload_dir = settings.upload_dir
        self.output_dir = settings.output_dir
        self.expiry_hours = settings.file_expiry_hours
        self._cleanup_task = None
        self._running = False

    def get_expired_files(self, directory: Path) -> List[Path]:
        """
        Get list of expired files in directory.

        Args:
            directory: Directory to scan

        Returns:
            List of expired file paths
        """
        expired_files = []
        expiry_threshold = datetime.now() - timedelta(hours=self.expiry_hours)

        if not directory.exists():
            return expired_files

        for item in directory.iterdir():
            try:
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime < expiry_threshold:
                    expired_files.append(item)
            except (OSError, IOError) as e:
                logger.warning(f"Cannot check file {item}: {e}")

        return expired_files

    def cleanup_file(self, file_path: Path) -> bool:
        """
        Delete a single file or directory.

        Args:
            file_path: Path to delete

        Returns:
            True if deleted successfully
        """
        try:
            if file_path.is_dir():
                # Recursively delete directory
                import shutil
                shutil.rmtree(file_path)
                logger.info(f"Deleted directory: {file_path}")
            else:
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")
            return True
        except (OSError, IOError) as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            return False

    def run_cleanup(self) -> dict:
        """
        Run cleanup process for all temp directories.

        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            "upload_deleted": 0,
            "output_deleted": 0,
            "errors": 0,
            "timestamp": datetime.now().isoformat()
        }

        # Cleanup upload directory
        for file_path in self.get_expired_files(self.upload_dir):
            if self.cleanup_file(file_path):
                stats["upload_deleted"] += 1
            else:
                stats["errors"] += 1

        # Cleanup output directory
        for file_path in self.get_expired_files(self.output_dir):
            if self.cleanup_file(file_path):
                stats["output_deleted"] += 1
            else:
                stats["errors"] += 1

        total_deleted = stats["upload_deleted"] + stats["output_deleted"]
        if total_deleted > 0:
            logger.info(
                f"Cleanup complete: {total_deleted} items deleted, "
                f"{stats['errors']} errors"
            )

        return stats

    async def start_background_cleanup(self, interval_hours: float = 1.0):
        """
        Start background cleanup task.

        Args:
            interval_hours: Interval between cleanup runs in hours
        """
        if self._running:
            logger.warning("Cleanup task already running")
            return

        self._running = True
        interval_seconds = interval_hours * 3600

        async def cleanup_loop():
            while self._running:
                try:
                    await asyncio.sleep(interval_seconds)
                    if self._running:
                        self.run_cleanup()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Cleanup task error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started background cleanup (interval: {interval_hours}h)")

    async def stop_background_cleanup(self):
        """Stop background cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped background cleanup")

    def get_storage_stats(self) -> dict:
        """
        Get storage usage statistics.

        Returns:
            Dictionary with storage stats
        """
        def get_dir_size(directory: Path) -> tuple:
            """Get total size and file count of directory."""
            total_size = 0
            file_count = 0

            if not directory.exists():
                return 0, 0

            for item in directory.rglob('*'):
                if item.is_file():
                    try:
                        total_size += item.stat().st_size
                        file_count += 1
                    except (OSError, IOError):
                        pass

            return total_size, file_count

        upload_size, upload_count = get_dir_size(self.upload_dir)
        output_size, output_count = get_dir_size(self.output_dir)

        return {
            "upload": {
                "size_bytes": upload_size,
                "size_mb": round(upload_size / (1024 * 1024), 2),
                "file_count": upload_count,
            },
            "output": {
                "size_bytes": output_size,
                "size_mb": round(output_size / (1024 * 1024), 2),
                "file_count": output_count,
            },
            "total": {
                "size_bytes": upload_size + output_size,
                "size_mb": round((upload_size + output_size) / (1024 * 1024), 2),
                "file_count": upload_count + output_count,
            },
            "expiry_hours": self.expiry_hours,
        }


# Singleton instance
cleanup_service = CleanupService()
