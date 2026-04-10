"""Pydantic response models for the API."""

from typing import List, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    job_id: str
    file_count: int
    status: str


class FileResultResponse(BaseModel):
    filename: str
    status: str
    warnings: List[str]
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    total_files: int
    processed_files: int
    files: List[FileResultResponse]
    download_ready: bool
