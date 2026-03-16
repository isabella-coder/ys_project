#!/usr/bin/env python3
import json
import re
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api/v1/store"
ROOT = Path(__file__).resolve().parents[1]
OPS_HOME_JS = ROOT / "miniprogram/subpackages/store/pages/ops-home/index.js"

ROLE_CASES = [
    {
        "role": "manager",
        "username": "manager_yushuai",
        "password": "admin123",
        "expect": {
            "orders_all": 200,
            "orders_mine": 200,
            "leads_all": 200,
            "leads_mine": 200,
            "dispatch_all": 200,
            "dispatch_mine": 200,
            "followups_all": 200,
            "followups_mine": 200,
            "followup_due": 200,
            "finance_logs": 200,
            "users_list": 200,
            "orders_import": 200,
        },
    },
    {
        "role": "sales",
        "username": "sales_mengao",
        "password": "sale123",
        "expect": {
            "orders_all": 200,
            "orders_mine": 200,
            "leads_all": 200,
            "leads_mine": 200,
            "dispatch_all": 200,
            "dispatch_mine": 200,
            "followups_all": 200,
            "followups_mine": 200,
            "followup_due": 200,
            "finance_logs": 403,
            "users_list": 403,
            "orders_import": 403,
        },
    },
    {
        "role": "finance",
        "username": "finance_huangyanting",
        "password": "123456",
        "expect": {
            "orders_all": 200,
            "orders_mine": 200,
            "leads_all": 200,
            "leads_mine": 200,
            "dispatch_all": 200,
            "dispatch_mine": 200,
            "followups_all": 200,
            "followups_mine": 200,
            "followup_due": 200,
            "finance_logs": 200,
            "users_list": 403,
            "orders_import": 403,
        },
    },
    {
        "role": "technician",
        "username": "tech_fangyuan",
        "password": "123456",
        "expect": {
            "orders_all": 403,
            "orders_mine": 200,
            "leads_all": 403,
            "leads_mine": 200,
            "dispatch_all": 403,
            "dispatch_mine": 200,
            "followups_all": 403,
            "followups_mine": 200,
            "followup_due": 403,
            "finance_logs": 403,
            "users_list": 403,
            "orders_import": 403,
        },
    },
]


def check_ops_home_routes():
    text = OPS_HOME_JS.read_text(encoding="utf-8")
    routes = sorted(set(re.findall(r"route:\s*'([^']+)'", text)))
    checks = []
    for route in routes:
        rel = route.lstrip("/")
        # route points to page path under miniprogram, and we check index.js exists.
        page_js = ROOT / "miniprogram" / (rel + ".js")
        checks.append({
            "route": route,
            "page_js_exists": page_js.exists(),
            "page_js": str(page_js.relative_to(ROOT)),
        })
    ok = all(item["page_js_exists"] for item in checks)
    return {"ok": ok, "items": checks}


def role_request_matrix(client: httpx.Client, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "orders_all": client.get(f"{API}/orders?view=ALL", headers=headers).status_code,
        "orders_mine": client.get(f"{API}/orders?view=MINE", headers=headers).status_code,
        "leads_all": client.get(f"{API}/leads?view=ALL", headers=headers).status_code,
        "leads_mine": client.get(f"{API}/leads?view=MINE", headers=headers).status_code,
        "dispatch_all": client.get(f"{API}/dispatch?view=ALL", headers=headers).status_code,
        "dispatch_mine": client.get(f"{API}/dispatch?view=MINE", headers=headers).status_code,
        "followups_all": client.get(f"{API}/followups?view=ALL", headers=headers).status_code,
        "followups_mine": client.get(f"{API}/followups?view=MINE", headers=headers).status_code,
        "followup_due": client.get(f"{API}/leads/followup-due", headers=headers).status_code,
        "finance_logs": client.get(f"{API}/finance/sync-logs", headers=headers).status_code,
        "users_list": client.get(f"{API}/users", headers=headers).status_code,
        "orders_import": client.post(f"{API}/orders/import", headers=headers, json={"orders": []}).status_code,
    }


def main():
    route_check = check_ops_home_routes()
    role_results = []
    anomalies = []

    with httpx.Client(timeout=20.0) as client:
        for case in ROLE_CASES:
            login = client.post(f"{API}/login", json={"username": case["username"], "password": case["password"]})
            body = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
            token = body.get("token", "")
            role_item = {
                "role": case["role"],
                "username": case["username"],
                "login_status": login.status_code,
                "login_code": body.get("code"),
                "login_ok": bool(login.status_code == 200 and body.get("code") == 0 and token),
                "checks": {},
            }

            if not role_item["login_ok"]:
                anomalies.append({
                    "role": case["role"],
                    "type": "login",
                    "expected": "200/code=0",
                    "actual": {"status": login.status_code, "code": body.get("code"), "message": body.get("message")},
                })
                role_results.append(role_item)
                continue

            checks = role_request_matrix(client, token)
            role_item["checks"] = checks
            for key, expected in case["expect"].items():
                actual = checks.get(key)
                if actual != expected:
                    anomalies.append({
                        "role": case["role"],
                        "type": key,
                        "expected": expected,
                        "actual": actual,
                    })

            role_results.append(role_item)
            client.post(f"{API}/logout", headers={"Authorization": f"Bearer {token}"})

    out = {
        "summary": {
            "route_check_ok": route_check["ok"],
            "role_case_count": len(ROLE_CASES),
            "role_login_success": sum(1 for item in role_results if item.get("login_ok")),
            "anomaly_count": len(anomalies),
        },
        "route_check": route_check,
        "roles": role_results,
        "anomalies": anomalies,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
