"""Rigorous input validation for document uploads and pasted text.

Enforces:
- File size caps (<= 5MB)
- Non-empty payload verification
- Content-based magic bytes detection to prevent file extension spoofing
- Allow-list enforcement: PDF, JPG, JPEG, DOCX, TXT
"""

from __future__ import annotations

import io
import zipfile
from typing import Tuple
from core.config import settings
from core.exceptions import InputValidationError, FileSizeLimitExceededError


# Magic byte signatures
PDF_MAGIC = b"%PDF"
JPEG_MAGIC = b"\xff\xd8\xff"
ZIP_MAGIC = b"PK\x03\x04"


def validate_file_payload(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    """Validate raw uploaded file content against size, emptiness, and magic bytes.

    Args:
        file_bytes: The raw byte content of the uploaded file.
        filename: Original name of the uploaded file.

    Returns:
        Tuple of (mime_type: str, normalized_extension: str)

    Raises:
        FileSizeLimitExceededError: If file exceeds 5MB limit.
        InputValidationError: If file is empty, has an unallowed extension,
                              or fails magic byte inspection.
    """
    if not file_bytes or len(file_bytes) == 0:
        raise InputValidationError("The uploaded file is empty. Please upload a valid document.")

    # Enforce 5MB limit
    if len(file_bytes) > settings.max_upload_size_bytes:
        raise FileSizeLimitExceededError(max_size_mb=settings.max_upload_size_bytes / (1024 * 1024))

    # Extension check
    lower_name = filename.lower()
    ext = None
    for allowed_ext in settings.allowed_extensions:
        if lower_name.endswith(allowed_ext):
            ext = allowed_ext
            break

    if not ext:
        allowed_str = ", ".join(settings.allowed_extensions)
        raise InputValidationError(
            f"Unsupported file format '{filename}'. Allowed formats are: {allowed_str}"
        )

    # Magic byte verification (content sniffing)
    if ext == ".pdf":
        if not file_bytes.startswith(PDF_MAGIC):
            raise InputValidationError(
                "Invalid PDF document: File header does not match PDF specification (%PDF)."
            )
        return "application/pdf", ".pdf"

    elif ext in (".jpg", ".jpeg"):
        if not file_bytes.startswith(JPEG_MAGIC):
            raise InputValidationError(
                "Invalid JPEG image: File header does not match JPEG specification."
            )
        return "image/jpeg", ".jpg"

    elif ext == ".docx":
        if not file_bytes.startswith(ZIP_MAGIC):
            raise InputValidationError(
                "Invalid DOCX document: File header does not match ZIP/DOCX format."
            )
        # Verify internal Word document structure
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                namelist = zf.namelist()
                if not any("word/document.xml" in name for name in namelist):
                    raise InputValidationError(
                        "Corrupted or invalid DOCX: Missing internal document structure (word/document.xml)."
                    )
        except zipfile.BadZipFile:
            raise InputValidationError("The uploaded DOCX file is damaged or corrupted.")
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"

    elif ext == ".txt":
        try:
            decoded = file_bytes.decode("utf-8")
            if not decoded.strip():
                raise InputValidationError("The uploaded text file contains no readable content.")
        except UnicodeDecodeError:
            raise InputValidationError("The text file must be encoded in valid UTF-8.")
        return "text/plain", ".txt"

    raise InputValidationError(f"Unhandled file extension '{ext}'.")


def validate_pasted_text(text: str) -> str:
    """Validate and sanitize raw pasted text.

    Args:
        text: Raw text string pasted by user.

    Returns:
        Cleaned, stripped text string.

    Raises:
        InputValidationError: If text is empty, contains only whitespace, or exceeds size limits.
    """
    if not text or not text.strip():
        raise InputValidationError("Please paste or type contract text to analyze.")

    cleaned = text.strip()
    byte_len = len(cleaned.encode("utf-8"))

    if byte_len > settings.max_upload_size_bytes:
        raise FileSizeLimitExceededError(max_size_mb=settings.max_upload_size_bytes / (1024 * 1024))

    # Reject trivial spam (less than 20 characters)
    if len(cleaned) < 20:
        raise InputValidationError(
            "Input is too brief to be a valid legal contract. Please provide the complete clause or agreement text."
        )

    return cleaned
