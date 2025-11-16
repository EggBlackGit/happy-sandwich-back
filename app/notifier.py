import logging
from typing import Iterable, List

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


def _format_menu_breakdown(breakdown: List[dict]) -> str:
    if not breakdown:
        return "- ยังไม่มีรายการ"
    lines = []
    for item in breakdown:
        total = item.get("total_quantity", 0)
        name = item.get("menu_item_name", "เมนูไม่ทราบชื่อ")
        lines.append(f"- {name}: {total} ชิ้น")
    return "\n".join(lines)


def notify_order_event(order: Order, menu_breakdown: List[dict], action: str) -> None:
    """Send LINE notification for an order event and include menu summary."""
    settings = get_settings()
    token = settings.line_channel_access_token
    targets: Iterable[str] = settings.line_target_ids
    if not token:
        return

    status_text = "ชำระแล้ว" if order.is_paid else "ยังไม่ชำระ"
    prefix = {
        "create": "🆕 มีออเดอร์ใหม่ 🟢🟢🟢",
        "update": "✏️ อัปเดตออเดอร์ 🟡🟡🟡",
        "delete": "🗑️ ลบออเดอร์ 🔴🔴🔴",
    }.get(action, "📦 ออเดอร์")

    text = (
        f"{prefix}\n"
        f"ลูกค้า: {order.customer_name}\n"
        f"เมนู: {order.menu_item_name} x{order.quantity}\n"
        f"ราคา: {order.price:.0f} บาท\n"
        f"สถานะ: {status_text}\n"
        "\nรายการที่ต้องทำตอนนี้:\n"
        f"{_format_menu_breakdown(menu_breakdown)}"
    )

    if targets:
        for recipient in targets:
            _push(recipient, token, text)
    else:
        _broadcast(token, text)
