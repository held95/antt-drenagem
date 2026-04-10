"""Upload, status, download, and cleanup endpoints for PDF and image processing."""

from __future__ import annotations

import base64
import logging
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from threading import Thread
from typing import Dict, List

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import settings
from app.models import FileResultResponse, JobStatusResponse, ProcessResponse, UploadResponse
from app.services.processing_pipeline import JobState, process_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

# In-memory job store (sufficient for single-server deployment)
_jobs: Dict[str, JobState] = {}


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


def _sanitize_filename(name: str) -> str:
    """Remove dangerous characters from filename, keep extension."""
    # Keep only alphanumeric, hyphens, underscores, dots, plus signs
    sanitized = re.sub(r"[^\w\-+.]", "_", name)
    return sanitized or "unnamed.pdf"


def _deduplicate_paths(pdf_paths: List[Path]) -> List[Path]:
    """Rename duplicate filenames by adding _2, _3, etc."""
    seen: Dict[str, int] = {}
    result: List[Path] = []
    for p in pdf_paths:
        name = p.name
        if name in seen:
            seen[name] += 1
            stem = p.stem
            suffix = p.suffix
            new_name = "{}_{}{}".format(stem, seen[name], suffix)
            new_path = p.parent / new_name
            p.rename(new_path)
            result.append(new_path)
        else:
            seen[name] = 1
            result.append(p)
    return result


def _save_and_process(job_id: str, file_paths: List[Path]):
    """Run in a background thread to process PDFs and images."""
    job_state = _jobs[job_id]
    process_batch(file_paths, job_state)


@router.post("/upload", response_model=UploadResponse)
async def upload_files(files: List[UploadFile]):
    """Upload multiple PDF and/or image files for processing."""
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado")

    if len(files) > settings.max_files_per_batch:
        raise HTTPException(
            status_code=400,
            detail="Máximo de {} arquivos por lote".format(settings.max_files_per_batch),
        )

    # Validate all files are PDFs or supported images
    for f in files:
        if not f.filename:
            raise HTTPException(status_code=400, detail="Arquivo sem nome")
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Arquivo '{}' nao e suportado. Use: {}".format(
                    f.filename, ", ".join(sorted(ALLOWED_EXTENSIONS))
                ),
            )

    # Create job directory
    job_id = str(uuid.uuid4())
    job_dir = settings.upload_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded files
    file_paths: List[Path] = []
    for f in files:
        safe_name = _sanitize_filename(f.filename or "unnamed.pdf")
        dest = job_dir / safe_name
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        file_paths.append(dest)

    # Handle duplicate filenames
    file_paths = _deduplicate_paths(file_paths)

    logger.info("Upload: job=%s, arquivos=%d", job_id, len(file_paths))

    # Initialize job state
    _jobs[job_id] = JobState(
        job_id=job_id,
        total_files=len(file_paths),
    )

    # Start processing in background thread
    thread = Thread(
        target=_save_and_process,
        args=(job_id, file_paths),
        daemon=True,
    )
    thread.start()

    return UploadResponse(
        job_id=job_id,
        file_count=len(file_paths),
        status="processing",
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get the processing status and per-file results for a job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        total_files=job.total_files,
        processed_files=job.processed_files,
        files=[
            FileResultResponse(
                filename=fr.filename,
                status=fr.status,
                warnings=fr.warnings,
                error=fr.error,
            )
            for fr in job.file_results
        ],
        download_ready=job.excel_bytes is not None,
    )


@router.get("/download/{job_id}")
async def download_excel(job_id: str):
    """Download the generated Excel file for a completed job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if not job.excel_bytes:
        raise HTTPException(status_code=409, detail="Excel ainda não está pronto")

    return Response(
        content=job.excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="drenagem_consolidado_{}.xlsx"'.format(job_id[:8])
        },
    )


@router.post("/process", response_model=ProcessResponse)
async def process_files(files: List[UploadFile]):
    """Synchronous processing: upload, extract, and return Excel in one request.

    Designed for serverless environments (Vercel) where background threads
    and in-memory state are not available.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado")

    if len(files) > settings.max_files_per_batch:
        raise HTTPException(
            status_code=400,
            detail="Máximo de {} arquivos por lote".format(settings.max_files_per_batch),
        )

    # Validate file extensions
    for f in files:
        if not f.filename:
            raise HTTPException(status_code=400, detail="Arquivo sem nome")
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Arquivo '{}' nao e suportado. Use: {}".format(
                    f.filename, ", ".join(sorted(ALLOWED_EXTENSIONS))
                ),
            )

    # Save to temp directory (works on Vercel's /tmp)
    tmp_dir = Path(tempfile.mkdtemp(prefix="antt_"))
    try:
        file_paths: List[Path] = []
        for f in files:
            safe_name = _sanitize_filename(f.filename or "unnamed.pdf")
            dest = tmp_dir / safe_name
            with dest.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            file_paths.append(dest)

        file_paths = _deduplicate_paths(file_paths)

        logger.info("Process (sync): arquivos=%d", len(file_paths))

        # Process synchronously
        job_state = JobState(job_id="sync", total_files=len(file_paths))
        process_batch(file_paths, job_state)

        # Build response
        file_results = [
            FileResultResponse(
                filename=fr.filename,
                status=fr.status,
                warnings=fr.warnings,
                error=fr.error,
            )
            for fr in job_state.file_results
        ]
        successful = sum(1 for fr in job_state.file_results if fr.record is not None)

        excel_b64 = None
        if job_state.excel_bytes:
            excel_b64 = base64.b64encode(job_state.excel_bytes).decode("ascii")

        return ProcessResponse(
            total_files=len(file_paths),
            successful_files=successful,
            files=file_results,
            excel_base64=excel_b64,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its temporary files."""
    job = _jobs.pop(job_id, None)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    # Remove uploaded files
    job_dir = settings.upload_dir / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
        logger.info("Cleanup: job=%s, diretorio removido", job_id)

    return {"deleted": True}
