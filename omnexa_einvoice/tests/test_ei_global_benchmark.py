# Copyright (c) 2026, Omnexa
import json, frappe
from frappe.tests.utils import FrappeTestCase
from omnexa_einvoice.ei_gap_register import GLOBAL_LEADER_TARGET, get_gap_status
from omnexa_einvoice.ei_global_benchmark import get_global_ei_score
from omnexa_einvoice.workspace.ei_workspace import sync_ei_workspace_menu

class TestEiGlobalBenchmark(FrappeTestCase):
	def test_global_score(self):
		s = get_global_ei_score()
		self.assertGreaterEqual(s["weighted_score"], GLOBAL_LEADER_TARGET)
		self.assertTrue(s.get("global_leader_gate"))
	def test_gaps_closed(self):
		self.assertTrue(get_gap_status()["global_leader_gate"])
	def test_workspace_sync(self):
		stats = sync_ei_workspace_menu(save=True, rebuild=True)
		self.assertGreater(stats["total_links"], 10)
		ws = frappe.get_doc("Workspace", "E-Invoice")
		self.assertGreater(len(ws.shortcuts), 5)
