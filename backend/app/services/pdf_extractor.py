"""Extract structured data from ANTT drainage monitoring PDFs.

Uses pdfplumber (table + text) when available, falls back to pdfminer.six (text only)
for lightweight deployments (e.g. Vercel serverless).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.layout import LAParams

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
    ("LARGURA(M)", "largura"),
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


def _extract_with_pdfplumber(pdf_path: Path) -> tuple:
    """Extract using pdfplumber (table + text). Returns (merged_fields, warnings, raw_text)."""
    warnings: List[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            return {}, ["PDF sem páginas"], ""

        page = pdf.pages[0]
        table_fields = _extract_from_tables(page)
        full_text = page.extract_text() or ""
        text_fields = extract_fields_from_text(full_text)

        merged = {**text_fields}
        for key, val in table_fields.items():
            if val:
                merged[key] = val

        # Check for Tipo separately — always prefer table value since the general text
        # regex can capture "Material" when cells are merged in pdfplumber text output.
        for table in (page.extract_tables() if hasattr(page, 'extract_tables') else []):
            for row in (table or []):
                cells = [c.strip() if c else "" for c in (row or [])]
                for i, cell in enumerate(cells):
                    if cell.upper().rstrip(":").strip() in _TIPO_LABELS and len(cell.rstrip(":").strip()) <= 6:
                        for j in range(i + 1, min(len(cells), i + 3)):
                            if cells[j] and re.match(r"MF?C", cells[j], re.IGNORECASE):
                                merged["tipo"] = cells[j]
                                break

    return merged, warnings, full_text


def _extract_with_pdfminer(pdf_path: Path) -> tuple:
    """Extract using pdfminer.six with multiple layout strategies.

    pdfminer.six extracts text differently than pdfplumber — form fields
    often end up on separate lines. We try multiple LAParams configs and
    use both standard + label-based extraction to maximize field capture.
    """
    # Strategy 1: tight layout (good for forms where labels and values are close)
    laparams_tight = LAParams(
        line_margin=0.3,
        word_margin=0.1,
        char_margin=2.0,
        boxes_flow=0.5,
    )
    # Strategy 2: default layout
    laparams_default = LAParams()

    # Strategy 3: wide layout (good for two-column forms)
    laparams_wide = LAParams(
        line_margin=0.5,
        word_margin=0.2,
        char_margin=3.0,
        boxes_flow=None,  # Use exact positioning
    )

    texts = []
    for lp in [laparams_tight, laparams_default, laparams_wide]:
        try:
            text = pdfminer_extract_text(str(pdf_path), laparams=lp)
            if text.strip():
                texts.append(text)
        except Exception as e:
            logger.debug("pdfminer extraction failed with params: %s", e)

    if not texts:
        return {}, ["PDF sem texto extraivel"], ""

    # Try standard regex on each text variant, keep the one with most fields
    best_merged: Dict[str, Optional[str]] = {}
    best_count = 0

    for text in texts:
        # Standard field_parser regex
        fields = extract_fields_from_text(text)
        count = sum(1 for v in fields.values() if v)
        if count > best_count:
            best_count = count
            best_merged = fields

    # Supplement with label-based extraction across ALL text variants
    combined_text = "\n".join(texts)
    label_fields = _extract_labels_from_text(combined_text)
    for key, val in label_fields.items():
        if key == "tipo":
            # Always prefer the specific MFC pattern — the general regex can capture
            # "Material" when pdfminer merges adjacent form cells on the same line.
            if val:
                best_merged[key] = val
        elif val and not best_merged.get(key):
            best_merged[key] = val

    # Robust coordinate extraction: handles pdfminer layouts where label and value
    # are separated by other cell text (e.g. "Início Coordenada X: Fim Coordenada X:\n-18,...")
    coord_fields = _extract_coords_robust(combined_text)
    for key, val in coord_fields.items():
        if val:
            best_merged[key] = val

    # Supplement with standalone keyword fallbacks
    fallback_fields = _extract_standalone_values(combined_text)
    for key, val in fallback_fields.items():
        if val and not best_merged.get(key):
            best_merged[key] = val

    return best_merged, [], combined_text


# Label patterns for pdfminer text where label and value may be on same or different lines
_PDFMINER_LABEL_PATTERNS: List[tuple] = [
    ("km_inicial", re.compile(r"KM\s*INICIAL\s*[:\s]*([\d]+\+[\d]+)", re.IGNORECASE)),
    ("km_final", re.compile(r"KM\s*FINAL\s*[:\s]*([\d]+\+[\d]+)", re.IGNORECASE)),
    ("extensao", re.compile(r"EXTENS[ÃA]O\s*\(?m?\)?\s*[:\s]*([\d.,]+)", re.IGNORECASE)),
    ("largura", re.compile(r"Largura\s*[\(（]?\s*m?\s*[\)）]?\s*[=:\s]*([\d.,]+)", re.IGNORECASE)),
    ("altura", re.compile(r"Altura\s*\(?m?\)?\s*[:\s]*([\d.,]+)", re.IGNORECASE)),
    ("coord_x_inicio", re.compile(r"In[ií]cio\s*Coordenada\s*X\s*[:\s]*([-\d.,]+)", re.IGNORECASE)),
    ("coord_y_inicio", re.compile(r"In[ií]cio\s*Coordenada\s*Y\s*[:\s]*([-\d.,]+)", re.IGNORECASE)),
    ("coord_x_fim", re.compile(r"Fim\s*Coordenada\s*X\s*[:\s]*([-\d.,]+)", re.IGNORECASE)),
    ("coord_y_fim", re.compile(r"Fim\s*Coordenada\s*Y\s*[:\s]*([-\d.,]+)", re.IGNORECASE)),
    ("estado_conservacao", re.compile(
        r"(?:Estado\s*de\s*)?Conserva[çc][ãa]o\s*[:\s]*(REGULAR|PREC[ÁA]RIO|BOM|RUIM|NOVO|P[ÉE]SSIMO)",
        re.IGNORECASE,
    )),
    ("ambiente", re.compile(r"Ambiente\s*[:\s]*(URBANO|RURAL)", re.IGNORECASE)),
    ("material", re.compile(r"Material\s*[:\s]*(CONCRETO|ALVENARIA|METAL\w*|PEDRA|PVC)", re.IGNORECASE)),
    ("tipo", re.compile(r"Tipo\s*[:\s]*(MF?C\s*[/\s]?\s*[A-Za-z0-9]{1,5})", re.IGNORECASE)),
    ("inspection_date", re.compile(r"Data\s*[Ii]nsp\.?\s*[:\s]*([\d]{1,2}[/\-][\d]{1,2}[/\-][\d]{2,4})", re.IGNORECASE)),
    ("identificacao", re.compile(r"IDENTIFICA[ÇC][ÃA]O\s*[:\s]*(MF\s*381\s*MG\s*[\d+]+\s*L?\s*\d?)", re.IGNORECASE)),
    ("reparar", re.compile(r"Reparar\s*[:\s]*(Sim|N[ãa]o)", re.IGNORECASE)),
    ("limpeza", re.compile(r"Limpeza\s*[:\s]*(Sim|N[ãa]o)", re.IGNORECASE)),
    ("implantar", re.compile(r"Implantar\s*[:\s]*(Sim|N[ãa]o)", re.IGNORECASE)),
]


def _extract_labels_from_text(text: str) -> Dict[str, Optional[str]]:
    """Extract fields using label-based patterns that handle multi-line text."""
    fields: Dict[str, Optional[str]] = {}
    for field_name, pattern in _PDFMINER_LABEL_PATTERNS:
        match = pattern.search(text)
        if match:
            fields[field_name] = match.group(1).strip()
    return fields


def _extract_coords_robust(text: str) -> Dict[str, Optional[str]]:
    """Robust coordinate extraction: find label, then scan ahead for the best signed decimal.

    Handles pdfminer layouts where label and value land on different lines with
    other text (e.g. another cell label) in between.

    Uses geographic bounds to discriminate X (latitude, -34..6) from Y (longitude,
    -74..-34), avoiding the common bug where a two-column form places Y values
    before X values in the extracted text stream.
    """
    coords: Dict[str, Optional[str]] = {}
    label_map = [
        ("coord_x_inicio", re.compile(r"In[ií]cio\s+Coordenada\s+X", re.IGNORECASE)),
        ("coord_y_inicio", re.compile(r"In[ií]cio\s+Coordenada\s+Y", re.IGNORECASE)),
        ("coord_x_fim", re.compile(r"Fim\s+Coordenada\s+X", re.IGNORECASE)),
        ("coord_y_fim", re.compile(r"Fim\s+Coordenada\s+Y", re.IGNORECASE)),
    ]
    # coord_x = latitude-like: -34 to 6; coord_y = longitude-like: -74 to -34
    # Values may also appear scaled (e.g. -1891559 → -18.91559), so we check after normalization
    preferred_bounds = {
        "coord_x_inicio": (-34.0, 6.0),
        "coord_x_fim":    (-34.0, 6.0),
        "coord_y_inicio": (-74.0, -34.0),
        "coord_y_fim":    (-74.0, -34.0),
    }
    for key, label_pat in label_map:
        m = label_pat.search(text)
        if not m:
            continue
        # Collect all signed decimals in the next 300 characters
        window = text[m.end(): m.end() + 300]
        candidates = re.finditer(r"-\d{1,10}[,.][\d,. ]{1,}", window)
        lo, hi = preferred_bounds[key]
        best: Optional[str] = None
        fallback: Optional[str] = None
        for cand_m in candidates:
            raw_match = re.match(r"-[\d.,]+", cand_m.group(0).replace(" ", ""))
            if not raw_match:
                continue
            raw = raw_match.group(0)
            # Parse to float for bounds checking (handle Brazilian comma-decimal)
            cleaned = raw.replace(",", ".")
            # Remove extra dots (1.234.56 → shouldn't happen but guard anyway)
            try:
                val = float(cleaned)
            except ValueError:
                continue
            # Normalize scaled values (e.g. -1891559 → try dividing by 10^n)
            if abs(val) > 180:
                from app.services.field_parser import normalize_coordinate
                val_norm = normalize_coordinate(val)
                if val_norm is None:
                    continue
            else:
                val_norm = val
            # Prefer the first candidate that falls within the expected bounds
            if fallback is None:
                fallback = raw  # keep first match as fallback regardless of bounds
            if lo <= val_norm <= hi:
                best = raw
                break
        coords[key] = best if best is not None else fallback
    return coords


def _extract_standalone_values(text: str) -> Dict[str, Optional[str]]:
    """Extract fields by finding standalone enum values and distinctive patterns."""
    fields: Dict[str, Optional[str]] = {}

    # Standalone enum values
    for key, pattern in [
        ("estado_conservacao", re.compile(r"\b(REGULAR|PREC[ÁA]RIO|P[ÉE]SSIMO|BOM|RUIM|NOVO)\b", re.IGNORECASE)),
        ("ambiente", re.compile(r"\b(URBANO|RURAL)\b", re.IGNORECASE)),
        ("material", re.compile(r"\b(CONCRETO|ALVENARIA)\b", re.IGNORECASE)),
    ]:
        match = pattern.search(text)
        if match:
            fields[key] = match.group(1).strip()

    # MFC type codes
    match = re.search(r"\b(MF?C\s*[/\s.]?\s*[A-Za-z0-9]{1,5})\b", text, re.IGNORECASE)
    if match:
        fields["tipo"] = match.group(1).strip()

    # KM patterns (NNN+NNN)
    km_matches = re.findall(r"\b(\d{3}\+\d{3})\b", text)
    unique_kms = list(dict.fromkeys(km_matches))
    if unique_kms:
        fields["km_inicial"] = unique_kms[0]
    if len(unique_kms) >= 2:
        fields["km_final"] = unique_kms[1]

    # MF 381 MG identification pattern
    match = re.search(r"(MF\s*381\s*MG\s*\d{2,3}\+\d{2,3}\s*L?\s*\d?)", text, re.IGNORECASE)
    if match:
        fields["identificacao"] = match.group(1).strip()

    return fields


def _auto_correct_coord_pair(
    coord_x: Optional[float], coord_y: Optional[float]
) -> tuple:
    """Detect and fix swapped X/Y coordinates using Brazilian geographic bounds.

    coord_x should be latitude-like (-34 to 6), coord_y should be longitude-like (-74 to -34).
    Handles two common extraction failures from two-column PDF forms:
    - Only coord_x extracted but its value is actually a longitude → move to coord_y
    - Both extracted but swapped → swap them back
    """
    def is_lat(v: Optional[float]) -> bool:
        return v is not None and -34.0 <= v <= 6.0

    def is_lon(v: Optional[float]) -> bool:
        return v is not None and -74.0 <= v <= -34.0

    # Only coord_x found, but it looks like a longitude value → belongs in coord_y
    if coord_x is not None and coord_y is None and is_lon(coord_x):
        logger.debug("Coordenada X parece longitude (%s) — movendo para coord_y", coord_x)
        return None, coord_x

    # Both present but reversed (X is longitude range, Y is latitude range)
    if is_lon(coord_x) and is_lat(coord_y):
        logger.debug("Coordenadas X/Y invertidas — corrigindo swap (%s, %s)", coord_x, coord_y)
        return coord_y, coord_x

    return coord_x, coord_y


def extract_record(pdf_path: Path) -> DrainageRecord:
    """Extract a DrainageRecord from a single ANTT drainage monitoring PDF.

    Uses pdfplumber (table + text) when available, falls back to
    pdfminer.six (text only) for lightweight deployments.
    """
    warnings: List[str] = []
    filename = pdf_path.name

    logger.info("Processando: %s", filename)

    if PDFPLUMBER_AVAILABLE:
        merged, extract_warnings, raw_text = _extract_with_pdfplumber(pdf_path)
    else:
        merged, extract_warnings, raw_text = _extract_with_pdfminer(pdf_path)

    warnings.extend(extract_warnings)

    if not merged:
        return DrainageRecord(
            source_filename=filename,
            confidence=0.0,
            warnings=warnings or ["PDF sem dados extraiveis"],
        )

    # Build the record
    confidence = compute_confidence(merged)

    # LLM gap-fill: preenche campos None quando confiança é baixa e API key configurada
    from app.config import settings
    if settings.anthropic_api_key and confidence < settings.llm_confidence_threshold and raw_text:
        from app.services.llm_extractor import extract_missing_fields
        llm_fields = extract_missing_fields(
            text=raw_text,
            existing_fields=merged,
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
        )
        if llm_fields:
            merged.update(llm_fields)
            confidence = compute_confidence(merged)
            warnings.append(
                f"LLM complementou {len(llm_fields)} campo(s): {', '.join(llm_fields)}"
            )

    if confidence < 0.5:
        warnings.append(
            f"Baixa confiança na extração ({confidence:.0%}) — verifique manualmente"
        )

    # Parse coordinates
    lat_inicio = normalize_coordinate(parse_brazilian_float(merged.get("coord_x_inicio")))
    lon_inicio = normalize_coordinate(parse_brazilian_float(merged.get("coord_y_inicio")))
    lat_fim = normalize_coordinate(parse_brazilian_float(merged.get("coord_x_fim")))
    lon_fim = normalize_coordinate(parse_brazilian_float(merged.get("coord_y_fim")))

    # Auto-correct swapped X/Y pairs (common in two-column PDF form extractions)
    lat_inicio, lon_inicio = _auto_correct_coord_pair(lat_inicio, lon_inicio)
    lat_fim, lon_fim = _auto_correct_coord_pair(lat_fim, lon_fim)

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
