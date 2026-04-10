"""Extract structured data from ANTT drainage monitoring PDFs using pdfplumber."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

from app.domain.drainage_record import DrainageRecord
from app.services.field_parser import (
    compute_confidence,
    derive_estaca,
    extract_fields_from_text,
    normalize_coordinate,
    parse_brazilian_float,
    parse_sim_nao,
    validate_brazil_coordinate,
)

logger = logging.getLogger(__name__)


def _extract_from_tables(page: pdfplumber.page.Page) -> Dict[str, Optional[str]]:
    """Try to extract fields from table structures on the page."""
    tables = page.extract_tables()
    if not tables:
        return {}

    fields: Dict[str, Optional[str]] = {}
    for table in tables:
        for row in table:
            if not row:
                continue
            cells = [c.strip() if c else "" for c in row]
            for i, cell in enumerate(cells):
                if not cell:
                    continue
                cell_upper = cell.upper()

                # Check if label and value are in the SAME cell (e.g. "KM INICIAL: 156+080")
                for label, key in _LABEL_MAP:
                    if label in cell_upper:
                        # Value in the same cell after the label?
                        parts = cell.split(":", 1) if ":" in cell else cell.split(label, 1)
                        if len(parts) > 1 and parts[1].strip():
                            fields[key] = parts[1].strip()
                        # Value in the next cell?
                        elif i + 1 < len(cells) and cells[i + 1]:
                            fields[key] = cells[i + 1]
                        break

    return fields


# Label -> field_name mapping for table extraction
_LABEL_MAP: List[tuple] = [
    ("KM INICIAL", "km_inicial"),
    ("KM FINAL", "km_final"),
    ("EXTENSÃO", "extensao"),
    ("EXTENSAO", "extensao"),
    ("LARGURA", "largura"),
    ("ALTURA", "altura"),
    ("IDENTIFICAÇÃO", "identificacao"),
    ("IDENTIFICACAO", "identificacao"),
    ("INÍCIO COORDENADA X", "coord_x_inicio"),
    ("INICIO COORDENADA X", "coord_x_inicio"),
    ("FIM COORDENADA X", "coord_x_fim"),
    ("INÍCIO COORDENADA Y", "coord_y_inicio"),
    ("INICIO COORDENADA Y", "coord_y_inicio"),
    ("FIM COORDENADA Y", "coord_y_fim"),
    ("CONSERVAÇÃO", "estado_conservacao"),
    ("CONSERVACAO", "estado_conservacao"),
    ("MATERIAL", "material"),
    ("AMBIENTE", "ambiente"),
]
# Tipo is checked separately due to short name causing false positives
_TIPO_LABELS = ("TIPO",)


def extract_record(pdf_path: Path) -> DrainageRecord:
    """Extract a DrainageRecord from a single ANTT drainage monitoring PDF.

    Strategy:
    1. Try table extraction (most reliable for form-like PDFs)
    2. Fall back to full-text regex extraction
    3. Merge results (table values take priority)
    """
    warnings: List[str] = []
    filename = pdf_path.name

    logger.info("Processando: %s", filename)

    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            logger.warning("%s: PDF sem paginas", filename)
            return DrainageRecord(
                source_filename=filename,
                confidence=0.0,
                warnings=["PDF sem páginas"],
            )

        page = pdf.pages[0]

        # Strategy 1: Table extraction
        table_fields = _extract_from_tables(page)

        # Strategy 2: Full text regex
        full_text = page.extract_text() or ""
        logger.debug("%s: texto extraido (%d chars)", filename, len(full_text))
        text_fields = extract_fields_from_text(full_text)

        # Merge: table values take priority, text fills gaps
        merged = {**text_fields}
        for key, val in table_fields.items():
            if val:
                merged[key] = val

    # Check for Tipo separately (short label, needs care)
    if not merged.get("tipo"):
        for table in (page.extract_tables() if hasattr(page, 'extract_tables') else []):
            for row in (table or []):
                cells = [c.strip() if c else "" for c in (row or [])]
                for i, cell in enumerate(cells):
                    if cell.upper() in _TIPO_LABELS and len(cell) <= 6 and i + 1 < len(cells):
                        merged["tipo"] = cells[i + 1]

    # Build the record
    confidence = compute_confidence(merged)
    if confidence < 0.5:
        warnings.append(
            f"Baixa confiança na extração ({confidence:.0%}) — verifique manualmente"
        )

    # Parse coordinates
    lat_inicio = normalize_coordinate(parse_brazilian_float(merged.get("coord_x_inicio")))
    lon_inicio = normalize_coordinate(parse_brazilian_float(merged.get("coord_y_inicio")))
    lat_fim = normalize_coordinate(parse_brazilian_float(merged.get("coord_x_fim")))
    lon_fim = normalize_coordinate(parse_brazilian_float(merged.get("coord_y_fim")))

    # Validate coordinates are within Brazil
    warnings.extend(validate_brazil_coordinate(lat_inicio, lon_inicio))
    warnings.extend(validate_brazil_coordinate(lat_fim, lon_fim))

    # Derive estaca from identification number, fallback to km
    identificacao = merged.get("identificacao")
    km_inicial = merged.get("km_inicial")
    km_final = merged.get("km_final")
    estaca_inicio = derive_estaca(identificacao, km_fallback=km_inicial)
    estaca_fim = derive_estaca(None, km_fallback=km_final)

    logger.info(
        "%s: confianca=%.0f%%, campos=%d/%d",
        filename, confidence * 100,
        sum(1 for v in merged.values() if v), len(merged),
    )

    return DrainageRecord(
        source_filename=filename,
        inspection_date=merged.get("inspection_date"),
        identificacao=identificacao,
        estaca_inicio=estaca_inicio,
        km_inicial=km_inicial,
        latitude_inicio=lat_inicio,
        longitude_inicio=lon_inicio,
        estaca_fim=estaca_fim,
        km_final=km_final,
        latitude_fim=lat_fim,
        longitude_fim=lon_fim,
        largura=parse_brazilian_float(merged.get("largura")),
        altura=parse_brazilian_float(merged.get("altura")),
        extensao=parse_brazilian_float(merged.get("extensao")),
        tipo=merged.get("tipo"),
        estado_conservacao=merged.get("estado_conservacao"),
        material=merged.get("material"),
        ambiente=merged.get("ambiente"),
        reparar=parse_sim_nao(merged.get("reparar")),
        limpeza=parse_sim_nao(merged.get("limpeza")),
        limpeza_extensao=parse_brazilian_float(merged.get("limpeza_extensao")),
        implantar=parse_sim_nao(merged.get("implantar")),
        confidence=confidence,
        warnings=warnings,
    )
