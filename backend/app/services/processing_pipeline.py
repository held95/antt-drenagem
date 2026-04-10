"""Orchestrate PDF/image extraction and Excel generation for a batch of files."""

from __future__ import annotations

import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from app.config import settings
from app.domain.drainage_record import DrainageRecord
from app.services.excel_generator import generate_excel
from app.services.pdf_extractor import extract_record
from app.services.image_extractor import extract_record_from_image

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class FileResult:
    filename: str
    status: str = "pending"  # pending | processing | success | error
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    record: Optional[DrainageRecord] = None


@dataclass
class JobState:
    job_id: str
    status: str = "processing"  # processing | completed | error
    total_files: int = 0
    processed_files: int = 0
    file_results: List[FileResult] = field(default_factory=list)
    excel_bytes: Optional[bytes] = None
    error: Optional[str] = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def increment_processed(self) -> None:
        with self._lock:
            self.processed_files += 1


def _process_single_file(file_path: Path) -> FileResult:
    """Process a single PDF or image file and return the result."""
    result = FileResult(filename=file_path.name, status="processing")
    try:
        if file_path.suffix.lower() in IMAGE_EXTENSIONS:
            record = extract_record_from_image(file_path)
        else:
            record = extract_record(file_path)
        result.record = record
        result.warnings = record.warnings
        result.status = "success"
    except Exception as e:
        logger.exception("Erro processando %s", file_path.name)
        result.status = "error"
        result.error = str(e)
    return result


def process_batch(
    file_paths: List[Path],
    job_state: JobState,
    on_progress: Optional[Callable[[JobState], None]] = None,
) -> JobState:
    """Process a batch of PDFs and/or images, extract data, and generate Excel.

    Updates job_state in-place with progress. Uses threading.Lock for
    thread-safe progress tracking.
    """
    start_time = time.monotonic()
    logger.info(
        "Iniciando processamento: job=%s, arquivos=%d",
        job_state.job_id, len(file_paths),
    )

    job_state.total_files = len(file_paths)
    job_state.file_results = [FileResult(filename=p.name) for p in file_paths]
    file_result_map = {p.name: r for p, r in zip(file_paths, job_state.file_results)}

    records: List[DrainageRecord] = []

    with ThreadPoolExecutor(max_workers=settings.workers) as executor:
        future_to_path = {
            executor.submit(_process_single_file, path): path
            for path in file_paths
        }

        for future in as_completed(future_to_path):
            path = future_to_path[future]
            result = future.result()

            # Update the corresponding FileResult in job_state
            fr = file_result_map[path.name]
            fr.status = result.status
            fr.warnings = result.warnings
            fr.error = result.error
            fr.record = result.record

            if result.record:
                records.append(result.record)

            job_state.increment_processed()
            if on_progress:
                on_progress(job_state)

    # Generate Excel from all successful records
    if records:
        try:
            job_state.excel_bytes = generate_excel(records)
            job_state.status = "completed"
        except Exception as e:
            logger.exception("Erro ao gerar Excel")
            job_state.status = "error"
            job_state.error = "Erro ao gerar Excel: {}".format(e)
    else:
        job_state.status = "error"
        job_state.error = "Nenhum arquivo foi processado com sucesso"

    elapsed = time.monotonic() - start_time
    logger.info(
        "Processamento concluido: job=%s, status=%s, sucesso=%d/%d, tempo=%.1fs",
        job_state.job_id, job_state.status,
        len(records), len(file_paths), elapsed,
    )

    return job_state
