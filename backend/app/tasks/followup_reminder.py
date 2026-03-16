"""
回访提醒定时任务 —— 每天 11:00 扫描当日到期+逾期回访，推送订阅消息给销售
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from app.config import settings
from app.db import get_db_context
from app.models import Sales, StoreOrder
from app.integrations.wechat_mini import send_subscribe_message

logger = logging.getLogger(__name__)


def _normalize(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _parse_date(text: str):
    """尝试从 YYYY-MM-DD / YYYY/MM/DD 解析日期"""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(text[:10], fmt).date()
        except (ValueError, TypeError):
            continue
    return None


FOLLOWUP_RULES = [
    {"type": "D7", "label": "7天回访", "days": 7},
    {"type": "D30", "label": "30天回访", "days": 30},
    {"type": "D60", "label": "60天回访", "days": 60},
    {"type": "D180", "label": "180天回访", "days": 180},
]


def _build_due_items(order_payload: dict, today: date) -> list[dict]:
    """从订单 payload 中提取今日到期或已逾期且未完成的回访节点"""
    if _normalize(order_payload.get("status")) == "已取消":
        return []
    if _normalize(order_payload.get("deliveryStatus")) != "交车通过":
        return []
    delivery_text = _normalize(order_payload.get("deliveryPassedAt"))
    if not delivery_text:
        return []
    delivery_date = _parse_date(delivery_text)
    if not delivery_date:
        return []

    records_raw = order_payload.get("followupRecords")
    done_types = set()
    if isinstance(records_raw, list):
        for r in records_raw:
            if isinstance(r, dict) and r.get("done"):
                done_types.add(_normalize(r.get("type")).upper())

    items = []
    for rule in FOLLOWUP_RULES:
        if rule["type"] in done_types:
            continue
        due_date = delivery_date + timedelta(days=rule["days"])
        if due_date <= today:
            items.append({
                "type": rule["type"],
                "label": rule["label"],
                "dueDateText": due_date.strftime("%Y-%m-%d"),
                "customerName": _normalize(order_payload.get("customerName")),
                "carModel": _normalize(order_payload.get("carModel")),
                "salesOwner": _normalize(order_payload.get("salesBrandText")),
                "orderId": _normalize(order_payload.get("id")),
            })
    return items


def _truncate(s: str, max_len: int = 20) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def run_followup_reminder_job() -> dict:
    """
    扫描所有到期 / 逾期回访，按销售聚合后推送订阅消息。
    同步函数，内部用 asyncio.run 完成异步发送。
    """
    template_id = settings.WX_SUBSCRIBE_TEMPLATE_FOLLOWUP
    if not template_id:
        logger.info("回访提醒: WX_SUBSCRIBE_TEMPLATE_FOLLOWUP 未配置，跳过")
        return {"skipped": True, "reason": "template not configured"}

    today = date.today()
    logger.info(f"回访提醒: 开始扫描 {today}")

    # 1) 查询所有订单
    with get_db_context() as db:
        rows = db.query(StoreOrder).all()
        # 2) 提取到期回访，按 salesOwner 聚合
        sales_items: dict[str, list[dict]] = {}
        for row in rows:
            payload = dict(row.payload) if isinstance(row.payload, dict) else {}
            items = _build_due_items(payload, today)
            for item in items:
                owner = item["salesOwner"]
                if not owner:
                    continue
                sales_items.setdefault(owner, []).append(item)

        if not sales_items:
            logger.info("回访提醒: 今日无到期回访")
            return {"sent": 0, "due_total": 0}

        # 3) 查询所有有 openid 的销售
        all_sales = db.query(Sales).filter(Sales.wx_openid.isnot(None), Sales.wx_openid != "").all()
        sales_map = {s.sales_name: s.wx_openid for s in all_sales}

    # 4) 逐个销售推送
    sent = 0
    total_due = sum(len(v) for v in sales_items.values())

    async def _push_all():
        nonlocal sent
        for sales_name, items in sales_items.items():
            openid = sales_map.get(sales_name)
            if not openid:
                logger.debug(f"回访提醒: 销售 {sales_name} 无 openid，跳过")
                continue

            count = len(items)
            first = items[0]
            msg_data = {
                "thing1": {"value": _truncate(f"您有{count}条回访待处理", 20)},
                "thing2": {"value": _truncate(first["customerName"] or "客户", 20)},
                "thing3": {"value": _truncate(first["label"], 20)},
            }
            page = "subpackages/store/pages/followup-reminder/index"
            try:
                ok = await send_subscribe_message(openid, template_id, msg_data, page)
                if ok:
                    sent += 1
                    logger.info(f"回访提醒: 已推送给 {sales_name}（{count}条）")
                else:
                    logger.warning(f"回访提醒: 推送失败 {sales_name}")
            except Exception as e:
                logger.error(f"回访提醒: 推送异常 {sales_name}: {e}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_push_all())
    except RuntimeError:
        asyncio.run(_push_all())

    logger.info(f"回访提醒: 完成，共 {total_due} 条到期回访，推送 {sent} 位销售")
    return {"sent": sent, "due_total": total_due}
