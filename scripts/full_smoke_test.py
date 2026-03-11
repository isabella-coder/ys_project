#!/usr/bin/env python3
import datetime
import json
import uuid

import requests

BASE = "http://127.0.0.1:8000"
API = f"{BASE}/api/v1"

results = []
ctx = {}


def rec(name, ok, detail="", status=None):
    results.append(
        {
            "name": name,
            "ok": bool(ok),
            "status": status,
            "detail": str(detail)[:300],
        }
    )


def req(
    name,
    method,
    url,
    expected_status=None,
    expect_json_key=None,
    headers=None,
    json_body=None,
    timeout=20,
):
    try:
        response = requests.request(method, url, headers=headers or {}, json=json_body, timeout=timeout)
        try:
            body = response.json()
            payload = body
        except Exception:
            body = response.text[:300]
            payload = None

        ok = True
        if expected_status is not None:
            if isinstance(expected_status, (list, tuple, set)):
                ok = ok and response.status_code in set(expected_status)
            else:
                ok = ok and response.status_code == expected_status
        if expect_json_key:
            ok = ok and isinstance(payload, dict) and expect_json_key in payload

        rec(name, ok, detail=body, status=response.status_code)
        return response, payload
    except Exception as error:
        rec(name, False, detail=error, status="ERR")
        return None, None


# Health
req("health", "GET", f"{BASE}/health", expected_status=200, expect_json_key="status")

# Auth module
_, payload = req("auth.sales", "GET", f"{API}/auth/sales", expected_status=200)
sales = []
if isinstance(payload, dict):
    sales = ((payload.get("data") or {}).get("items") or [])

sales_id = sales[0]["sales_id"] if sales else "sales_mengao"
_, payload = req(
    "auth.login",
    "POST",
    f"{API}/auth/login",
    expected_status=200,
    json_body={"sales_id": sales_id, "password": "sale123"},
)
auth_token = ""
if isinstance(payload, dict) and payload.get("code") == 0:
    auth_token = ((payload.get("data") or {}).get("token") or "")
ctx["sales_id"] = sales_id

if auth_token:
    auth_headers = {"Authorization": f"Bearer {auth_token}"}
    req("auth.me", "GET", f"{API}/auth/me", expected_status=200, headers=auth_headers)

    today = datetime.date.today().isoformat()
    req("stats.daily", "GET", f"{API}/stats/daily?stat_date={today}", expected_status=200, headers=auth_headers)
    req(
        "stats.by-sales",
        "GET",
        f"{API}/stats/by-sales?store_code=BOP&days=7",
        expected_status=200,
        headers=auth_headers,
    )
    req("stats.sla", "GET", f"{API}/stats/sla?stat_date={today}", expected_status=200, headers=auth_headers)
    req(
        "stats.daily-by-sales",
        "GET",
        f"{API}/stats/daily-by-sales?stat_date={today}&store_code=BOP",
        expected_status=200,
        headers=auth_headers,
    )

    lead_payload = {
        "platform": "douyin",
        "source_channel": "live",
        "account_code": "DY-BOP-001",
        "customer_nickname": "测试客户",
        "car_model": "测试车型",
        "service_type": "贴膜",
        "budget_range": "5000-8000",
        "consultation_topic": "smoke",
        "conversation_summary": "smoke test lead",
    }
    _, payload = req("leads.create", "POST", f"{API}/leads", expected_status=200, json_body=lead_payload)
    lead_id = ((payload.get("data") or {}).get("lead_id") if isinstance(payload, dict) else "") or ""

    if lead_id:
        req("leads.list", "GET", f"{API}/leads?page=1&page_size=5", expected_status=200, headers=auth_headers)
        req("leads.detail", "GET", f"{API}/leads/{lead_id}", expected_status=200, headers=auth_headers)
        req(
            "leads.first-reply",
            "POST",
            f"{API}/leads/{lead_id}/first-reply",
            expected_status=200,
            headers=auth_headers,
            json_body={"actor_id": sales_id, "actor_type": "sales", "description": "smoke"},
        )
        req(
            "leads.wechat-invite",
            "POST",
            f"{API}/leads/{lead_id}/wechat-invite",
            expected_status=200,
            headers=auth_headers,
            json_body={
                "actor_id": sales_id,
                "actor_type": "sales",
                "method": "sales_sent",
                "description": "smoke",
            },
        )
        req(
            "leads.wechat-status",
            "PATCH",
            f"{API}/leads/{lead_id}/wechat-status",
            expected_status=200,
            headers=auth_headers,
            json_body={"wechat_status": "success", "actor_id": sales_id, "actor_type": "sales"},
        )
    else:
        for name in [
            "leads.list",
            "leads.detail",
            "leads.first-reply",
            "leads.wechat-invite",
            "leads.wechat-status",
        ]:
            rec(name, False, detail="skip: lead create failed", status="SKIP")
else:
    for name in [
        "auth.me",
        "stats.daily",
        "stats.by-sales",
        "stats.sla",
        "stats.daily-by-sales",
        "leads.create",
        "leads.list",
        "leads.detail",
        "leads.first-reply",
        "leads.wechat-invite",
        "leads.wechat-status",
    ]:
        rec(name, False, detail="skip: auth login failed", status="SKIP")

# Chat module
req("chat.webhook.verify", "GET", f"{API}/chat/douyin/webhook?challenge=smoke_challenge", expected_status=200)
req(
    "chat.test",
    "POST",
    f"{API}/chat/test",
    expected_status=200,
    json_body={"platform": "douyin", "account_code": "DY-BOP-001", "open_id": "smoke_user", "message": "你好"},
)

