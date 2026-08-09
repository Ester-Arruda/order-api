from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Order, Item


def check_db_alive(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def count_orders(db: Session) -> int:
    return db.query(Order).count()


def count_orders_by_status(db: Session, status: str) -> int:
    return db.query(Order).filter(Order.status == status).count()


def count_items(db: Session) -> int:
    return db.query(Item).count()


def create_order(db: Session, customer: str) -> Order:
    order = Order(id=str(uuid4()), customer=customer)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_all_orders(db: Session) -> list[Order]:
    return db.query(Order).all()


def get_order_by_id(db: Session, order_id: str) -> Order | None:
    return db.query(Order).filter(Order.id == order_id).first()


def add_item_to_order(db: Session, order_id: str, sku: str, description: str, quantity: int) -> Item:
    item = Item(id=str(uuid4()), order_id=order_id, sku=sku, description=description, quantity=quantity)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def cancel_order(db: Session, order: Order) -> None:
    order.status = "cancelled"
    db.commit()
