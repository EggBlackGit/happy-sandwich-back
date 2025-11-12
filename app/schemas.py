from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class OrderBase(BaseModel):
    customer_name: str
    menu_item_id: str
    menu_item_name: str
    quantity: int = 1
    price: float = 0
    note: Optional[str] = None
    order_date: Optional[datetime] = None
    is_paid: bool = False

    @field_validator("order_date", mode="before")
    @classmethod
    def parse_order_date(cls, value: datetime | date | None) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        return datetime.fromisoformat(value)


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    customer_name: Optional[str] = None
    menu_item_id: Optional[str] = None
    menu_item_name: Optional[str] = None
    quantity: Optional[int] = None
    price: Optional[float] = None
    note: Optional[str] = None
    order_date: Optional[datetime] = None
    is_paid: Optional[bool] = None


class OrderRead(OrderBase):
    id: int
    created_at: datetime
    updated_at: datetime


class MenuOption(BaseModel):
    id: str
    name: str
    default_price: float


class MenuItemBase(BaseModel):
    name: str
    slug: Optional[str] = None
    default_price: float
    is_active: bool = True
    description: Optional[str] = None


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    default_price: Optional[float] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class MenuItemRead(MenuItemBase):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime


class OptionsResponse(BaseModel):
    menu_items: List[MenuOption]


class MenuSummary(BaseModel):
    menu_item_id: str
    menu_item_name: str
    total_quantity: int
    unpaid_quantity: int


class SummaryResponse(BaseModel):
    total_orders: int
    unpaid_orders: int
    total_quantity: int
    menu_breakdown: List[MenuSummary]


class MenuGroupedOrder(BaseModel):
    customer_name: str
    quantity: int
    note: Optional[str] = None
    is_paid: bool


class MenuOrdersGroup(BaseModel):
    menu_item_id: str
    menu_item_name: str
    orders: List[MenuGroupedOrder]
