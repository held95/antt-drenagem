"""FastAPI application for ANTT Drainage PDF Consolidator."""

import logging
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.upload import router as upload_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

VERSION = "1.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("ANTT Drenagem Consolidador v%s iniciado", VERSION)
    logger.info("Upload dir: %s", settings.upload_dir.resolve())
    yield
    # Shutdown: clean up temp files
    if settings.upload_dir.exists():
        shutil.rmtree(settings.upload_dir, ignore_errors=True)
        logger.info("Cleanup: diretorio uploads removido no shutdown")


app = FastAPI(
    title="ANTT Drenagem — Consolidador de PDFs",
    description="Processa PDFs de monitoração de drenagem e gera Excel consolidado",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}
