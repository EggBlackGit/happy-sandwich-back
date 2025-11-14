from __future__ import annotations

import csv
import io
from datetime import datetime, time
from typing import Annotated, List

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from . import crud, schemas
from .config import get_settings
from .database import engine, get_session, init_db
from .notifier import notify_new_order

app = FastAPI(title="Happy Sandwich Orders", version="0.1.0")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with Session(engine) as session:
        crud.ensure_default_menu_items(session)

def verify_access_key(
    x_access_key: Annotated[str | None, Header(alias="X-Access-Key")] = None
) -> None:
    if settings.access_key and x_access_key != settings.access_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access key",
        )



AccessGuard = Annotated[None, Depends(verify_access_key)]


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/meta/options", response_model=schemas.OptionsResponse)
def get_options(
    _: AccessGuard,
    session: Session = Depends(get_session),
):
    menu_items = crud.list_menu_items(session, active_only=True)
    return schemas.OptionsResponse(
        menu_items=[
            schemas.MenuOption(
                id=item.slug,
                name=item.name,
                default_price=item.default_price,
                priority=item.priority,
            )
            for item in menu_items
        ],
    )


@app.get("/menu-items", response_model=List[schemas.MenuItemRead])
def list_menu_items(
    active_only: bool = False,
    _: AccessGuard = None,
    session: Session = Depends(get_session),
):
    return crud.list_menu_items(session, active_only=active_only)


@app.post("/menu-items", response_model=schemas.MenuItemRead, status_code=status.HTTP_201_CREATED)
def create_menu_item(
    payload: schemas.MenuItemCreate,
    _: AccessGuard = None,
    session: Session = Depends(get_session),
):
    data = payload.model_dump(exclude_unset=True)
    try:
        return crud.create_menu_item(session, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.put("/menu-items/{menu_item_id}", response_model=schemas.MenuItemRead)
def update_menu_item(
    menu_item_id: int,
    payload: schemas.MenuItemUpdate,
    _: AccessGuard = None,
    session: Session = Depends(get_session),
):
    menu_item = crud.get_menu_item(session, menu_item_id)
    if not menu_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    data = payload.model_dump(exclude_unset=True)
    try:
        return crud.update_menu_item(session, menu_item, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.delete("/menu-items/{menu_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item(
    menu_item_id: int,
    _: AccessGuard = None,
    session: Session = Depends(get_session),
):
    menu_item = crud.get_menu_item(session, menu_item_id)
    if not menu_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    try:
        crud.delete_menu_item(session, menu_item)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/orders", response_model=List[schemas.OrderRead])
def list_orders(
    _: AccessGuard,
    session: Session = Depends(get_session),
):
    return crud.list_orders(session)


@app.post("/orders", response_model=schemas.OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: schemas.OrderCreate,
    _: AccessGuard,
    session: Session = Depends(get_session),
):
    order_dict = payload.model_dump()
    menu_meta = _resolve_menu_item(session, order_dict.get("menu_item_id"))
    order_dict["menu_item_name"] = menu_meta.name
    if order_dict.get("price") is None or order_dict.get("price", 0) <= 0:
        order_dict["price"] = menu_meta.default_price * order_dict.get("quantity", 1)
    order = crud.create_order(session, order_dict)
    print(1111)
    notify_new_order(order)
    return order


@app.put("/orders/{order_id}", response_model=schemas.OrderRead)
def update_order(
    order_id: int,
    payload: schemas.OrderUpdate,
    _: AccessGuard,
    session: Session = Depends(get_session),
):
    order = crud.get_order(session, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "menu_item_id" in updates:
        menu_meta = _resolve_menu_item(session, updates["menu_item_id"])
        updates["menu_item_name"] = menu_meta.name
        if updates.get("price") is None or updates.get("price", 0) <= 0:
            updates["price"] = menu_meta.default_price * updates.get("quantity", order.quantity)
    if not updates:
        return order
    return crud.update_order(session, order, updates)


@app.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(
    order_id: int,
    _: AccessGuard,
    session: Session = Depends(get_session),
):
    order = crud.get_order(session, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    crud.delete_order(session, order)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/orders/mark-paid")
def bulk_update_order_payment(
    payload: schemas.PaymentBulkUpdate,
    _: AccessGuard,
    session: Session = Depends(get_session),
):
    start_dt = datetime.combine(payload.start_date, time.min)
    end_dt = datetime.combine(payload.end_date, time.max)
    updated = crud.update_payment_status_by_date(
        session=session,
        start_date=start_dt,
        end_date=end_dt,
        is_paid=payload.is_paid,
    )
    return {"updated": updated, "is_paid": payload.is_paid}


@app.get("/reports/summary", response_model=schemas.SummaryResponse)
def summary(
    _: AccessGuard,
    session: Session = Depends(get_session),
):
    data = crud.compute_summary(session)
    return schemas.SummaryResponse(**data)


@app.get("/reports/menu-orders", response_model=List[schemas.MenuOrdersGroup])
def menu_orders(
    _: AccessGuard,
    session: Session = Depends(get_session),
):
    groups = crud.group_orders_by_menu(session)
    return [
        schemas.MenuOrdersGroup(
            menu_item_id=group["menu_item_id"],
            menu_item_name=group["menu_item_name"],
            orders=[
                schemas.MenuGroupedOrder(
                    customer_name=item["customer_name"],
                    quantity=item["quantity"],
                    note=item["note"],
                    is_paid=item["is_paid"],
                )
                for item in group["orders"]
            ],
        )
        for group in groups
    ]


@app.get("/orders/export", response_class=PlainTextResponse)
def export_orders(
    _: AccessGuard,
    session: Session = Depends(get_session),
):
    orders = crud.list_orders(session)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "id",
        "customer_name",
        "menu_item_name",
        "quantity",
        "price",
        "note",
        "order_date",
        "is_paid",
    ])
    for order in orders:
        writer.writerow([
            order.id,
            order.customer_name,
            order.menu_item_name,
            order.quantity,
            order.price,
            order.note or "",
            order.order_date.isoformat() if order.order_date else "",
            "paid" if order.is_paid else "pending",
        ])
    csv_content = buffer.getvalue()
    headers = {
        "Content-Disposition": "attachment; filename=orders.csv",
    }
    return PlainTextResponse(content=csv_content, media_type="text/csv", headers=headers)


def _resolve_menu_item(session: Session, menu_item_id: str | None):
    if not menu_item_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="menu_item_id is required")
    menu_item = crud.get_menu_item_by_slug(session, menu_item_id)
    if not menu_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid menu item")
    return menu_item
