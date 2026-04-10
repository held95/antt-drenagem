"""Tests for field_parser module."""

import pytest

from app.services.field_parser import (
    compute_confidence,
    derive_estaca,
    extract_fields_from_text,
    normalize_coordinate,
    parse_brazilian_float,
    parse_sim_nao,
    validate_brazil_coordinate,
)


# ---------------------------------------------------------------------------
# parse_brazilian_float
# ---------------------------------------------------------------------------

class TestParseBrazilianFloat:
    def test_brazilian_comma(self):
        assert parse_brazilian_float("180,00") == 180.0

    def test_international_dot(self):
        assert parse_brazilian_float("0.15") == 0.15

    def test_negative(self):
        assert parse_brazilian_float("-18.91475") == -18.91475

    def test_mixed_format(self):
        assert parse_brazilian_float("1.234,56") == 1234.56

    def test_none(self):
        assert parse_brazilian_float(None) is None

    def test_empty_string(self):
        assert parse_brazilian_float("") is None

    def test_whitespace(self):
        assert parse_brazilian_float("  180,00  ") == 180.0

    def test_invalid(self):
        assert parse_brazilian_float("abc") is None


# ---------------------------------------------------------------------------
# normalize_coordinate
# ---------------------------------------------------------------------------

class TestNormalizeCoordinate:
    def test_normal_range(self):
        assert normalize_coordinate(-18.91) == -18.91

    def test_scaled_value(self):
        result = normalize_coordinate(-1891086.0)
        assert result is not None
        assert abs(result - (-18.91086)) < 0.001

    def test_zero(self):
        assert normalize_coordinate(0.0) == 0.0

    def test_none(self):
        assert normalize_coordinate(None) is None

    def test_positive_scaled(self):
        result = normalize_coordinate(42618530.0)
        assert result is not None
        assert 0 < result < 180


# ---------------------------------------------------------------------------
# validate_brazil_coordinate
# ---------------------------------------------------------------------------

class TestValidateBrazilCoordinate:
    def test_valid(self):
        warnings = validate_brazil_coordinate(-18.91, -42.61)
        assert warnings == []

    def test_invalid_lat(self):
        warnings = validate_brazil_coordinate(50.0, -42.61)
        assert len(warnings) == 1
        assert "Latitude" in warnings[0]

    def test_invalid_lon(self):
        warnings = validate_brazil_coordinate(-18.91, 10.0)
        assert len(warnings) == 1
        assert "Longitude" in warnings[0]

    def test_none_values(self):
        warnings = validate_brazil_coordinate(None, None)
        assert warnings == []


# ---------------------------------------------------------------------------
# derive_estaca
# ---------------------------------------------------------------------------

class TestDeriveEstaca:
    def test_from_identificacao(self):
        assert derive_estaca("MF 381 MG 156+080 L 1") == "156+080"

    def test_from_km_fallback(self):
        assert derive_estaca(None, km_fallback="156+390") == "156+390"

    def test_identificacao_priority(self):
        assert derive_estaca("MF 381 MG 156+080 L 1", km_fallback="999+000") == "156+080"

    def test_none(self):
        assert derive_estaca(None) is None

    def test_no_km_in_string(self):
        assert derive_estaca("no km marker here") is None


# ---------------------------------------------------------------------------
# parse_sim_nao
# ---------------------------------------------------------------------------

class TestParseSimNao:
    def test_sim(self):
        assert parse_sim_nao("Sim") is True

    def test_nao(self):
        assert parse_sim_nao("Não") is False

    def test_nao_ascii(self):
        assert parse_sim_nao("Nao") is False

    def test_none(self):
        assert parse_sim_nao(None) is None

    def test_empty(self):
        assert parse_sim_nao("") is None


# ---------------------------------------------------------------------------
# extract_fields_from_text
# ---------------------------------------------------------------------------

SAMPLE_TEXT = """
MONITORAÇÃO DE DRENAGEM
Drenagem Superficial Rod. BR-381
Data Insp.: 27/01/2025
IDENTIFICAÇÃO  MF 381 MG 156+300 L 1   KM INICIAL  156+080
EXTENSÃO (m)  180,00  KM FINAL  156+390
Largura (m)  0,15  Altura (m)  0,2
Início Coordenada X  -18,91475  Fim Coordenada X  -1891086,000000
Início Coordenada Y  -42,618530  Fim Coordenada Y  -420125,000000
Tipo  MFC/VG  Estado de Conservação  REGULAR
Material  CONCRETO  Ambiente  URBANO
Reparar  Não
Limpeza  Sim  20,80
Implantar  Não
"""


class TestExtractFieldsFromText:
    def test_all_fields_present(self):
        fields = extract_fields_from_text(SAMPLE_TEXT)
        assert fields["inspection_date"] == "27/01/2025"
        assert fields["km_inicial"] == "156+080"
        assert fields["km_final"] == "156+390"
        assert fields["extensao"] == "180,00"
        assert fields["largura"] == "0,15"
        assert fields["altura"] == "0,2"
        assert fields["tipo"] == "MFC/VG"
        assert fields["estado_conservacao"] == "REGULAR"
        assert fields["material"] == "CONCRETO"
        assert fields["ambiente"] == "URBANO"

    def test_diagnostico(self):
        fields = extract_fields_from_text(SAMPLE_TEXT)
        assert fields["reparar"] == "Não"
        assert fields["limpeza"] == "Sim"
        assert fields["limpeza_extensao"] == "20,80"
        assert fields["implantar"] == "Não"

    def test_coordinates(self):
        fields = extract_fields_from_text(SAMPLE_TEXT)
        assert fields["coord_x_inicio"] == "-18,91475"
        assert fields["coord_y_inicio"] == "-42,618530"


# ---------------------------------------------------------------------------
# compute_confidence
# ---------------------------------------------------------------------------

class TestComputeConfidence:
    def test_all_found(self):
        fields = {
            "km_inicial": "156+080",
            "extensao": "180",
            "largura": "0.15",
            "tipo": "MFC",
            "estado_conservacao": "REGULAR",
            "ambiente": "URBANO",
        }
        assert compute_confidence(fields) == 1.0

    def test_half_found(self):
        fields = {
            "km_inicial": "156+080",
            "extensao": "180",
            "largura": "0.15",
        }
        assert compute_confidence(fields) == 0.5

    def test_none_found(self):
        assert compute_confidence({}) == 0.0
