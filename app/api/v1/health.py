from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import order_service as service

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    return service.get_health(db)


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    return service.get_stats(db)
