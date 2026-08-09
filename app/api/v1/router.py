from fastapi import APIRouter

from app.api.v1 import health, orders

router = APIRouter()
router.include_router(health.router)
router.include_router(orders.router)
