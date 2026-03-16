#!/usr/bin/env python3
import json
from typing import Dict, List

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
CANDIDATES = ["admin123", "sale123", "123456", "password", "123123"]


def grade_rank(grade: str) -> int:
    return {"S": 0, "A": 1, "B": 2, "C": 3}.get((grade or "").upper(), 9)


def load_accounts() -> List[Dict[str, str]]:
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("select username, role from store_user where is_active=true order by username")
    items = [{"username": u, "role": r} for u, r in cur.fetchall()]
    cur.close()
    conn.close()
    return items


def main() -> None:
    accounts = load_accounts()
    report = []
    weight_issues = []
    role_issues = []
    login_fail = []

    with httpx.Client(timeout=20.0) as client:
        for acc in accounts:
            username = acc["username"]
            role = acc["role"]
            token = ""
            used_password = ""
            last_error = ""

            for pwd in CANDIDATES:
                resp = client.post(f"{API}/login", json={"username": username, "password": pwd})
                try:
                    payload = resp.json()
                except Exception:
                    payload = {}
                if resp.status_code == 200 and payload.get("code") == 0 and payload.get("token"):
                    token = payload["token"]
                    used_password = pwd
                    break
                last_error = payload.get("message") or payload.get("detail") or str(resp.status_code)

            entry = {
                "username": username,
                "role": role,
                "login_ok": bool(token),
                "password_used": used_password,
                "error": "" if token else last_error,
            }

            if not token:
                login_fail.append(username)
                report.append(entry)
                continue

            headers = {"Authorization": f"Bearer {token}"}
            me = client.get(f"{API}/me", headers=headers)
            leads_all = client.get(f"{API}/leads?view=ALL", headers=headers)
            leads_mine = client.get(f"{API}/leads?view=MINE", headers=headers)
            orders_all = client.get(f"{API}/orders?view=ALL", headers=headers)

            la = leads_all.json() if leads_all.headers.get("content-type", "").startswith("application/json") else {}
            lm = leads_mine.json() if leads_mine.headers.get("content-type", "").startswith("application/json") else {}
            oa = orders_all.json() if orders_all.headers.get("content-type", "").startswith("application/json") else {}

            la_items = la.get("items") if isinstance(la, dict) else None
            lm_items = lm.get("items") if isinstance(lm, dict) else None
            oa_items = oa.get("items") if isinstance(oa, dict) else None

            entry.update(
                {
                    "me_code": me.status_code,
                    "leads_all_code": leads_all.status_code,
                    "leads_mine_code": leads_mine.status_code,
                    "orders_all_code": orders_all.status_code,
                    "leads_all_count": len(la_items) if isinstance(la_items, list) else None,
                    "leads_mine_count": len(lm_items) if isinstance(lm_items, list) else None,
                    "orders_all_count": len(oa_items) if isinstance(oa_items, list) else None,
                }
            )

            if role == "technician" and orders_all.status_code != 403:
                role_issues.append(
                    {
                        "username": username,
                        "issue": "technician should be forbidden on orders view=ALL",
                        "actual": orders_all.status_code,
                    }
                )
            if role in ("manager", "sales", "finance") and orders_all.status_code != 200:
                role_issues.append(
                    {
                        "username": username,
                        "issue": f"{role} expected 200 on orders view=ALL",
                        "actual": orders_all.status_code,
                    }
                )

            if leads_all.status_code == 200 and isinstance(la_items, list) and len(la_items) > 1:
                sorted_ok = True
                for i in range(len(la_items) - 1):
                    left = la_items[i]
                    right = la_items[i + 1]
                    k_left = (grade_rank(left.get("leadGrade")), -int(left.get("leadGradeScore") or 0))
                    k_right = (grade_rank(right.get("leadGrade")), -int(right.get("leadGradeScore") or 0))
                    if k_left > k_right:
                        sorted_ok = False
                        weight_issues.append(
                            {
                                "username": username,
                                "at_index": i,
                                "left": {
                                    "id": left.get("id"),
                                    "grade": left.get("leadGrade"),
                                    "score": left.get("leadGradeScore"),
                                },
                                "right": {
                                    "id": right.get("id"),
                                    "grade": right.get("leadGrade"),
                                    "score": right.get("leadGradeScore"),
                                },
                            }
                        )
                        break
                entry["weight_sorted"] = sorted_ok
            elif leads_all.status_code == 200:
                entry["weight_sorted"] = True
            else:
                entry["weight_sorted"] = None

            report.append(entry)

    output = {
        "summary": {
            "total_accounts": len(accounts),
            "login_success": sum(1 for r in report if r.get("login_ok")),
            "login_failed": len(login_fail),
            "failed_accounts": login_fail,
            "weight_issue_count": len(weight_issues),
            "role_issue_count": len(role_issues),
        },
        "report": report,
        "weight_issues": weight_issues,
        "role_issues": role_issues,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
