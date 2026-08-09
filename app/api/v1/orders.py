from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import order_service as service

router = APIRouter()


class ItemIn(BaseModel):
    sku: str
    description: str
    quantity: int


class OrderIn(BaseModel):
    customer: str


@router.post("/orders", status_code=status.HTTP_201_CREATED, tags=["orders"])
def create_order(body: OrderIn, db: Session = Depends(get_db)):
    return service.create_order(db, body.customer)


@router.get("/orders", tags=["orders"])
def list_orders(db: Session = Depends(get_db)):
    return service.list_orders(db)


@router.get("/orders/{order_id}", tags=["orders"])
def get_order(order_id: str, db: Session = Depends(get_db)):
    order = service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return order


@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["orders"])
def cancel_order(order_id: str, db: Session = Depends(get_db)):
    ok = service.cancel_order(db, order_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")


@router.post("/orders/{order_id}/items", status_code=status.HTTP_201_CREATED, tags=["items"])
def add_item(order_id: str, body: ItemIn, db: Session = Depends(get_db)):
    item = service.add_item(db, order_id, body.sku, body.description, body.quantity)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return item


@router.get("/orders/{order_id}/items", tags=["items"])
def list_items(order_id: str, db: Session = Depends(get_db)):
    items = service.list_items(db, order_id)
    if items is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return items
