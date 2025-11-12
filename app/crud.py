from __future__ import annotations

import re
from datetime import datetime
from typing import List

from sqlalchemy import case, func
from sqlmodel import Session, select

from .menu_data import DEFAULT_MENU_ITEMS
from .models import MenuItem, Order


# -------------------------
# Order operations
# -------------------------

def list_orders(session: Session) -> List[Order]:
    statement = select(Order).order_by(Order.order_date.desc(), Order.id.desc())
    return list(session.exec(statement))


def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)


def create_order(session: Session, data: dict) -> Order:
    now = datetime.utcnow()
    order = Order(**data)
    order.order_date = order.order_date or now
    order.created_at = now
    order.updated_at = now
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def update_order(session: Session, order: Order, updates: dict) -> Order:
    for key, value in updates.items():
        if value is None:
            continue
        setattr(order, key, value)
    order.updated_at = datetime.utcnow()
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def delete_order(session: Session, order: Order) -> None:
    session.delete(order)
    session.commit()


def compute_summary(session: Session) -> dict:
    total_orders = session.exec(select(func.count(Order.id))).one()
    unpaid_orders = session.exec(select(func.count()).where(Order.is_paid == False)).one()  # noqa: E712
    total_quantity = session.exec(select(func.coalesce(func.sum(Order.quantity), 0))).one()

    breakdown_stmt = (
        select(
            Order.menu_item_id,
            Order.menu_item_name,
            func.coalesce(func.sum(Order.quantity), 0),
            func.coalesce(
                func.sum(case((Order.is_paid == False, Order.quantity), else_=0)),  # noqa: E712
                0,
            ),
        )
        .group_by(Order.menu_item_id, Order.menu_item_name)
        .order_by(Order.menu_item_name)
    )
    breakdown = [
        {
            "menu_item_id": row[0],
            "menu_item_name": row[1],
            "total_quantity": int(row[2] or 0),
            "unpaid_quantity": int(row[3] or 0),
        }
        for row in session.exec(breakdown_stmt).all()
    ]

    return {
        "total_orders": int(total_orders or 0),
        "unpaid_orders": int(unpaid_orders or 0),
        "total_quantity": int(total_quantity or 0),
        "menu_breakdown": breakdown,
    }


def group_orders_by_menu(session: Session) -> List[dict]:
    statement = select(Order).order_by(Order.menu_item_name.asc(), Order.order_date.asc(), Order.id.asc())
    orders = session.exec(statement).all()
    grouped: dict[str, dict] = {}
    for order in orders:
        group = grouped.setdefault(
            order.menu_item_id,
            {
                "menu_item_id": order.menu_item_id,
                "menu_item_name": order.menu_item_name,
                "orders": [],
            },
        )
        group["orders"].append(
            {
                "customer_name": order.customer_name,
                "quantity": order.quantity,
                "note": order.note,
                "is_paid": order.is_paid,
            }
        )
    return list(grouped.values())


# -------------------------
# Menu operations
# -------------------------

def list_menu_items(session: Session, *, active_only: bool = False) -> List[MenuItem]:
    statement = select(MenuItem)
    if active_only:
        statement = statement.where(MenuItem.is_active.is_(True))
    statement = statement.order_by(MenuItem.id.asc())
    return list(session.exec(statement))


def get_menu_item(session: Session, menu_item_id: int) -> MenuItem | None:
    return session.get(MenuItem, menu_item_id)


def get_menu_item_by_slug(session: Session, slug: str) -> MenuItem | None:
    statement = select(MenuItem).where(MenuItem.slug == slug)
    return session.exec(statement).first()


def create_menu_item(session: Session, data: dict) -> MenuItem:
    slug = data.get("slug") or data.get("name") or ""
    slug = _generate_unique_slug(session, slug)
    now = datetime.utcnow()
    item = MenuItem(
        slug=slug,
        name=data["name"],
        default_price=data.get("default_price", 0),
        is_active=data.get("is_active", True),
        description=data.get("description"),
        created_at=now,
        updated_at=now,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def update_menu_item(session: Session, menu_item: MenuItem, updates: dict) -> MenuItem:
    if "slug" in updates and updates["slug"]:
        updates["slug"] = _generate_unique_slug(session, updates["slug"], current_id=menu_item.id)
    for key, value in updates.items():
        if value is None:
            continue
        setattr(menu_item, key, value)
    menu_item.updated_at = datetime.utcnow()
    session.add(menu_item)
    session.commit()
    session.refresh(menu_item)
    return menu_item


def delete_menu_item(session: Session, menu_item: MenuItem) -> None:
    in_use = session.exec(
        select(func.count(Order.id)).where(Order.menu_item_id == menu_item.slug)
    ).one()
    if in_use:
        raise ValueError("ไม่สามารถลบเมนูที่มีออเดอร์อยู่แล้วได้")
    session.delete(menu_item)
    session.commit()


def ensure_default_menu_items(session: Session) -> None:
    existing_count = session.exec(select(func.count(MenuItem.id))).one()
    if existing_count:
        return
    now = datetime.utcnow()
    for item in DEFAULT_MENU_ITEMS:
        session.add(
            MenuItem(
                slug=item["slug"],
                name=item["name"],
                default_price=item["default_price"],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()


def _generate_unique_slug(session: Session, base: str, current_id: int | None = None) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", base.strip().lower()).strip("-")
    slug = slug or "menu-item"
    candidate = slug
    suffix = 1
    while True:
        statement = select(MenuItem).where(MenuItem.slug == candidate)
        existing = session.exec(statement).first()
        if existing is None or (current_id is not None and existing.id == current_id):
            return candidate
        suffix += 1
        candidate = f"{slug}-{suffix}"
