# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Visão Geral

Aplicação web que processa PDFs e imagens de monitoração de drenagem da ANTT (BR-381) e gera um Excel consolidado. Backend em Python/FastAPI, frontend em React/TypeScript/Vite. Deploy via Vercel (serverless).

## Comandos

### Backend
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8001

# Testes
pytest tests/ -v
pytest tests/test_field_parser.py -v  # testa só o parser
```

### Frontend
```bash
cd frontend
npm run dev          # Dev server (proxy /api → localhost:8001)
npm run build        # TypeScript check + production build
npm run lint         # ESLint
```

## API Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| POST | /api/process | Upload síncrono (usado no Vercel — retorna Excel em base64) |
| POST | /api/upload | Upload assíncrono, retorna job_id |
| GET | /api/status/{job_id} | Progresso + resultados por arquivo |
| GET | /api/download/{job_id} | Download do .xlsx consolidado |
| DELETE | /api/job/{job_id} | Cleanup de job e arquivos temporários |
| GET | /health | Health check + versão |

O frontend usa `/api/process` (síncrono). Os endpoints assíncronos existem mas não são chamados pelo frontend atual.

## Arquitetura

### Serverless (Vercel)
- `api/index.py` — Entry point do Vercel; importa o app FastAPI do backend
- `vercel.json` — Todas as rotas `/api/*` vão para `api/index.py`; timeout 60s
- `requirements.txt` (raiz) — Dependências Python para o Vercel (diferente de `backend/requirements.txt`)

### Backend (6 serviços)
- `services/field_parser.py` — 15+ regex PT-BR, normalização de floats brasileiros (`180,00` → `180.0`), coordenadas
- `services/pdf_extractor.py` — pdfplumber (tabela + texto); fallback pdfminer.six; tabela tem prioridade sobre texto
- `services/image_extractor.py` — pytesseract local; fallback OCR.space cloud (Engine 2, lógica de reassembly de 2 colunas)
- `services/excel_generator.py` — openpyxl: formato exato ANTT (14 colunas, 3 grupos, aba Metadados)
- `services/processing_pipeline.py` — ThreadPoolExecutor (4 workers) + threading.Lock para progresso
- `routers/upload.py` — REST endpoints + job store in-memory (`_jobs: Dict[str, JobState]`)

### Frontend (4 componentes principais)
- `DropZone.tsx` — Drag-and-drop para PDFs e imagens
- `FileList.tsx` — Lista com tamanho total e "Limpar todos"
- `ProcessingStatus.tsx` — Barra de progresso + contadores + warnings
- `ResultsPanel.tsx` — Download Excel (decodifica base64) + Novo Lote

## Fluxo de Extração

```
PDF  → pdfplumber.extract_tables() → busca labels (KM INICIAL, EXTENSÃO...)
     → pdfplumber.extract_text()   → regex patterns (15+ campos PT-BR)
     → Merge (tabela prioridade)   → normalização (floats BR, coordenadas)

IMG  → pytesseract (local) OU OCR.space (cloud fallback)
     → extract_fields_from_text()  → mesmo parser de regex

→ DrainageRecord → Excel via openpyxl
```

## Como Adicionar Novos Campos

1. Adicionar campo no `DrainageRecord` dataclass (`domain/drainage_record.py`)
2. Adicionar regex pattern em `FIELD_PATTERNS` (`services/field_parser.py`)
3. Adicionar label em `_LABEL_MAP` (`services/pdf_extractor.py`)
4. Mapear o campo no `extract_record()` (`services/pdf_extractor.py`)
5. Adicionar coluna em `COLUMNS` (`services/excel_generator.py`)
6. Adicionar ao `row_data` no loop de dados (`services/excel_generator.py`)
7. Adicionar testes em `tests/test_field_parser.py`

## Particularidades

- **Coordenadas escalonadas**: `-1891086.000000` é normalizado para `-18.91086` automaticamente
- **Formato brasileiro**: `180,00` e `1.234,56` são parseados corretamente
- **Estaca derivada**: Extraída do campo IDENTIFICAÇÃO (`MF 381 MG 156+080 L 1` → `156+080`)
- **Registros ordenados**: Excel ordena por km_inicial automaticamente
- **Python 3.9+**: Type hints usam `Optional[str]` (não `str | None`)
- **Dois requirements.txt**: `backend/requirements.txt` (desenvolvimento local) e `requirements.txt` raiz (Vercel deploy)
