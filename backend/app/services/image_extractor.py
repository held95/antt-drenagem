"""Extract structured data from ANTT drainage monitoring images using OCR (Tesseract).

Uses a multi-pass OCR strategy with different preprocessing settings to maximize
text extraction quality, especially for photos of screens or low-quality scans.
Also includes OCR-tolerant regex patterns that complement the standard field_parser.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

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


# ---------------------------------------------------------------------------
# Image preprocessing variants
# ---------------------------------------------------------------------------

def _prep_binarize(img: Image.Image) -> Image.Image:
    """Grayscale + contrast + binarize — best for high-contrast forms."""
    if img.mode != "L":
        img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda x: 255 if x > 140 else 0, "1")
    return img


def _prep_grayscale(img: Image.Image) -> Image.Image:
    """Grayscale + contrast + sharpen, no binarization — best for photos."""
    if img.mode != "L":
        img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    return img


def _prep_color(img: Image.Image) -> Image.Image:
    """Keep color, just sharpen — sometimes Tesseract handles color better."""
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    return img


# ---------------------------------------------------------------------------
# OCR-tolerant regex patterns (supplement field_parser patterns)
# ---------------------------------------------------------------------------

# These patterns handle common OCR misreads while keeping specificity.
OCR_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    # KM markers: look for the distinctive NNN+NNN pattern near KM/INICIAL/FINAL
    ("km_inicial", re.compile(r"(?:KM|km|Km).?(?:INICIAL|INIC\w*|IN\w*)\s*[:\|]?\s*(\d{2,3}\+\d{2,3})", re.IGNORECASE)),
    ("km_final", re.compile(r"(?:KM|km|Km).?(?:FINAL|FIN\w*)\s*[:\|]?\s*(\d{2,3}\+\d{2,3})", re.IGNORECASE)),
    # Extensao: OCR may garble the label but value pattern is distinctive
    ("extensao", re.compile(r"[EÉe]xt?ens\w*\s*\(?m?\)?\s*[:\|]?\s*([\d.,]+)", re.IGNORECASE)),
    # Largura
    ("largura", re.compile(r"[Ll]argura\s*\(?m?\)?\s*[:\|]?\s*([\d.,]+)", re.IGNORECASE)),
    # Altura
    ("altura", re.compile(r"[Aa]ltura\s*\(?m?\)?\s*[:\|]?\s*([\d.,]+)", re.IGNORECASE)),
    # Coordinates — very tolerant label matching
    ("coord_x_inicio", re.compile(r"[Ii]n\w{0,6}\s*[CcGg]oord\w*\s*[Xx]\s*[:\|]?\s*([-\d.,]+)", re.IGNORECASE)),
    ("coord_y_inicio", re.compile(r"[Ii]n\w{0,6}\s*[CcGg]oord\w*\s*[Yy]\s*[:\|]?\s*([-\d.,]+)", re.IGNORECASE)),
    ("coord_x_fim", re.compile(r"[Ff]im\s*[CcGg]oord\w*\s*[Xx]\s*[:\|]?\s*([-\d.,]+)", re.IGNORECASE)),
    ("coord_y_fim", re.compile(r"[Ff]im\s*[CcGg]oord\w*\s*[Yy]\s*[:\|]?\s*([-\d.,]+)", re.IGNORECASE)),
    # Estado de Conservação — look for keyword values anywhere (very OCR-tolerant)
    ("estado_conservacao", re.compile(
        r"(?:[Cc]onserv|[Cc]omerv|[Cc]onierv)\w*\s*[:\|]?\s*(REGULAR|PREC[ÁA]RIO|BOM|RUIM|NOVO|P[ÉE]SSIMO)",
        re.IGNORECASE,
    )),
    # Ambiente — look for URBANO/RURAL near "Amb" or standalone
    ("ambiente", re.compile(r"[Aa]mb\w*\s*[:\|]?\s*(URBANO|RURAL)", re.IGNORECASE)),
    # Material — very tolerant
    ("material", re.compile(r"[Mm]at\w*[li]a[li]\s*[:\|]?\s*(CONCRETO|ALVENARIA|METAL\w*|PEDRA|PVC)", re.IGNORECASE)),
    # Tipo — look for MFC pattern which is distinctive
    ("tipo", re.compile(r"[Tt]i[op][eo]\s*[:\|]?\s*([A-Za-z]{2,4}[/\s]?[A-Za-z0-9]{1,4})", re.IGNORECASE)),
    # Identificação — look for MF 381 MG pattern (very distinctive)
    ("identificacao", re.compile(r"(MF\s*381\s*MG\s*\d{2,3}\+\d{2,3}\s*L?\s*\d?)", re.IGNORECASE)),
    # Date pattern — more flexible
    ("inspection_date", re.compile(r"(?:Data|Insp|ata)\w*\.?\s*[:\|\]]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE)),
    # Diagnostics
    ("reparar", re.compile(r"[Rr]eparar\s*[:\|]?\s*(Sim|S[iI1]m|N[ãaÃA]o|Nao)", re.IGNORECASE)),
    ("limpeza", re.compile(r"[Ll]impeza\s*[:\|]?\s*(Sim|S[iI1]m|N[ãaÃA]o|Nao)", re.IGNORECASE)),
    ("implantar", re.compile(r"[Ii]mplantar\s*[:\|]?\s*(Sim|S[iI1]m|N[ãaÃA]o|Nao)", re.IGNORECASE)),
]

# Fallback: standalone keyword patterns — used when labels are completely garbled
# These match enum values that are very unlikely to appear as OCR noise
OCR_FALLBACK_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("estado_conservacao", re.compile(r"\b(REGULAR|PREC[ÁA]RIO|P[ÉE]SSIMO)\b", re.IGNORECASE)),
    ("ambiente", re.compile(r"\b(URBANO|RURAL)\b")),
    ("material", re.compile(r"\b(CONCRETO|ALVENARIA)\b")),
    # MFC/XXX type codes
    ("tipo", re.compile(r"\b(MFC\s*[/\s]?\s*[A-Za-z0-9]{1,4})\b", re.IGNORECASE)),
    # NNN+NNN km patterns (first occurrence likely km_inicial)
    ("km_inicial", re.compile(r"\b(\d{3}\+\d{3})\b")),
]


def _extract_ocr_fields(text: str) -> Dict[str, Optional[str]]:
    """Extract fields using OCR-tolerant patterns, with fallback for garbled labels."""
    fields: Dict[str, Optional[str]] = {}

    # Primary OCR patterns (label-based, but more tolerant)
    for field_name, pattern in OCR_PATTERNS:
        match = pattern.search(text)
        if match:
            fields[field_name] = match.group(1).strip()

    # Fallback: standalone keyword matching for fields not yet found
    for field_name, pattern in OCR_FALLBACK_PATTERNS:
        if not fields.get(field_name):
            match = pattern.search(text)
            if match:
                fields[field_name] = match.group(1).strip()

    # Special: find second km pattern for km_final if km_inicial was found
    if fields.get("km_inicial") and not fields.get("km_final"):
        km_pattern = re.compile(r"\b(\d{3}\+\d{3})\b")
        all_kms = km_pattern.findall(text)
        unique_kms = list(dict.fromkeys(all_kms))  # preserve order, deduplicate
        if len(unique_kms) >= 2 and unique_kms[0] == fields["km_inicial"]:
            fields["km_final"] = unique_kms[1]

    return fields


# ---------------------------------------------------------------------------
# Multi-pass OCR
# ---------------------------------------------------------------------------

def _ocr_multipass(image_path: Path) -> str:
    """Run Tesseract with multiple preprocessing variants, return combined text."""
    img = Image.open(image_path)

    # Ensure minimum resolution for OCR
    min_width = 2000
    if img.width < min_width:
        scale = min_width / img.width
        img = img.resize(
            (int(img.width * scale), int(img.height * scale)),
            Image.LANCZOS,
        )

    lang = "por+eng"
    texts: List[str] = []

    preprocess_configs = [
        (_prep_binarize, "--psm 6"),
        (_prep_grayscale, "--psm 3"),
        (_prep_color, "--psm 6"),
    ]

    for prep_fn, psm_config in preprocess_configs:
        processed = prep_fn(img.copy())
        try:
            text = pytesseract.image_to_string(processed, lang=lang, config=psm_config)
        except pytesseract.TesseractError:
            try:
                text = pytesseract.image_to_string(processed, lang="eng", config=psm_config)
            except pytesseract.TesseractError:
                text = ""
        texts.append(text)

    # Combine all texts (separated by newlines)
    combined = "\n".join(texts)
    return combined


def extract_record_from_image(image_path: Path) -> DrainageRecord:
    """Extract a DrainageRecord from a JPEG/PNG image of an ANTT drainage form.

    Strategy:
    1. Run OCR with multiple preprocessing variants (multi-pass)
    2. Apply standard regex extraction from field_parser
    3. Apply OCR-tolerant regex patterns as supplement
    4. Merge results (standard patterns take priority, OCR patterns fill gaps)
    5. Normalize and validate extracted values
    """
    warnings: List[str] = []
    filename = image_path.name

    if not OCR_AVAILABLE:
        logger.error("pytesseract/Pillow nao instalado — OCR indisponivel")
        return DrainageRecord(
            source_filename=filename,
            confidence=0.0,
            warnings=["OCR indisponivel neste ambiente (pytesseract/Pillow nao instalado)"],
        )

    logger.info("Processando imagem (OCR): %s", filename)

    full_text = _ocr_multipass(image_path)
    logger.debug("%s: texto OCR combinado (%d chars)", filename, len(full_text))

    if not full_text.strip():
        logger.warning("%s: OCR nao extraiu texto", filename)
        return DrainageRecord(
            source_filename=filename,
            confidence=0.0,
            warnings=["OCR nao conseguiu extrair texto da imagem"],
        )

    # Strategy 1: Standard field_parser regex (designed for clean PDF text)
    standard_fields = extract_fields_from_text(full_text)

    # Strategy 2: OCR-tolerant regex patterns
    ocr_fields = _extract_ocr_fields(full_text)

    # Merge: standard patterns take priority, OCR patterns fill gaps
    merged: Dict[str, Optional[str]] = {}
    all_keys = set(list(standard_fields.keys()) + list(ocr_fields.keys()))
    for key in all_keys:
        std_val = standard_fields.get(key)
        ocr_val = ocr_fields.get(key)
        merged[key] = std_val if std_val else ocr_val

    # Build the record
    confidence = compute_confidence(merged)
    if confidence < 0.5:
        warnings.append(
            "Baixa confianca na extracao OCR ({:.0%}) — verifique manualmente".format(confidence)
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
