"""
File storage abstraction.

LocalFSBackend writes uploaded files to ``settings.UPLOAD_DIR`` with UUID
filenames partitioned by ``{category}/{yyyy-mm}/`` to avoid path traversal,
filename collisions, and unbounded directory size.

The backend is intentionally minimal — a future S3Backend can be slotted in
behind the same ``Storage`` protocol without touching callers.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol

import aiofiles
import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BusinessRuleError
from app.enums import FileCategory
from app.models.audit import UploadedFile

log = structlog.get_logger(__name__)

# 8 KB chunks — small enough to interleave with other tasks, large enough to
# avoid syscall churn on typical 1–10 MB uploads.
_CHUNK_SIZE = 8 * 1024

# MIME whitelist per category. Only these are accepted; anything else 422s.
_ALLOWED_MIME_BY_CATEGORY: dict[FileCategory, frozenset[str]] = {
    FileCategory.OCR_INVOICE: frozenset({
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    }),
    FileCategory.EINVOICE_PDF: frozenset({"application/pdf"}),
    FileCategory.AVATAR: frozenset({"image/jpeg", "image/png", "image/webp"}),
    FileCategory.LOGO: frozenset({"image/jpeg", "image/png", "image/svg+xml", "image/webp"}),
    FileCategory.IMPORT_EXCEL: frozenset({
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
    }),
    FileCategory.REJECTION_ATTACHMENT: frozenset({
        "image/jpeg",
        "image/png",
        "application/pdf",
    }),
    FileCategory.OTHER: frozenset(),  # OTHER bypasses the whitelist (caller responsible)
}


class Storage(Protocol):
    async def save_upload(
        self,
        file: UploadFile,
        *,
        category: FileCategory,
        organization_id: int,
        uploaded_by: Optional[int],
        max_size_mb: Optional[int] = None,
        session: AsyncSession,
    ) -> UploadedFile:
        ...

    async def read_bytes(self, stored_path: str) -> bytes:
        ...


class LocalFSBackend:
    """Writes files under ``settings.UPLOAD_DIR/{category}/{yyyy-mm}/{uuid}{ext}``."""

    def __init__(self, root: Optional[str] = None) -> None:
        self.root = Path(root or settings.UPLOAD_DIR)

    def _resolve_path(self, category: FileCategory, ext: str) -> tuple[Path, str]:
        partition = datetime.utcnow().strftime("%Y-%m")
        folder = self.root / category.value / partition
        folder.mkdir(parents=True, exist_ok=True)
        # ext keeps a leading dot if present
        clean_ext = ext if ext.startswith(".") or not ext else f".{ext}"
        name = f"{uuid.uuid4().hex}{clean_ext}"
        return folder / name, str(folder / name)

    async def save_upload(
        self,
        file: UploadFile,
        *,
        category: FileCategory,
        organization_id: int,
        uploaded_by: Optional[int],
        max_size_mb: Optional[int] = None,
        session: AsyncSession,
    ) -> UploadedFile:
        mime = (file.content_type or "").lower()
        allowed = _ALLOWED_MIME_BY_CATEGORY.get(category, frozenset())
        if allowed and mime not in allowed:
            raise BusinessRuleError(
                error_code="UNSUPPORTED_MIME_TYPE",
                message=f"File type '{mime}' is not allowed for {category.value}.",
                detail={"allowed": sorted(allowed)},
            )

        size_cap = (max_size_mb or settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024

        original = file.filename or "upload"
        ext = Path(original).suffix.lower()[:16]
        abs_path, stored_path = self._resolve_path(category, ext)

        # Stream-write to disk while computing sha256 and enforcing the size cap.
        hasher = hashlib.sha256()
        bytes_written = 0
        try:
            async with aiofiles.open(abs_path, "wb") as out:
                while True:
                    chunk = await file.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > size_cap:
                        raise BusinessRuleError(
                            error_code="FILE_TOO_LARGE",
                            message=f"File exceeds {size_cap // (1024 * 1024)} MB limit.",
                        )
                    hasher.update(chunk)
                    await out.write(chunk)
        except BusinessRuleError:
            # Clean up partial write before re-raising.
            try:
                os.remove(abs_path)
            except FileNotFoundError:
                pass
            raise

        record = UploadedFile(
            organization_id=organization_id,
            category=category,
            original_filename=original[:255],
            stored_path=stored_path,
            mime_type=mime or "application/octet-stream",
            size_bytes=bytes_written,
            sha256=hasher.hexdigest(),
            uploaded_by=uploaded_by,
        )
        session.add(record)
        await session.flush()
        log.info(
            "storage.saved",
            category=category.value,
            stored_path=stored_path,
            size_bytes=bytes_written,
            uploaded_by=uploaded_by,
        )
        return record

    async def read_bytes(self, stored_path: str) -> bytes:
        async with aiofiles.open(stored_path, "rb") as f:
            return await f.read()


# Default singleton — swap to S3Backend later by reassigning here.
storage: Storage = LocalFSBackend()