# Store module login candidates
store_token = ""
store_user = ""
for username, password in [
    ("manager_yushuai", "admin123"),
    ("manager_wujiabin", "admin123"),
    ("finance_huangyanting", "admin123"),
]:
    _, payload = req(
        f"store.login[{username}]",
        "POST",
        f"{API}/store/login",
        expected_status=200,
        json_body={"username": username, "password": password},
    )
    if isinstance(payload, dict) and payload.get("code") == 0 and payload.get("token"):
        store_token = payload["token"]
        store_user = username
        break

if store_token:
    store_headers = {"Authorization": f"Bearer {store_token}"}
    req("store.me", "GET", f"{API}/store/me", expected_status=200, headers=store_headers)

    _, payload = req("store.orders", "GET", f"{API}/store/orders", expected_status=200, headers=store_headers)
    order_id = ""
    if isinstance(payload, dict):
        items = payload.get("items") or []
        if items:
            order_id = items[0].get("id") or ""

    req(
        "store.patch-order-negative",
        "PATCH",
        f"{API}/store/orders/{order_id or 'SMOKE-NOT-EXIST'}",
        expected_status=[404, 409],
        headers=store_headers,
        json_body={"version": 999999, "status": "未完工"},
    )
    req("store.leads", "GET", f"{API}/store/leads", expected_status=200, headers=store_headers)
    req(
        "store.leads.followup-due",
        "GET",
        f"{API}/store/leads/followup-due",
        expected_status=200,
        headers=store_headers,
    )
    req(
        "store.leads.update-status-negative",
        "POST",
        f"{API}/store/leads/update-status",
        expected_status=404,
        headers=store_headers,
        json_body={"id": "SMOKE-NO-ID", "leadStatus": "已联系"},
    )
    req("store.dispatch", "GET", f"{API}/store/dispatch", expected_status=200, headers=store_headers)
    req("store.followups", "GET", f"{API}/store/followups", expected_status=200, headers=store_headers)
    req(
        "store.followups.mark-done-negative",
        "POST",
        f"{API}/store/followups/mark-done",
        expected_status=404,
        headers=store_headers,
        json_body={"orderId": "SMOKE-NO-ID", "type": "D7", "remark": "smoke"},
    )
    req(
        "store.finance.sync-logs",
        "GET",
        f"{API}/store/finance/sync-logs?limit=10",
        expected_status=200,
        headers=store_headers,
    )
    req(
        "store.password.change-negative",
        "POST",
        f"{API}/store/password/change",
        expected_status=400,
        headers=store_headers,
        json_body={"currentPassword": "wrong", "newPassword": "123456"},
    )
    req(
        "store.users.reset-password-negative",
        "POST",
        f"{API}/store/users/reset-password",
        expected_status=404,
        headers=store_headers,
        json_body={"username": "no_such_user", "newPassword": "123456"},
    )
    req("store.users", "GET", f"{API}/store/users", expected_status=200, headers=store_headers)
    req(
        "store.orders.import-empty",
        "POST",
        f"{API}/store/orders/import",
        expected_status=200,
        headers=store_headers,
        json_body={"orders": []},
    )
    req("store.internal.orders", "GET", f"{API}/store/internal/orders", expected_status=200, headers=store_headers)
    req(
        "store.internal.orders.sync-empty",
        "POST",
        f"{API}/store/internal/orders/sync",
        expected_status=200,
        headers=store_headers,
        json_body={"orders": []},
    )
    req(
        "store.internal.work-orders.sync",
        "POST",
        f"{API}/store/internal/work-orders/sync",
        expected_status=200,
        headers=store_headers,
        json_body={
            "eventType": "SMOKE",
            "source": "SMOKE",
            "order": {
                "id": "SMOKE-" + uuid.uuid4().hex[:8],
                "serviceType": "FILM",
                "status": "未完工",
                "priceSummary": {"totalPrice": 0},
            },
        },
    )
    req(
        "store.internal.leads.push",
        "POST",
        f"{API}/store/internal/leads/push",
        expected_status=400,
        headers=store_headers,
        json_body={
            "lead": {
                "lead_id": "lead_smoke_" + uuid.uuid4().hex[:6],
                "platform": "douyin",
                "account_code": "DY-BOP-001",
                "customer_nickname": "smoke",
                "car_model": "smoke",
                "service_type": "贴膜",
                "store_code": "BOP",
            }
        },
    )
    req("store.health.db", "GET", f"{API}/store/health/db", expected_status=200)
    req("store.logout", "POST", f"{API}/store/logout", expected_status=200, headers=store_headers)
else:
    for name in [
        "store.me",
        "store.orders",
        "store.patch-order-negative",
        "store.leads",
        "store.leads.followup-due",
        "store.leads.update-status-negative",
        "store.dispatch",
        "store.followups",
        "store.followups.mark-done-negative",
        "store.finance.sync-logs",
        "store.password.change-negative",
        "store.users.reset-password-negative",
        "store.users",
        "store.orders.import-empty",
        "store.internal.orders",
        "store.internal.orders.sync-empty",
        "store.internal.work-orders.sync",
        "store.internal.leads.push",
        "store.health.db",
        "store.logout",
    ]:
        rec(name, False, detail="skip: store login failed", status="SKIP")

passed = sum(1 for item in results if item["ok"])
failed = len(results) - passed
summary = {
    "total": len(results),
    "passed": passed,
    "failed": failed,
    "store_login_user": store_user,
    "sales_login_user": ctx.get("sales_id", ""),
}

print("SMOKE_SUMMARY=" + json.dumps(summary, ensure_ascii=False))
for item in results:
    tag = "PASS" if item["ok"] else "FAIL"
    detail = str(item["detail"]).replace("\n", " ")[:180]
    print(f"{tag}\t{item['name']}\tstatus={item['status']}\tdetail={detail}")
