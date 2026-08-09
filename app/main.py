import logging
import json

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from scalar_fastapi import get_scalar_api_reference

from app.database import engine, Base
from app.models import Order, Item  # noqa: F401 - ensures models register with Base before create_all
from app.api.v1.router import router as v1_router

Base.metadata.create_all(bind=engine)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        return json.dumps(log)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Pedidos",
    description="Projeto base do curso Move Tech — Magalu × Prósper Digital Skills",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

Instrumentator().instrument(app).expose(app)

app.include_router(v1_router)


@app.get("/docs", include_in_schema=False)
def docs():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)
