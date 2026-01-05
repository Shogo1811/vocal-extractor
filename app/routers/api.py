"""API endpoints for vocal extraction."""
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from app.config import settings
from app.logging_config import logger
from app.models.job import (
    Job, JobType, JobStatus, JobResponse, UploadResponse,
    YouTubeRequest, ErrorResponse
)
from app.services.file_processor import file_processor, FileProcessorError
from app.services.youtube_downloader import youtube_downloader, YouTubeDownloaderError
from app.services.job_manager import job_manager, JobManagerError


router = APIRouter(prefix="/api", tags=["API"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload audio file for vocal extraction.

    - Accepts MP3, WAV, M4A, FLAC formats
    - Max file size: 50MB
    - Returns job ID for tracking progress
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file_processor.validate_file_format(file.filename):
        supported = ", ".join(settings.supported_formats)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Supported: {supported}"
        )

    # Create job
    job = job_manager.create_job(
        job_type=JobType.FILE_UPLOAD,
        input_filename=file.filename
    )

    try:
        # Save uploaded file
        file_path, file_size = await file_processor.save_upload_file(
            file, job.job_id
        )
        job.input_file_path = file_path

        # Start processing in background
        background_tasks.add_task(
            job_manager.process_file_upload,
            job.job_id,
            file_path
        )

        return UploadResponse(
            job_id=job.job_id,
            message="File uploaded successfully. Processing started.",
            filename=file.filename
        )

    except FileProcessorError as e:
        job_manager.set_job_error(job.job_id, str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload error: {e}")
        job_manager.set_job_error(job.job_id, "Upload failed")
        raise HTTPException(status_code=500, detail="Upload failed")


@router.post("/youtube", response_model=UploadResponse)
async def process_youtube(
    background_tasks: BackgroundTasks,
    request: YouTubeRequest
):
    """
    Process YouTube URL for vocal extraction.

    - Accepts valid YouTube video URLs
    - Downloads audio and extracts vocals
    - Returns job ID for tracking progress
    """
    # Validate URL
    if not youtube_downloader.validate_url(request.url):
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL"
        )

    # Create job
    job = job_manager.create_job(
        job_type=JobType.YOUTUBE_DOWNLOAD,
        input_url=request.url
    )

    try:
        # Get video info first (quick validation)
        video_info = youtube_downloader.get_video_info(request.url)
        job.input_filename = video_info.get("title", "youtube_audio")

        # Start processing in background
        background_tasks.add_task(
            job_manager.process_youtube_download,
            job.job_id,
            request.url
        )

        return UploadResponse(
            job_id=job.job_id,
            message="YouTube processing started.",
            filename=video_info.get("title", "youtube_audio")
        )

    except YouTubeDownloaderError as e:
        job_manager.set_job_error(job.job_id, str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"YouTube processing error: {e}")
        job_manager.set_job_error(job.job_id, "Processing failed")
        raise HTTPException(status_code=500, detail="Processing failed")


@router.get("/status/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """
    Get job processing status.

    - Returns current status and progress
    - Includes download URL when complete
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = JobResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
    )

    if job.status == JobStatus.COMPLETED:
        response.download_url = f"/api/download/{job_id}"
        response.preview_url = f"/api/preview/{job_id}"
        response.message = "Processing complete"
    elif job.status == JobStatus.FAILED:
        response.error = job.error_message
        response.message = "Processing failed"
    elif job.status == JobStatus.PROCESSING:
        response.message = "Extracting vocals..."
    elif job.status == JobStatus.DOWNLOADING:
        response.message = "Downloading from YouTube..."
    else:
        response.message = "Waiting to process..."

    return response


@router.get("/download/{job_id}")
async def download_vocal(job_id: str):
    """
    Download extracted vocal file.

    - Only available for completed jobs
    - Returns WAV file
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Job not yet completed"
        )

    if not job.output_file_path:
        raise HTTPException(
            status_code=404,
            detail="Output file not found"
        )

    output_path = Path(job.output_file_path)
    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Output file not found"
        )

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(
        c for c in (job.input_filename or "audio")
        if c.isalnum() or c in "._- "
    )[:50]
    filename = f"{safe_name}_vocals_{timestamp}.wav"

    return FileResponse(
        path=str(output_path),
        filename=filename,
        media_type="audio/wav"
    )


@router.get("/preview/{job_id}")
async def preview_vocal(job_id: str):
    """
    Stream preview of extracted vocal.

    - Limited to first 30 seconds
    - Only available for completed jobs
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Job not yet completed"
        )

    if not job.output_file_path:
        raise HTTPException(
            status_code=404,
            detail="Output file not found"
        )

    output_path = Path(job.output_file_path)
    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Output file not found"
        )

    # Create or return preview file
    preview_path = output_path.parent / f"{job_id}_preview.wav"

    if not preview_path.exists():
        try:
            file_processor.create_preview(
                str(output_path),
                str(preview_path),
                settings.preview_duration_seconds
            )
        except FileProcessorError as e:
            raise HTTPException(status_code=500, detail=str(e))

    return FileResponse(
        path=str(preview_path),
        media_type="audio/wav"
    )


@router.get("/stats")
async def get_stats() -> dict:
    """Get job processing statistics."""
    return job_manager.get_stats()
