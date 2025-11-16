import logging
from typing import Iterable

import httpx

from .config import get_settings
from .models import Order

logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"


def _post_line(url: str, token: str, payload: dict) -> None:
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=5,
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send LINE message: %s", exc)


def _push(recipient: str, token: str, text: str) -> None:
    payload = {
        "to": recipient,
        "messages": [{"type": "text", "text": text}],
    }
    _post_line(LINE_PUSH_URL, token, payload)


def _broadcast(token: str, text: str) -> None:
    payload = {
        "messages": [{"type": "text", "text": text}],
    }
    _post_line(LINE_BROADCAST_URL, token, payload)


def notify_new_order(order: Order) -> None:
    settings = get_settings()
    if settings.line_channel_access_token is None:
        logger.error("line_channel_access_token is empty")
    token = settings.line_channel_access_token
    targets: Iterable[str] = settings.line_target_ids
    if not token:
        return
    text = (
        "มีออเดอร์ใหม่!\n"
        f"ลูกค้า: {order.customer_name}\n"
        f"เมนู: {order.menu_item_name} x{order.quantity}\n"
        f"ราคา: {order.price:.0f} บาท\n"
        f"สถานะ: {'ชำระแล้ว' if order.is_paid else 'ยังไม่ชำระ'}"
    )

    if targets:
        for recipient in targets:
            _push(recipient, token, text)
    else:
        _broadcast(token, text)
