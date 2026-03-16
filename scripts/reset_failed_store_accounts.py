#!/usr/bin/env python3
import json
import sys

import httpx


REPORT_PATH = "/tmp/store_account_weight_report_before_reset.json"
NEW_PASSWORD = "123456"
API = "http://127.0.0.1:8000/api/v1/store"


def main() -> int:
    try:
        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            report = json.load(f)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"read report failed: {exc}"}, ensure_ascii=False))
        return 1

    failed = list(report.get("summary", {}).get("failed_accounts", []))
    client = httpx.Client(timeout=20.0)

    login = client.post(f"{API}/login", json={"username": "manager_yushuai", "password": "admin123"})
    if login.status_code != 200:
        print(json.dumps({"ok": False, "error": "manager login http failed", "status": login.status_code}, ensure_ascii=False))
        return 2

    data = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = data.get("token", "")
    if not token:
        print(json.dumps({"ok": False, "error": "manager login has no token", "body": data}, ensure_ascii=False))
        return 3

    headers = {"Authorization": f"Bearer {token}"}
    ok_accounts = []
    failures = []

    for username in failed:
        resp = client.post(
            f"{API}/users/reset-password",
            headers=headers,
            json={"username": username, "newPassword": NEW_PASSWORD},
        )
        body = {}
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:200]}

        if resp.status_code == 200 and body.get("code") == 0:
            ok_accounts.append(username)
        else:
            failures.append({"username": username, "status": resp.status_code, "body": body})

    print(
        json.dumps(
            {
                "ok": len(failures) == 0,
                "target_count": len(failed),
                "reset_ok": len(ok_accounts),
                "reset_fail": len(failures),
                "ok_accounts": ok_accounts,
                "failures": failures,
                "new_password": NEW_PASSWORD,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not failures else 4


if __name__ == "__main__":
    sys.exit(main())
