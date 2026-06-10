"""FastAPI app entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.nominatim import client as nominatim_singleton, get_client as get_nominatim
from app.routers import alagamentos, geocode, health, hotspots, rota
from app.valhalla import client as valhalla_singleton, get_client as get_valhalla

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
LOG = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOG.info("startup: valhalla=%s nominatim=%s", settings.valhalla_url, settings.nominatim_url)
    get_valhalla()  # warm singleton
    get_nominatim()
    yield
    LOG.info("shutdown")
    if valhalla_singleton is not None:
        await valhalla_singleton.close()
    if nominatim_singleton is not None:
        await nominatim_singleton.close()


app = FastAPI(
    title="Roteamento Resiliente — backend",
    version="0.1.0",
    description=(
        "Backend que orquestra Valhalla + PostGIS + Nominatim para o modelo ERMAC. "
        "Veja docs/ na raiz do projeto."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(geocode.router)
app.include_router(alagamentos.router)
app.include_router(rota.router)
app.include_router(hotspots.router)
