"""Job and processing related models."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class JobStatus(str, Enum):
    """Job processing status."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    """Type of job."""
    FILE_UPLOAD = "file_upload"
    YOUTUBE_DOWNLOAD = "youtube_download"


class Job(BaseModel):
    """Processing job model."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # Input information
    input_filename: Optional[str] = None
    input_url: Optional[str] = None
    input_file_path: Optional[str] = None

    # Output information
    output_file_path: Optional[str] = None
    output_filename: Optional[str] = None

    # Error information
    error_message: Optional[str] = None
    error_details: Optional[str] = None

    # Processing information
    estimated_duration: Optional[float] = None
    processing_time: Optional[float] = None

    def update_status(self, status: JobStatus, progress: float = None) -> None:
        """Update job status and progress."""
        self.status = status
        self.updated_at = datetime.now()
        if progress is not None:
            self.progress = progress
        if status == JobStatus.COMPLETED:
            self.completed_at = datetime.now()
            self.progress = 100.0

    def set_error(self, message: str, details: str = None) -> None:
        """Set job error state."""
        self.status = JobStatus.FAILED
        self.error_message = message
        self.error_details = details
        self.updated_at = datetime.now()


class AudioFileInfo(BaseModel):
    """Audio file information model."""
    filename: str
    file_path: str
    file_size: int  # bytes
    duration: Optional[float] = None  # seconds
    format: str
    sample_rate: Optional[int] = None
    channels: Optional[int] = None


class ProcessingResult(BaseModel):
    """Processing result model."""
    job_id: str
    original_file: AudioFileInfo
    vocal_file: AudioFileInfo
    processing_time: float  # seconds
    download_url: str
    preview_url: str
    expires_at: datetime


class JobResponse(BaseModel):
    """API response for job status."""
    job_id: str
    status: JobStatus
    progress: float
    message: Optional[str] = None
    download_url: Optional[str] = None
    preview_url: Optional[str] = None
    error: Optional[str] = None


class UploadResponse(BaseModel):
    """API response for file upload."""
    job_id: str
    message: str
    filename: str


class YouTubeRequest(BaseModel):
    """Request model for YouTube processing."""
    url: str = Field(..., description="YouTube video URL")


class ErrorResponse(BaseModel):
    """Error response model."""
    error_code: str
    message: str
    details: Optional[str] = None
    suggested_action: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
