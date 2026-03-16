#!/usr/bin/env python3
import json
from typing import Dict, List, Tuple

import httpx
import psycopg2

API = "http://127.0.0.1:8000/api/v1/store"
DB = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "xls_db",
    "user": "xls_admin",
    "password": "xls_admin_2024",
}

# reset 后技术账号临时密码
TECH_PASSWORD = "123456"


def load_technicians() -> List[str]:
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "select username from store_user where is_active=true and role='technician' order by username"
    )
    usernames = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return usernames


def expected_matrix() -> Dict[str, int]:
    return {
        "me": 200,
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
        "logout": 200,
    }


def check_user(client: httpx.Client, username: str) -> Tuple[dict, List[dict]]:
    login = client.post(f"{API}/login", json={"username": username, "password": TECH_PASSWORD})
    login_body = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = login_body.get("token", "")

    result = {
        "username": username,
        "login_status": login.status_code,
        "login_code": login_body.get("code"),
        "login_ok": bool(login.status_code == 200 and login_body.get("code") == 0 and token),
        "checks": {},
    }
    anomalies: List[dict] = []

    if not result["login_ok"]:
        anomalies.append({
            "username": username,
            "key": "login",
            "expected": "200/code=0",
            "actual": {
                "status": login.status_code,
                "code": login_body.get("code"),
                "message": login_body.get("message", ""),
            },
        })
        return result, anomalies

    headers = {"Authorization": f"Bearer {token}"}
    checks = {
        "me": client.get(f"{API}/me", headers=headers),
        "orders_all": client.get(f"{API}/orders?view=ALL", headers=headers),
        "orders_mine": client.get(f"{API}/orders?view=MINE", headers=headers),
        "leads_all": client.get(f"{API}/leads?view=ALL", headers=headers),
        "leads_mine": client.get(f"{API}/leads?view=MINE", headers=headers),
        "dispatch_all": client.get(f"{API}/dispatch?view=ALL", headers=headers),
        "dispatch_mine": client.get(f"{API}/dispatch?view=MINE", headers=headers),
        "followups_all": client.get(f"{API}/followups?view=ALL", headers=headers),
        "followups_mine": client.get(f"{API}/followups?view=MINE", headers=headers),
        "followup_due": client.get(f"{API}/leads/followup-due", headers=headers),
        "finance_logs": client.get(f"{API}/finance/sync-logs", headers=headers),
        "users_list": client.get(f"{API}/users", headers=headers),
        "orders_import": client.post(f"{API}/orders/import", headers=headers, json={"orders": []}),
        "logout": client.post(f"{API}/logout", headers=headers),
    }

    expect = expected_matrix()
    for key, resp in checks.items():
        result["checks"][key] = resp.status_code
        if resp.status_code != expect[key]:
            body = {}
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text[:200]}
            anomalies.append({
                "username": username,
                "key": key,
                "expected": expect[key],
                "actual": resp.status_code,
                "body": body,
            })

    return result, anomalies


def main() -> None:
    users = load_technicians()
    report = []
    anomalies: List[dict] = []

    with httpx.Client(timeout=20.0) as client:
        for username in users:
            item, issues = check_user(client, username)
            report.append(item)
            anomalies.extend(issues)

    summary = {
        "technician_count": len(users),
        "login_success": sum(1 for r in report if r.get("login_ok")),
        "login_failed": sum(1 for r in report if not r.get("login_ok")),
        "anomaly_count": len(anomalies),
    }

    print(json.dumps({"summary": summary, "report": report, "anomalies": anomalies}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
