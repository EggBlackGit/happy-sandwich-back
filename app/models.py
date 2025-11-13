from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class MenuItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, sa_column_kwargs={"unique": True})
    name: str = Field(index=True)
    default_price: float = Field(default=0, ge=0)
    priority: int = Field(default=100, ge=0, index=True)
    is_active: bool = Field(default=True, index=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_name: str = Field(index=True)
    menu_item_id: str
    menu_item_name: str
    quantity: int = Field(default=1, ge=1)
    price: float = Field(default=0, ge=0)
    note: Optional[str] = None
    order_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    is_paid: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = ["Order", "MenuItem"]
