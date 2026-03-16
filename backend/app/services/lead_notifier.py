"""
线索通知服务 —— 线索分配后推送订阅消息给销售
"""
from __future__ import annotations

import asyncio
import logging
from app.config import settings
from app.integrations.wechat_mini import send_subscribe_message

logger = logging.getLogger(__name__)


def notify_lead_assigned(lead, sales) -> None:
    """
    线索分配后，异步推送订阅消息给销售的小程序。
    在同步上下文中调用（allocation_service 是同步的），内部起 async task。
    """
    template_id = settings.WX_SUBSCRIBE_TEMPLATE_LEAD
    openid = getattr(sales, "wx_openid", None)

    if not template_id or not openid:
        logger.debug(
            f"跳过通知: template_id={'有' if template_id else '无'}, "
            f"openid={'有' if openid else '无'} (sales={sales.sales_id})"
        )
        return

    # 组装订阅消息 data（字段名需与微信后台模板一致，这里用常见字段名）
    customer = getattr(lead, "customer_nickname", "") or "抖音客户"
    service = getattr(lead, "service_type", "") or "咨询"
    car_model = getattr(lead, "car_model", "") or "未知"

    msg_data = {
        "thing1": {"value": _truncate(f"{customer} - {service}", 20)},
        "thing2": {"value": _truncate(car_model, 20)},
        "thing3": {"value": _truncate("抖音私信", 20)},
    }

    page = f"pages/lead-detail?id={lead.lead_id}" if hasattr(lead, "lead_id") else ""

    # 在后台 fire-and-forget 发送
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send(openid, template_id, msg_data, page, sales.sales_id))
    except RuntimeError:
        # 没有 running loop（不太可能在 FastAPI 中发生），忽略
        logger.warning("无法获取事件循环，跳过订阅消息推送")


async def _send(openid: str, template_id: str, data: dict, page: str, sales_id: str):
    """实际发送，捕获异常不影响主流程"""
    try:
        ok = await send_subscribe_message(openid, template_id, data, page)
        if ok:
            logger.info(f"线索通知已推送给销售 {sales_id}")
        else:
            logger.warning(f"线索通知推送失败: sales={sales_id}")
    except Exception as e:
        logger.error(f"线索通知推送异常: {e}")


def _truncate(s: str, max_len: int) -> str:
    """微信订阅消息字段值有长度限制"""
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"
