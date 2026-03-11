"""
数据迁移脚本：将 car-film admin-console 的 slim 数据库数据迁入 lx_center 数据库。

使用前请设置环境变量：
  SOURCE_DB_DSN=postgresql://user:pass@host:5432/slim
  TARGET_DB_DSN=postgresql://user:pass@host:5432/lx_center

或直接修改下面的 SOURCE_DSN / TARGET_DSN 常量。

用法：
  python3 scripts/migrate_slim_to_lx_center.py [--dry-run]
"""

import argparse
import json
import sys
import os
import uuid
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("需要安装 psycopg2: pip install psycopg2-binary")
    sys.exit(1)


SOURCE_DSN = os.getenv("SOURCE_DB_DSN", "postgresql://postgres:password@localhost:5432/slim")
TARGET_DSN = os.getenv("TARGET_DB_DSN", "postgresql://postgres:password@localhost:5432/lx_center")


def connect(dsn: str):
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    return conn


def migrate_users(source_conn, target_conn, dry_run: bool) -> int:
    """users → store_user"""
    with source_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT username, name, role, password_hash, status, payload FROM users ORDER BY username")
        rows = cur.fetchall()

    count = 0
    with target_conn.cursor() as cur:
        for row in rows:
            username = (row["username"] or "").strip()
            if not username:
                continue
            name = (row["name"] or "").strip()
            role = (row["role"] or "sales").strip().lower()
            password_hash = (row["password_hash"] or "").strip()
            is_active = (row.get("status") or "active").strip().lower() == "active"
            store_code = ""
            payload = row.get("payload")
            if isinstance(payload, dict):
                store_code = (payload.get("store") or "").strip()

            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO store_user (username, name, role, password_hash, store_code, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET
                        name = EXCLUDED.name,
                        role = EXCLUDED.role,
                        password_hash = EXCLUDED.password_hash,
                        store_code = EXCLUDED.store_code,
                        is_active = EXCLUDED.is_active,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (username, name, role, password_hash, store_code, is_active, datetime.utcnow(), datetime.utcnow()),
                )
            count += 1
            print(f"  用户: {username} ({name}, {role})")

    return count


def migrate_orders(source_conn, target_conn, dry_run: bool) -> int:
    """orders → store_order"""
    with source_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT order_id, status, version, payload, created_at, updated_at FROM orders ORDER BY created_at")
        rows = cur.fetchall()

    count = 0
    with target_conn.cursor() as cur:
        for row in rows:
            order_id = (row["order_id"] or "").strip()
            if not order_id:
                continue
            payload = row["payload"] if isinstance(row["payload"], dict) else {}
            status = (row["status"] or payload.get("status") or "未完工").strip()
            version = int(row.get("version") or payload.get("version") or 0)

            store_name = (payload.get("store") or "").strip()
            sales_brand_text = (payload.get("salesBrandText") or "").strip()
            customer_name = (payload.get("customerName") or "").strip()
            phone = (payload.get("phone") or "").strip()
            car_model = (payload.get("carModel") or "").strip()
            lead_source = (payload.get("leadSource") or "").strip()
            lead_grade = (payload.get("leadGrade") or "").strip().upper()
            lead_status = (payload.get("leadStatus") or "").strip()
            created_at_text = (payload.get("createdAt") or "").strip()
            updated_at_text = (payload.get("updatedAt") or "").strip()

            created_at_dt = row.get("created_at") or datetime.utcnow()
            updated_at_dt = row.get("updated_at") or datetime.utcnow()

            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO store_order (
                        order_id, status, version, store_name, sales_brand_text,
                        customer_name, phone, car_model, lead_source, lead_grade, lead_status,
                        created_at_text, updated_at_text, created_at_dt, updated_at_dt, payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (order_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        version = EXCLUDED.version,
                        store_name = EXCLUDED.store_name,
                        payload = EXCLUDED.payload,
                        updated_at_dt = EXCLUDED.updated_at_dt
                    """,
                    (
                        order_id, status, version, store_name, sales_brand_text,
                        customer_name, phone, car_model, lead_source, lead_grade, lead_status,
                        created_at_text, updated_at_text, created_at_dt, updated_at_dt,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )
            count += 1
            label = customer_name or order_id
            print(f"  订单: {order_id} ({label}, {status})")

    return count


def migrate_finance_logs(source_conn, target_conn, dry_run: bool) -> int:
    """finance_sync_logs → finance_sync_log"""
    with source_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT payload, created_at FROM finance_sync_logs ORDER BY created_at DESC LIMIT 1000")
        rows = cur.fetchall()

    count = 0
    with target_conn.cursor() as cur:
        for row in rows:
            payload = row["payload"] if isinstance(row["payload"], dict) else {}
            log_id = (payload.get("id") or uuid.uuid4().hex).strip()
            order_id = (payload.get("orderId") or "").strip()
            event_type = (payload.get("eventType") or "").strip()
            service_type = (payload.get("serviceType") or "").strip()
            result = (payload.get("result") or "SUCCESS").strip().upper()
            external_id = (payload.get("externalId") or "").strip()
            try:
                total_price = float(payload.get("totalPrice") or 0)
            except (TypeError, ValueError):
                total_price = 0.0
            created_at = row.get("created_at") or datetime.utcnow()

            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO finance_sync_log (
                        log_id, order_id, event_type, service_type, result,
                        total_price, external_id, payload, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (log_id) DO NOTHING
                    """,
                    (
                        log_id, order_id, event_type, service_type, result,
                        total_price, external_id, json.dumps(payload, ensure_ascii=False),
                        created_at, datetime.utcnow(),
                    ),
                )
            count += 1
            print(f"  日志: {log_id[:12]}... ({event_type}, {order_id})")

    return count


def main():
    parser = argparse.ArgumentParser(description="迁移 slim → lx_center 数据")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写入目标数据库")
    args = parser.parse_args()

    print(f"源数据库: {SOURCE_DSN.split('@')[-1] if '@' in SOURCE_DSN else SOURCE_DSN}")
    print(f"目标数据库: {TARGET_DSN.split('@')[-1] if '@' in TARGET_DSN else TARGET_DSN}")
    if args.dry_run:
        print("⚠️  DRY RUN 模式，不会写入数据\n")
    else:
        print()

    source_conn = connect(SOURCE_DSN)
    target_conn = connect(TARGET_DSN)

    try:
        print("═══ 迁移用户 ═══")
        user_count = migrate_users(source_conn, target_conn, args.dry_run)
        print(f"  → {user_count} 条用户\n")

        print("═══ 迁移订单 ═══")
        order_count = migrate_orders(source_conn, target_conn, args.dry_run)
        print(f"  → {order_count} 条订单\n")

        print("═══ 迁移财务日志 ═══")
        log_count = migrate_finance_logs(source_conn, target_conn, args.dry_run)
        print(f"  → {log_count} 条日志\n")

        if not args.dry_run:
            target_conn.commit()
            print("✅ 所有数据已提交")
        else:
            print("✅ Dry run 完成，未写入数据")

        print(f"\n汇总: {user_count} 用户 + {order_count} 订单 + {log_count} 财务日志")

    except Exception as e:
        target_conn.rollback()
        print(f"\n❌ 迁移失败，已回滚: {e}")
        raise
    finally:
        source_conn.close()
        target_conn.close()


if __name__ == "__main__":
    main()
