import json
import logging

from sqlalchemy.orm import Session

from app.models import Order
from app.repositories import order_repository as repo

logger = logging.getLogger(__name__)


def order_to_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "customer": order.customer,
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "items": [
            {"id": i.id, "sku": i.sku, "description": i.description, "quantity": i.quantity}
            for i in order.items
        ],
    }


def get_health(db: Session) -> dict:
    db_ok = repo.check_db_alive(db)
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unavailable"}


def get_stats(db: Session) -> dict:
    return {
        "orders": {
            "total": repo.count_orders(db),
            "open": repo.count_orders_by_status(db, "open"),
            "cancelled": repo.count_orders_by_status(db, "cancelled"),
        },
        "items": {"total": repo.count_items(db)},
    }


def create_order(db: Session, customer: str) -> dict:
    order = repo.create_order(db, customer)
    logger.info(json.dumps({"event": "order_created", "order_id": order.id, "customer": order.customer}))
    return order_to_dict(order)


def list_orders(db: Session) -> list[dict]:
    return [order_to_dict(o) for o in repo.get_all_orders(db)]


def get_order(db: Session, order_id: str) -> dict | None:
    order = repo.get_order_by_id(db, order_id)
    if not order:
        return None
    return order_to_dict(order)


def add_item(db: Session, order_id: str, sku: str, description: str, quantity: int) -> dict | None:
    order = repo.get_order_by_id(db, order_id)
    if not order:
        return None
    item = repo.add_item_to_order(db, order_id, sku, description, quantity)
    return {"id": item.id, "sku": item.sku, "description": item.description, "quantity": item.quantity}


def list_items(db: Session, order_id: str) -> list[dict] | None:
    order = repo.get_order_by_id(db, order_id)
    if not order:
        return None
    return [
        {"id": i.id, "sku": i.sku, "description": i.description, "quantity": i.quantity}
        for i in order.items
    ]


def cancel_order(db: Session, order_id: str) -> bool:
    order = repo.get_order_by_id(db, order_id)
    if not order:
        return False
    repo.cancel_order(db, order)
    return True
