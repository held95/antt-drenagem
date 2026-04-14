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


class DrainageRecordData(BaseModel):
    """Serializable version of DrainageRecord for API responses."""
    source_filename: str
    inspection_date: Optional[str] = None
    identificacao: Optional[str] = None
    estaca_inicio: Optional[str] = None
    km_inicial: Optional[str] = None
    latitude_inicio: Optional[float] = None
    longitude_inicio: Optional[float] = None
    estaca_fim: Optional[str] = None
    km_final: Optional[str] = None
    latitude_fim: Optional[float] = None
    longitude_fim: Optional[float] = None
    largura: Optional[float] = None
    altura: Optional[float] = None
    extensao: Optional[float] = None
    tipo: Optional[str] = None
    estado_conservacao: Optional[str] = None
    material: Optional[str] = None
    ambiente: Optional[str] = None
    reparar: Optional[bool] = None
    limpeza: Optional[bool] = None
    limpeza_extensao: Optional[float] = None
    implantar: Optional[bool] = None
    confidence: float = 0.0


class ColumnConfigItem(BaseModel):
    field: str
    label: str
    group: str = ""


class GenerateExcelRequest(BaseModel):
    records: List[DrainageRecordData]
    columns: List[ColumnConfigItem]


class ProcessResponse(BaseModel):
    """Synchronous processing response (serverless-compatible)."""
    total_files: int
    successful_files: int
    files: List[FileResultResponse]
    excel_base64: Optional[str] = None
    records: List[DrainageRecordData] = []
