#!/usr/bin/env python3
"""25 contract tests for mini program ops flow and lead allocation."""

import re
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent


def read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


class TestMiniProgramOpsContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ops_js = read_text("miniprogram/subpackages/store/pages/ops-home/index.js")
        cls.ops_wxml = read_text("miniprogram/subpackages/store/pages/ops-home/index.wxml")

    def test_ops_home_film_chain_route(self):
        self.assertIn("/subpackages/store/pages/film-order/index", self.ops_js)

    def test_ops_home_wash_chain_route(self):
        self.assertIn("/subpackages/store/pages/wash-order/index", self.ops_js)

    def test_ops_home_quick_entries_count_contract(self):
        entries = re.findall(r"\{ key: '([^']+)', name: '([^']+)', route: '([^']+)' \}", self.ops_js)
        self.assertEqual(len(entries), 4)

    def test_ops_home_has_all_orders_entry(self):
        self.assertIn("{ key: 'all-orders', name: '全部订单'", self.ops_js)
        self.assertIn("/subpackages/store/pages/order-list/index", self.ops_js)

    def test_ops_home_has_film_dispatch_entry(self):
        self.assertIn("{ key: 'dispatch-film', name: '贴膜派工看板'", self.ops_js)
        self.assertIn("/subpackages/store/pages/dispatch-board/index", self.ops_js)

    def test_ops_home_has_wash_dispatch_entry(self):
        self.assertIn("{ key: 'dispatch-wash', name: '洗车派工看板'", self.ops_js)
        self.assertIn("/subpackages/store/pages/wash-dispatch-board/index", self.ops_js)

    def test_ops_home_has_sales_board_entry(self):
        self.assertIn("{ key: 'sales-board', name: '销售业绩看板'", self.ops_js)
        self.assertIn("/subpackages/store/pages/sales-performance/index", self.ops_js)

    def test_ops_home_role_manager_label(self):
        self.assertIn("manager: '店长'", self.ops_js)

    def test_ops_home_role_sales_label(self):
        self.assertIn("sales: '销售'", self.ops_js)

    def test_ops_home_role_finance_label(self):
        self.assertIn("finance: '财务'", self.ops_js)

    def test_ops_home_role_technician_label(self):
        self.assertIn("technician: '施工'", self.ops_js)

    def test_ops_home_fallback_sales_label(self):
        self.assertIn("roleLabelMap[role] || '销售'", self.ops_js)

    def test_ops_home_toast_for_closed_entry(self):
        self.assertIn("title: '该入口暂未开放'", self.ops_js)

    def test_ops_home_wxml_contains_film_wash_cards(self):
        self.assertIn("贴膜链路", self.ops_wxml)
        self.assertIn("洗车链路", self.ops_wxml)

    def test_ops_home_wxml_binds_on_open_route(self):
        self.assertIn('bindtap="onOpenRoute"', self.ops_wxml)
        self.assertIn('data-route="{{item.route}}"', self.ops_wxml)


class TestMiniProgramPermissionContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.permission_js = read_text("miniprogram/utils/adapters/store-permission.js")

    def test_permission_role_whitelist(self):
        for role in ["manager", "sales", "finance", "technician"]:
            self.assertIn(f"'{role}'", self.permission_js)

    def test_permission_batch_edit_roles(self):
        self.assertIn("target === 'manager' || target === 'sales'", self.permission_js)

    def test_permission_mine_order_roles(self):
        self.assertIn("target === 'sales' || target === 'technician'", self.permission_js)

    def test_permission_default_sales_fallback(self):
        self.assertIn("return 'sales'", self.permission_js)
        self.assertIn("|| 'sales'", self.permission_js)

    def test_permission_manager_can_edit_shortcut(self):
        self.assertIn("if (target === 'manager')", self.permission_js)
        self.assertIn("return true", self.permission_js)


class TestLeadAllocationService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        backend_dir = ROOT / "backend"
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from app.services import allocation_service  # pylint: disable=import-outside-toplevel

        cls.alloc_mod = allocation_service

    def test_get_next_sales_rotates_pointer_and_commits(self):
        allocation = SimpleNamespace(
            current_sales_index=1,
            last_assigned_sales_id=None,
            last_assigned_at=None,
            rotation_count=4,
        )
        sales_list = [SimpleNamespace(sales_id="S1"), SimpleNamespace(sales_id="S2")]

        alloc_query = MagicMock()
        alloc_query.filter.return_value.first.return_value = allocation

        sales_query = MagicMock()
        sales_query.filter.return_value.order_by.return_value.all.return_value = sales_list

        db = MagicMock()
        db.query.side_effect = [alloc_query, sales_query]

        picked = self.alloc_mod.get_next_sales(db, "BOP")

        self.assertEqual(picked.sales_id, "S2")
        self.assertEqual(allocation.current_sales_index, 0)
        self.assertEqual(allocation.last_assigned_sales_id, "S2")
        self.assertEqual(allocation.rotation_count, 5)
        self.assertIsInstance(allocation.last_assigned_at, datetime)
        db.commit.assert_called_once()

    def test_get_next_sales_raises_without_config(self):
        alloc_query = MagicMock()
        alloc_query.filter.return_value.first.return_value = None

        db = MagicMock()
        db.query.side_effect = [alloc_query]

        with self.assertRaisesRegex(ValueError, "has no allocation config"):
            self.alloc_mod.get_next_sales(db, "BOP")

    def test_get_next_sales_raises_without_active_sales(self):
        allocation = SimpleNamespace(
            current_sales_index=0,
            last_assigned_sales_id=None,
            last_assigned_at=None,
            rotation_count=0,
        )

        alloc_query = MagicMock()
        alloc_query.filter.return_value.first.return_value = allocation

        sales_query = MagicMock()
        sales_query.filter.return_value.order_by.return_value.all.return_value = []

        db = MagicMock()
        db.query.side_effect = [alloc_query, sales_query]

        with self.assertRaisesRegex(ValueError, "has no active sales"):
            self.alloc_mod.get_next_sales(db, "BOP")

        db.commit.assert_not_called()

    def test_assign_lead_to_sales_sets_assignee_and_status(self):
        lead = SimpleNamespace(store_code="BOP", assigned_sales_id=None, assigned_at=None, status="created")
        db = MagicMock()
        next_sales = SimpleNamespace(sales_id="S100")

        with patch.object(self.alloc_mod, "get_next_sales", return_value=next_sales):
            result = self.alloc_mod.assign_lead_to_sales(db, lead)

        self.assertIs(result, lead)
        self.assertEqual(lead.assigned_sales_id, "S100")
        self.assertEqual(lead.status, "assigned")
        self.assertIsInstance(lead.assigned_at, datetime)

    def test_assign_lead_to_sales_calls_commit(self):
        lead = SimpleNamespace(store_code="LM", assigned_sales_id=None, assigned_at=None, status="created")
        db = MagicMock()
        next_sales = SimpleNamespace(sales_id="S200")

        with patch.object(self.alloc_mod, "get_next_sales", return_value=next_sales) as mocked_next:
            self.alloc_mod.assign_lead_to_sales(db, lead)

        mocked_next.assert_called_once_with(db, "LM")
        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
