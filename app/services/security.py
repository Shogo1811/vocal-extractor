"""Security utilities for input validation and sanitization."""
import re
import html
from pathlib import Path
from typing import Optional
import magic

from app.logging_config import logger


class SecurityError(Exception):
    """Custom exception for security-related errors."""
    pass


class SecurityValidator:
    """Service for validating and sanitizing user inputs."""

    # Allowed MIME types for audio files
    ALLOWED_MIME_TYPES = {
        'audio/mpeg',           # MP3
        'audio/mp3',            # MP3 alternative
        'audio/wav',            # WAV
        'audio/x-wav',          # WAV alternative
        'audio/wave',           # WAV alternative
        'audio/x-m4a',          # M4A
        'audio/mp4',            # M4A/MP4
        'audio/x-flac',         # FLAC
        'audio/flac',           # FLAC alternative
    }

    # Dangerous file patterns
    DANGEROUS_PATTERNS = [
        b'<%',              # ASP
        b'<?php',           # PHP
        b'<script',         # JavaScript
        b'#!/',             # Shell scripts
        b'PK\x03\x04',      # ZIP (potentially malicious)
    ]

    def __init__(self):
        """Initialize security validator."""
        self._magic = None
        try:
            self._magic = magic.Magic(mime=True)
        except Exception as e:
            logger.warning(f"python-magic not available: {e}")

    def validate_file_content(self, file_path: str) -> bool:
        """
        Validate file content is actually an audio file.

        Args:
            file_path: Path to file to validate

        Returns:
            True if file is valid audio

        Raises:
            SecurityError: If file is potentially malicious
        """
        path = Path(file_path)
        if not path.exists():
            raise SecurityError("File not found")

        # Check MIME type if magic is available
        if self._magic:
            try:
                mime_type = self._magic.from_file(str(path))
                if mime_type not in self.ALLOWED_MIME_TYPES:
                    logger.warning(
                        f"Invalid MIME type: {mime_type} for {file_path}"
                    )
                    raise SecurityError(
                        f"Invalid file type: {mime_type}. "
                        "Only audio files are allowed."
                    )
            except magic.MagicException as e:
                logger.warning(f"MIME detection failed: {e}")

        # Check for dangerous patterns in file header
        try:
            with open(path, 'rb') as f:
                header = f.read(1024)

            for pattern in self.DANGEROUS_PATTERNS:
                if pattern in header:
                    logger.error(
                        f"Dangerous pattern detected in {file_path}"
                    )
                    raise SecurityError(
                        "File contains potentially malicious content"
                    )
        except IOError as e:
            raise SecurityError(f"Cannot read file: {e}")

        return True

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and special characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        if not filename:
            return "unnamed"

        # Remove path components
        filename = Path(filename).name

        # Remove null bytes
        filename = filename.replace('\x00', '')

        # Remove/replace dangerous characters
        # Keep only alphanumeric, dots, underscores, hyphens, spaces
        sanitized = re.sub(r'[^\w.\-\s]', '_', filename)

        # Prevent hidden files
        sanitized = sanitized.lstrip('.')

        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            sanitized = f"{name[:250]}.{ext}" if ext else name[:255]

        return sanitized or "unnamed"

    def sanitize_url(self, url: str) -> str:
        """
        Sanitize URL input.

        Args:
            url: URL to sanitize

        Returns:
            Sanitized URL

        Raises:
            SecurityError: If URL is invalid or potentially malicious
        """
        if not url:
            raise SecurityError("URL is required")

        # Strip whitespace
        url = url.strip()

        # Check for dangerous protocols
        dangerous_protocols = ['javascript:', 'data:', 'vbscript:', 'file:']
        url_lower = url.lower()
        for protocol in dangerous_protocols:
            if url_lower.startswith(protocol):
                raise SecurityError(f"Dangerous protocol: {protocol}")

        # Ensure HTTPS or HTTP
        if not url_lower.startswith(('http://', 'https://')):
            # Add https if no protocol
            if url_lower.startswith('www.') or url_lower.startswith('youtube.') or url_lower.startswith('youtu.be'):
                url = 'https://' + url
            else:
                raise SecurityError("Invalid URL protocol")

        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )

        if not url_pattern.match(url):
            raise SecurityError("Invalid URL format")

        return url

    def sanitize_text(self, text: str, max_length: int = 1000) -> str:
        """
        Sanitize text input for XSS prevention.

        Args:
            text: Text to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Truncate
        text = text[:max_length]

        # HTML escape
        text = html.escape(text)

        # Remove null bytes
        text = text.replace('\x00', '')

        return text

    def validate_job_id(self, job_id: str) -> bool:
        """
        Validate job ID format to prevent injection.

        Args:
            job_id: Job ID to validate

        Returns:
            True if valid

        Raises:
            SecurityError: If job ID is invalid
        """
        if not job_id:
            raise SecurityError("Job ID is required")

        # UUID format validation
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )

        if not uuid_pattern.match(job_id):
            raise SecurityError("Invalid job ID format")

        return True


# Singleton instance
security_validator = SecurityValidator()
