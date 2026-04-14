"""Regex-based field extraction and normalization for ANTT drainage PDFs."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Number helpers
# ---------------------------------------------------------------------------

def parse_brazilian_float(value: Optional[str]) -> Optional[float]:
    """Parse a number in Brazilian format (comma as decimal separator).

    Handles: "180,00" -> 180.0, "0.15" -> 0.15, "-18.91475" -> -18.91475,
             "1.234,56" -> 1234.56
    """
    if not value:
        return None
    cleaned = value.strip().replace(" ", "")
    if not cleaned:
        return None
    # If contains comma but no dot -> Brazilian format
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    # If contains both -> assume comma is decimal (e.g. "1.234,56")
    elif "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_coordinate(value: Optional[float]) -> Optional[float]:
    """Normalize coordinates that may be in a scaled format.

    The PDFs sometimes show coordinates like -1891086.000000 instead of -18.91086.
    If the absolute value exceeds 180, try dividing by powers of 10 to find a
    plausible lat/long.

    Also validates that the result is within Brazilian territory bounds:
    - Latitude:  -34.0 to 6.0
    - Longitude: -74.0 to -34.0
    """
    if value is None:
        return None
    if -180.0 <= value <= 180.0:
        return round(value, 6)
    # Try dividing by 10^n to bring into range
    abs_val = abs(value)
    for power in range(1, 10):
        candidate = abs_val / (10 ** power)
        if candidate <= 180.0:
            result = round(-candidate if value < 0 else candidate, 6)
            logger.debug(
                "Coordenada normalizada: %s -> %s (dividido por 10^%d)",
                value, result, power,
            )
            return result
    return value  # Return as-is if normalization fails


def validate_brazil_coordinate(
    lat: Optional[float], lon: Optional[float]
) -> List[str]:
    """Validate that coordinates are within Brazilian territory. Returns warnings."""
    warnings: List[str] = []
    if lat is not None and not (-34.0 <= lat <= 6.0):
        warnings.append(f"Latitude {lat} fora dos limites do Brasil (-34 a 6)")
    if lon is not None and not (-74.0 <= lon <= -34.0):
        warnings.append(f"Longitude {lon} fora dos limites do Brasil (-74 a -34)")
    return warnings


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Each pattern is (field_name, compiled_regex_with_capture_group)
FIELD_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    (
        "inspection_date",
        re.compile(r"Data\s*Insp\.?\s*:?\s*([\d]{1,2}[/\-][\d]{1,2}[/\-][\d]{2,4})", re.IGNORECASE),
    ),
    (
        "identificacao",
        re.compile(r"IDENTIFICA[ÇC][ÃA]O\s*:?\s*(.+?)(?:\s*KM\s*INICIAL|\s*\n)", re.IGNORECASE),
    ),
    (
        "km_inicial",
        re.compile(r"KM\s*INICIAL\s*:?\s*([\d]+\+[\d]+)", re.IGNORECASE),
    ),
    (
        "km_final",
        re.compile(r"KM\s*FINAL\s*:?\s*([\d]+\+[\d]+)", re.IGNORECASE),
    ),
    (
        "extensao",
        re.compile(r"EXTENS[ÃA]O\s*\(?m?\)?\s*:?\s*([\d.,]+)", re.IGNORECASE),
    ),
    (
        "largura",
        re.compile(r"Largura\s*[\(（]?\s*m?\s*[\)）]?\s*[=:]?\s*([\d.,]+)", re.IGNORECASE),
    ),
    (
        "altura",
        re.compile(r"Altura\s*\(?m?\)?\s*:?\s*([\d.,]+)", re.IGNORECASE),
    ),
    (
        "coord_x_inicio",
        re.compile(r"In[ií]cio\s*Coordenada\s*X\s*:?\s*([-\d.,]+)", re.IGNORECASE),
    ),
    (
        "coord_x_fim",
        re.compile(r"Fim\s*Coordenada\s*X\s*:?\s*([-\d.,]+)", re.IGNORECASE),
    ),
    (
        "coord_y_inicio",
        re.compile(r"In[ií]cio\s*Coordenada\s*Y\s*:?\s*([-\d.,]+)", re.IGNORECASE),
    ),
    (
        "coord_y_fim",
        re.compile(r"Fim\s*Coordenada\s*Y\s*:?\s*([-\d.,]+)", re.IGNORECASE),
    ),
    (
        "tipo",
        re.compile(
            r"Tipo\s*:?\s*"
            r"(?!(?:Material|Ambiente|Estado|Conserva|Reparar|Limpeza|Implantar|"
            r"REGULAR|BOM|RUIM|Prec[áa]rio|P[ée]ssimo|"
            r"CONCRETO|METAL|PL[ÁA]STICO|HDPE|PVC|ARGAMASSA)\b)"
            r"([A-Za-z0-9/]+(?:\s+(?!(?:Estado|Material|Ambiente|Conserva|Reparar|Limpeza|Implantar|de)\b)[A-Za-z0-9]+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        "estado_conservacao",
        re.compile(
            r"Estado\s*de\s*Conserva[çc][ãa]o\s*:?\s*(REGULAR|PREC[ÁA]RIO|BOM|RUIM|NOVO|P[ÉE]SSIMO)",
            re.IGNORECASE,
        ),
    ),
    (
        "material",
        re.compile(r"Material\s*:?\s*([A-Za-zÀ-ÿ]+)", re.IGNORECASE),
    ),
    (
        "ambiente",
        re.compile(r"Ambiente\s*:?\s*(URBANO|RURAL)", re.IGNORECASE),
    ),
]

DIAG_PATTERNS: Dict[str, "re.Pattern[str]"] = {
    "reparar": re.compile(r"Reparar\s*[:\s]*(Sim|N[ãa]o)", re.IGNORECASE),
    "limpeza": re.compile(r"Limpeza\s*[:\s]*(Sim|N[ãa]o)", re.IGNORECASE),
    "limpeza_extensao": re.compile(r"Limpeza\s*.*?(Sim)\s*[\s:]*([\d.,]+)", re.IGNORECASE),
    "implantar": re.compile(r"Implantar\s*[:\s]*(Sim|N[ãa]o)", re.IGNORECASE),
}

REQUIRED_FIELDS = ["km_inicial", "extensao", "largura", "tipo", "estado_conservacao", "ambiente"]


# ---------------------------------------------------------------------------
# Extraction from raw text
# ---------------------------------------------------------------------------

def extract_fields_from_text(text: str) -> Dict[str, Optional[str]]:
    """Extract all fields from raw PDF text using regex patterns.

    Returns a dict with field names -> raw string values (before type conversion).
    """
    fields: Dict[str, Optional[str]] = {}

    for field_name, pattern in FIELD_PATTERNS:
        match = pattern.search(text)
        if match:
            fields[field_name] = match.group(1).strip()
        else:
            fields[field_name] = None

    # Diagnostico
    for diag_name, pattern in DIAG_PATTERNS.items():
        match = pattern.search(text)
        if match:
            if diag_name == "limpeza_extensao":
                fields[diag_name] = match.group(2).strip() if match.group(1) else None
            else:
                fields[diag_name] = match.group(1).strip()
        else:
            fields[diag_name] = None

    return fields


def parse_sim_nao(value: Optional[str]) -> Optional[bool]:
    """Convert 'Sim'/'Nao' to bool."""
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized == "sim":
        return True
    if normalized in ("não", "nao", "no"):
        return False
    return None


def derive_estaca(identificacao: Optional[str], km_fallback: Optional[str] = None) -> Optional[str]:
    """Derive the 'Estaca' value from the identification number.

    Example: "MF 381 MG 156+080 L 1" -> the km portion "156+080" is used as estaca.
    Falls back to km_fallback if identificacao has no km marker.
    """
    if identificacao:
        match = re.search(r"(\d+\+\d+)", identificacao)
        if match:
            return match.group(1)
    if km_fallback:
        match = re.search(r"(\d+\+\d+)", km_fallback)
        if match:
            return match.group(1)
    return None


def compute_confidence(fields: Dict[str, Optional[str]]) -> float:
    """Compute extraction confidence as ratio of required fields found."""
    found = sum(1 for f in REQUIRED_FIELDS if fields.get(f))
    return found / len(REQUIRED_FIELDS)
