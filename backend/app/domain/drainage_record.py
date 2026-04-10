from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DrainageRecord:
    """One row of extracted data from an ANTT drainage monitoring PDF."""

    source_filename: str

    # Header
    inspection_date: Optional[str] = None  # "27/01/2025"

    # IDENTIFICAÇÃO
    identificacao: Optional[str] = None  # "MF 381 MG 156+080 L 1"

    # Localização do Início
    estaca_inicio: Optional[str] = None
    km_inicial: Optional[str] = None  # "156+080"
    latitude_inicio: Optional[float] = None
    longitude_inicio: Optional[float] = None

    # Localização do Fim
    estaca_fim: Optional[str] = None
    km_final: Optional[str] = None  # "156+390"
    latitude_fim: Optional[float] = None
    longitude_fim: Optional[float] = None

    # Dimensões
    largura: Optional[float] = None
    altura: Optional[float] = None
    extensao: Optional[float] = None

    # Classificação
    tipo: Optional[str] = None  # "MFC/VG", "MFC196"
    estado_conservacao: Optional[str] = None  # "REGULAR", "PRECÁRIO"
    material: Optional[str] = None  # "CONCRETO"
    ambiente: Optional[str] = None  # "URBANO", "RURAL"

    # Diagnóstico
    reparar: Optional[bool] = None
    limpeza: Optional[bool] = None
    limpeza_extensao: Optional[float] = None
    implantar: Optional[bool] = None

    # Metadata
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
