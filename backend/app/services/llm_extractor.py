"""LLM-assisted field gap-fill for ANTT drainage PDFs using Claude API.

This module is optional. If `anthropic` is not installed or ANTHROPIC_API_KEY
is not configured, all functions return empty dicts without raising.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

_ALL_FIELDS = [
    "inspection_date",
    "identificacao",
    "km_inicial",
    "km_final",
    "extensao",
    "largura",
    "altura",
    "coord_x_inicio",
    "coord_y_inicio",
    "coord_x_fim",
    "coord_y_fim",
    "tipo",
    "estado_conservacao",
    "material",
    "ambiente",
    "reparar",
    "limpeza",
    "limpeza_extensao",
    "implantar",
]

_SYSTEM = """\
Você é um extrator de dados de formulários de monitoração de drenagem ANTT (BR-381).
Extraia apenas os campos solicitados do texto do formulário.
Retorne SOMENTE JSON válido com null para campos não encontrados — sem texto adicional.

Formatos obrigatórios:
- km_inicial / km_final: "NNN+NNN" (ex: "156+080")
- inspection_date: "DD/MM/YYYY"
- coordenadas (coord_x_*, coord_y_*): decimal com sinal como string (ex: "-18.91475")
- reparar / limpeza / implantar: "Sim" ou "Não"
- limpeza_extensao: número decimal como string (ex: "20.80")
- estado_conservacao: um de REGULAR, PRECÁRIO, BOM, RUIM, NOVO, PÉSSIMO
- ambiente: URBANO ou RURAL
- material: CONCRETO, ALVENARIA, METAL, PEDRA ou PVC
"""


def extract_missing_fields(
    text: str,
    existing_fields: Dict[str, Optional[str]],
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
) -> Dict[str, str]:
    """Call Claude API to fill only the fields that are None/missing.

    Returns a dict with only the newly found fields (may be empty).
    Never overwrites fields that already have values in existing_fields.
    Safe to call even if anthropic is not installed — returns {} in that case.
    """
    if not _ANTHROPIC_AVAILABLE or not api_key:
        return {}

    missing = [f for f in _ALL_FIELDS if not existing_fields.get(f)]
    if not missing:
        return {}

    fields_list = "\n".join(f"- {f}" for f in missing)
    user_msg = (
        f"Extraia SOMENTE estes campos ausentes do formulário:\n{fields_list}\n\n"
        f"Texto do formulário:\n```\n{text[:4000]}\n```\n\n"
        "Retorne JSON com exatamente estas chaves e null para os não encontrados."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

        data = json.loads(raw)
        # Return only the fields that were missing AND now have a non-null value
        return {k: v for k, v in data.items() if k in missing and v is not None}

    except Exception as e:
        logger.warning("LLM extraction failed: %s", e)
        return {}
