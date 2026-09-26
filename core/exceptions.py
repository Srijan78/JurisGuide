"""Custom exceptions for JurisGuide with safe, user-facing error reporting."""

from __future__ import annotations
from typing import Optional, Dict, Any


class JurisGuideError(Exception):
    """Base exception for all JurisGuide domain errors."""
    def __init__(self, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class InputValidationError(JurisGuideError):
    """Raised when file type, size, magic bytes, or text payload is invalid."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, status_code=400, details=details)


class FileSizeLimitExceededError(InputValidationError):
    """Raised when uploaded file exceeds 5MB limit."""
    def __init__(self, max_size_mb: float = 5.0) -> None:
        super().__init__(
            message=f"File exceeds maximum allowed upload size of {max_size_mb:.1f}MB.",
            details={"max_size_mb": max_size_mb}
        )


class SessionExpiredError(JurisGuideError):
    """Raised when an ephemeral session token has timed out or is missing."""
    def __init__(self, session_id: str) -> None:
        super().__init__(
            message="Your document session has expired or is invalid. Please re-upload your document.",
            status_code=404,
            details={"session_id": session_id}
        )


class LLMServiceError(JurisGuideError):
    """Raised when the Gemini API encounters an error or quota exhaustion."""
    DEFAULT_USER_MESSAGE: str = "The AI service was temporarily unable to process the document. Please try again."

    def __init__(
        self,
        message: Optional[str] = None,
        internal_detail: Optional[str] = None,
        status_code: int = 502,
    ) -> None:
        user_message = message or self.DEFAULT_USER_MESSAGE
        super().__init__(message=user_message, status_code=status_code)
        self.user_message = user_message
        self.internal_detail = internal_detail or ""


class SchemaExtractionError(JurisGuideError):
    """Raised when document data cannot be coerced into the required schema."""
    DEFAULT_USER_MESSAGE: str = "Failed to extract structured clauses from document. Please try again."

    def __init__(
        self,
        message: Optional[str] = None,
        internal_detail: Optional[str] = None,
        status_code: int = 422,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        user_message = message or self.DEFAULT_USER_MESSAGE
        super().__init__(message=user_message, status_code=status_code, details=details)
        self.user_message = user_message
        self.internal_detail = internal_detail or ""
