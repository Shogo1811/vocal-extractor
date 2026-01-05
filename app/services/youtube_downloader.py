"""YouTube audio download service using yt-dlp."""
import re
from pathlib import Path
from typing import Optional, Callable
import yt_dlp

from app.config import settings
from app.logging_config import logger


class YouTubeDownloaderError(Exception):
    """Custom exception for YouTube download errors."""
    pass


class YouTubeDownloader:
    """Service for downloading audio from YouTube videos."""

    # YouTube URL patterns
    YOUTUBE_PATTERNS = [
        r"^(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"^(https?://)?(www\.)?youtu\.be/[\w-]+",
        r"^(https?://)?(www\.)?youtube\.com/shorts/[\w-]+",
    ]

    def __init__(self):
        """Initialize YouTube downloader."""
        self.upload_dir = settings.upload_dir

    def validate_url(self, url: str) -> bool:
        """
        Validate if URL is a valid YouTube URL.

        Args:
            url: URL to validate

        Returns:
            True if valid YouTube URL, False otherwise
        """
        if not url:
            return False

        for pattern in self.YOUTUBE_PATTERNS:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def get_video_info(self, url: str) -> dict:
        """
        Get video information without downloading.

        Args:
            url: YouTube video URL

        Returns:
            Dictionary with video information

        Raises:
            YouTubeDownloaderError: If video info cannot be retrieved
        """
        if not self.validate_url(url):
            raise YouTubeDownloaderError("Invalid YouTube URL")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "duration": info.get("duration"),  # seconds
                    "uploader": info.get("uploader"),
                    "thumbnail": info.get("thumbnail"),
                    "description": info.get("description", "")[:500],
                }
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Video unavailable" in error_msg:
                raise YouTubeDownloaderError("Video is unavailable or private")
            elif "age" in error_msg.lower():
                raise YouTubeDownloaderError("Video is age-restricted")
            elif "copyright" in error_msg.lower():
                raise YouTubeDownloaderError("Video is blocked due to copyright")
            else:
                raise YouTubeDownloaderError(f"Failed to get video info: {error_msg}")
        except Exception as e:
            raise YouTubeDownloaderError(f"Unexpected error: {e}")

    def download_audio(
        self,
        url: str,
        job_id: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> tuple[str, dict]:
        """
        Download audio from YouTube video.

        Args:
            url: YouTube video URL
            job_id: Job ID for creating unique filename
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (file_path, video_info)

        Raises:
            YouTubeDownloaderError: If download fails
        """
        if not self.validate_url(url):
            raise YouTubeDownloaderError("Invalid YouTube URL")

        output_template = str(self.upload_dir / f"{job_id}.%(ext)s")

        def progress_hook(d):
            if d["status"] == "downloading" and progress_callback:
                if "total_bytes" in d and d["total_bytes"]:
                    progress = (d["downloaded_bytes"] / d["total_bytes"]) * 100
                    progress_callback(progress)
                elif "total_bytes_estimate" in d and d["total_bytes_estimate"]:
                    progress = (d["downloaded_bytes"] / d["total_bytes_estimate"]) * 100
                    progress_callback(progress)
            elif d["status"] == "finished" and progress_callback:
                progress_callback(100)

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            logger.info(f"Starting YouTube download: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                # Find the downloaded file
                output_path = self.upload_dir / f"{job_id}.mp3"
                if not output_path.exists():
                    # Try to find any file with the job_id
                    possible_files = list(self.upload_dir.glob(f"{job_id}.*"))
                    if possible_files:
                        output_path = possible_files[0]
                    else:
                        raise YouTubeDownloaderError("Downloaded file not found")

                video_info = {
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "duration": info.get("duration"),
                    "uploader": info.get("uploader"),
                }

                logger.info(f"YouTube download complete: {output_path}")
                return str(output_path), video_info

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            logger.error(f"YouTube download error: {error_msg}")

            if "Video unavailable" in error_msg:
                raise YouTubeDownloaderError("Video is unavailable or private")
            elif "age" in error_msg.lower():
                raise YouTubeDownloaderError("Video is age-restricted")
            elif "copyright" in error_msg.lower():
                raise YouTubeDownloaderError("Video is blocked due to copyright")
            elif "too many requests" in error_msg.lower():
                raise YouTubeDownloaderError(
                    "Too many requests. Please try again later."
                )
            else:
                raise YouTubeDownloaderError(f"Download failed: {error_msg}")
        except YouTubeDownloaderError:
            raise
        except Exception as e:
            logger.error(f"Unexpected YouTube download error: {e}")
            raise YouTubeDownloaderError(f"Unexpected error: {e}")


# Singleton instance
youtube_downloader = YouTubeDownloader()
