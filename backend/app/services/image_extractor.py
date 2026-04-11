"""Extract structured data from ANTT drainage monitoring images using OCR.

Uses local Tesseract when available, falls back to OCR.space cloud API
for serverless deployments (Vercel).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from app.config import settings
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
# OCR.space Cloud API (fallback when Tesseract is not installed)
# ---------------------------------------------------------------------------

def _reassemble_two_column_text(raw_text: str) -> str:
    """Reassemble two-column OCR text into 'LABEL: VALUE' lines.

    OCR.space Engine 2 reads forms column-by-column, producing blocks of
    labels (lines with ':') followed by blocks of values.
    This function detects those blocks and pairs labels with values by order.
    """
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    def _is_label_line(line: str) -> bool:
        """A line is a label if it ends with ':' or is a known label with ':'."""
        if line.endswith(":"):
            return True
        # Handle "Material: NOISE TEXT" — label with OCR noise appended
        for label in [
            "IDENTIFICAÇÃO", "IDENTIFICACAO", "EXTENSÃO", "EXTENSAO",
            "Largura", "Altura", "Inicio Coordenada", "Fim Coordenada",
            "Tipo", "Material", "KM INICIAL", "KM FINAL",
            "Estado de Conserva", "Ambiente", "Reparar", "Limpeza", "Implantar",
        ]:
            if line.lower().startswith(label.lower()) and ":" in line:
                return True
        return False

    def _clean_label(line: str) -> str:
        """Extract just the label part, removing OCR noise after the colon."""
        # If line ends with ':', it's clean
        if line.endswith(":"):
            return line
        # Otherwise extract up to and including the first ':'
        idx = line.index(":")
        return line[:idx + 1]

    result_lines = []
    i = 0
    while i < len(lines):
        # Collect a block of consecutive label lines
        labels = []
        while i < len(lines) and _is_label_line(lines[i]):
            labels.append(_clean_label(lines[i]))
            i += 1

        if labels:
            # Collect next N non-label lines as values
            values = []
            while i < len(lines) and not _is_label_line(lines[i]) and len(values) < len(labels):
                values.append(lines[i])
                i += 1
            # Pair them
            for j, label in enumerate(labels):
                if j < len(values):
                    result_lines.append("{} {}".format(label, values[j]))
                else:
                    result_lines.append(label)
        else:
            result_lines.append(lines[i])
            i += 1

    return "\n".join(result_lines)


def _ocr_via_api(image_path: Path) -> str:
    """Send image to OCR.space free API and return extracted text."""
    api_key = settings.ocr_space_api_key
    if not api_key:
        logger.error("OCR_SPACE_API_KEY nao configurada")
        return ""

    url = "https://api.ocr.space/parse/image"
    file_bytes = image_path.read_bytes()
    filename = image_path.name

    # Build multipart/form-data manually (no extra dependencies)
    boundary = "----PythonFormBoundary7MA4YWxkTrZu0gW"
    body = b""

    # API key field
    body += ("--{}\r\n".format(boundary)).encode()
    body += b"Content-Disposition: form-data; name=\"apikey\"\r\n\r\n"
    body += api_key.encode() + b"\r\n"

    # Language
    body += ("--{}\r\n".format(boundary)).encode()
    body += b"Content-Disposition: form-data; name=\"language\"\r\n\r\n"
    body += b"por\r\n"

    # Scale (better for small text)
    body += ("--{}\r\n".format(boundary)).encode()
    body += b"Content-Disposition: form-data; name=\"scale\"\r\n\r\n"
    body += b"true\r\n"

    # Detect orientation
    body += ("--{}\r\n".format(boundary)).encode()
    body += b"Content-Disposition: form-data; name=\"detectOrientation\"\r\n\r\n"
    body += b"true\r\n"

    # OCR Engine 2 — better for documents/forms
    body += ("--{}\r\n".format(boundary)).encode()
    body += b"Content-Disposition: form-data; name=\"OCREngine\"\r\n\r\n"
    body += b"2\r\n"

    # File
    body += ("--{}\r\n".format(boundary)).encode()
    body += 'Content-Disposition: form-data; name="file"; filename="{}"\r\n'.format(filename).encode()
    body += b"Content-Type: application/octet-stream\r\n\r\n"
    body += file_bytes + b"\r\n"

    body += ("--{}--\r\n".format(boundary)).encode()

    headers = {
        "Content-Type": "multipart/form-data; boundary={}".format(boundary),
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        logger.error("OCR.space API falhou: %s", e)
        return ""

    if data.get("IsErroredOnProcessing"):
        error_msg = data.get("ErrorMessage", ["Erro desconhecido"])
        logger.error("OCR.space erro: %s", error_msg)
        return ""

    # Combine text from all parsed results
    texts = []
    for result in data.get("ParsedResults", []):
        texts.append(result.get("ParsedText", ""))

    return "\n".join(texts)


# ---------------------------------------------------------------------------
# Local Tesseract preprocessing + multi-pass
# ---------------------------------------------------------------------------

def _prep_binarize(img: "Image.Image") -> "Image.Image":
    if img.mode != "L":
        img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda x: 255 if x > 140 else 0, "1")
    return img


def _prep_grayscale(img: "Image.Image") -> "Image.Image":
    if img.mode != "L":
        img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    return img


def _prep_color(img: "Image.Image") -> "Image.Image":
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    return img


def _ocr_multipass(image_path: Path) -> str:
    """Run Tesseract with multiple preprocessing variants, return combined text."""
    img = Image.open(image_path)

    min_width = 2000
    if img.width < min_width:
        scale = min_width / img.width
        img = img.resize(
            (int(img.width * scale), int(img.height * scale)),
            Image.LANCZOS,
        )

    lang = "por+eng"
    texts: List[str] = []

    for prep_fn, psm_config in [
        (_prep_binarize, "--psm 6"),
        (_prep_grayscale, "--psm 3"),
        (_prep_color, "--psm 6"),
    ]:
        processed = prep_fn(img.copy())
        try:
            text = pytesseract.image_to_string(processed, lang=lang, config=psm_config)
        except pytesseract.TesseractError:
            try:
                text = pytesseract.image_to_string(processed, lang="eng", config=psm_config)
            except pytesseract.TesseractError:
                text = ""
        texts.append(text)

    return "\n".join(texts)


# ---------------------------------------------------------------------------
# OCR-tolerant regex patterns
# ---------------------------------------------------------------------------

OCR_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("km_inicial", re.compile(r"(?:KM|km|Km).?(?:INICIAL|INIC\w*|IN\w*)\s*[:\|]?\s*(\d{2,3}\+\d{2,3})", re.IGNORECASE)),
    ("km_final", re.compile(r"(?:KM|km|Km).?(?:FINAL|FIN\w*)\s*[:\|]?\s*(\d{2,3}\+\d{2,3})", re.IGNORECASE)),
    ("extensao", re.compile(r"[EÉe]xt?ens\w*\s*\(?m?\)?\s*[:\|]?\s*([\d.,]+)", re.IGNORECASE)),
    ("largura", re.compile(r"[Ll]argura\s*\(?m?\)?\s*[=:\|]?\s*([\d.,]+)", re.IGNORECASE)),
    ("altura", re.compile(r"[Aa]ltura\s*\(?m?\)?\s*[:\|]?\s*([\d.,]+)", re.IGNORECASE)),
    ("coord_x_inicio", re.compile(r"[Ii]n\w{0,6}\s*[CcGg]oord\w*\s*[Xx]\s*[:\|]?\s*([-\d.,]+)", re.IGNORECASE)),
    ("coord_y_inicio", re.compile(r"[Ii]n\w{0,6}\s*[CcGg]oord\w*\s*[Yy]\s*[:\|]?\s*([-\d.,]+)", re.IGNORECASE)),
    ("coord_x_fim", re.compile(r"[Ff]im\s*[CcGg]oord\w*\s*[Xx]\s*[:\|]?\s*([-\d.,]+)", re.IGNORECASE)),
    ("coord_y_fim", re.compile(r"[Ff]im\s*[CcGg]oord\w*\s*[Yy]\s*[:\|]?\s*([-\d.,]+)", re.IGNORECASE)),
    ("estado_conservacao", re.compile(
        r"(?:[Cc]onserv|[Cc]omerv|[Cc]onierv)\w*\s*[:\|]?\s*(REGULAR|PREC[ÁA]RIO|BOM|RUIM|NOVO|P[ÉE]SSIMO)",
        re.IGNORECASE,
    )),
    ("ambiente", re.compile(r"[Aa]mb\w*\s*[:\|]?\s*(URBANO|RURAL)", re.IGNORECASE)),
    ("material", re.compile(r"[Mm]at\w*[li]a[li]\s*[:\|]?\s*(CONCRE.?O|ALVENARIA|METAL\w*|PEDRA|PVC)", re.IGNORECASE)),
    ("tipo", re.compile(r"Tipo\s*[:\|]?\s*(MF?C\s*[/\s.]?\s*[A-Za-z0-9]{1,4})", re.IGNORECASE)),
    ("identificacao", re.compile(r"(MF\s*381\s*MG\s*\d{2,3}\+\d{2,3}\s*L?\s*\d?)", re.IGNORECASE)),
    ("inspection_date", re.compile(r"(?:Data|Insp|ata)\w*\.?\s*[:\|\]]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE)),
    ("reparar", re.compile(r"[Rr]eparar\s*[:\|]?\s*(Sim|S[iI1]m|N[ãaÃA]o|Nao)", re.IGNORECASE)),
    ("limpeza", re.compile(r"[Ll]impeza\s*[:\|]?\s*(Sim|S[iI1]m|N[ãaÃA]o|Nao)", re.IGNORECASE)),
    ("implantar", re.compile(r"[Ii]mplantar\s*[:\|]?\s*(Sim|S[iI1]m|N[ãaÃA]o|Nao)", re.IGNORECASE)),
]

OCR_FALLBACK_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("estado_conservacao", re.compile(r"\b(REGULAR|PREC.?RIO|P.?SSIMO|BOM|RUIM|NOVO)\b", re.IGNORECASE)),
    ("ambiente", re.compile(r"\b(URBANO|RURAL)\b", re.IGNORECASE)),
    ("material", re.compile(r"\b(CONCRE.?O|ALVENARIA|METAL\w*|PEDRA|PVC)\b", re.IGNORECASE)),
    ("tipo", re.compile(r"\b(M[FY][CG]\s*[/\s.]?\s*[A-Za-z0-9]{1,4})\b", re.IGNORECASE)),
    ("km_inicial", re.compile(r"\b(\d{3}\+\d{3})\b")),
    ("identificacao", re.compile(r"(MF\s*381\s*MG\s*\d{2,3}\+\d{2,3}\s*L?\s*\d?)", re.IGNORECASE)),
]


def _extract_ocr_fields(text: str) -> Dict[str, Optional[str]]:
    """Extract fields using OCR-tolerant patterns."""
    fields: Dict[str, Optional[str]] = {}

    for field_name, pattern in OCR_PATTERNS:
        match = pattern.search(text)
        if match:
            fields[field_name] = match.group(1).strip()

    for field_name, pattern in OCR_FALLBACK_PATTERNS:
        if not fields.get(field_name):
            match = pattern.search(text)
            if match:
                fields[field_name] = match.group(1).strip()

    if fields.get("km_inicial") and not fields.get("km_final"):
        km_pattern = re.compile(r"\b(\d{3}\+\d{3})\b")
        all_kms = km_pattern.findall(text)
        unique_kms = list(dict.fromkeys(all_kms))
        if len(unique_kms) >= 2 and unique_kms[0] == fields["km_inicial"]:
            fields["km_final"] = unique_kms[1]

    return fields


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def _build_record(filename: str, full_text: str, use_standard_patterns: bool = True) -> DrainageRecord:
    """Build a DrainageRecord from OCR-extracted text."""
    warnings: List[str] = []

    ocr_fields = _extract_ocr_fields(full_text)

    if use_standard_patterns:
        # Local Tesseract: text is single-line label:value, standard patterns work
        standard_fields = extract_fields_from_text(full_text)
        merged: Dict[str, Optional[str]] = {}
        all_keys = set(list(standard_fields.keys()) + list(ocr_fields.keys()))
        for key in all_keys:
            std_val = standard_fields.get(key)
            ocr_val = ocr_fields.get(key)
            merged[key] = std_val if std_val else ocr_val
    else:
        # Cloud API: two-column text, standard patterns mismatch — use OCR only
        merged = {k: v for k, v in ocr_fields.items()}

    confidence = compute_confidence(merged)
    if confidence < 0.5:
        warnings.append(
            "Baixa confianca na extracao OCR ({:.0%}) — verifique manualmente".format(confidence)
        )

    lat_inicio = normalize_coordinate(parse_brazilian_float(merged.get("coord_x_inicio")))
    lon_inicio = normalize_coordinate(parse_brazilian_float(merged.get("coord_y_inicio")))
    lat_fim = normalize_coordinate(parse_brazilian_float(merged.get("coord_x_fim")))
    lon_fim = normalize_coordinate(parse_brazilian_float(merged.get("coord_y_fim")))

    warnings.extend(validate_brazil_coordinate(lat_inicio, lon_inicio))
    warnings.extend(validate_brazil_coordinate(lat_fim, lon_fim))

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


def extract_record_from_image(image_path: Path) -> DrainageRecord:
    """Extract a DrainageRecord from a JPEG/PNG image of an ANTT drainage form.

    Uses local Tesseract (multi-pass) when available.
    Falls back to OCR.space cloud API for serverless environments.
    """
    filename = image_path.name
    logger.info("Processando imagem (OCR): %s", filename)

    # Strategy 1: Local Tesseract (best quality, multi-pass)
    if TESSERACT_AVAILABLE:
        full_text = _ocr_multipass(image_path)
        if full_text.strip():
            return _build_record(filename, full_text, use_standard_patterns=True)

    # Strategy 2: OCR.space cloud API (two-column text — only use OCR patterns)
    if settings.ocr_space_api_key:
        logger.info("%s: usando OCR.space API", filename)
        full_text = _ocr_via_api(image_path)
        if full_text.strip():
            return _build_record(filename, full_text, use_standard_patterns=False)

    # No OCR available
    return DrainageRecord(
        source_filename=filename,
        confidence=0.0,
        warnings=["OCR indisponivel. Configure OCR_SPACE_API_KEY ou instale Tesseract localmente."],
    )
