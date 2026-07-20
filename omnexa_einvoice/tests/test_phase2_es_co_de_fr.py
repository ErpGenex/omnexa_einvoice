# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.country_catalog import get_catalog_entry
from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1, run_country_phase2


class TestPhase2EsCoDeFr(FrappeTestCase):
	def test_catalog_engines(self):
		self.assertEqual(get_catalog_entry("ES").engine, "facturae")
		self.assertEqual(get_catalog_entry("CO").engine, "dian_ubl")
		self.assertEqual(get_catalog_entry("DE").engine, "xrechnung")
		self.assertEqual(get_catalog_entry("FR").engine, "facturx")

	def test_integration_tiers_sandbox(self):
		for code in ("ES", "CO", "DE", "FR"):
			self.assertEqual(COUNTRY_REGISTRY[code].integration_tier, "sandbox")
			self.assertFalse(COUNTRY_REGISTRY[code].production_ready)

	def _payload(self, ref: str) -> dict:
		return {
			"company": "Test",
			"reference_name": ref,
			"seller_name": "Seller",
			"tax_registration_number": "B12345678",
			"buyer": {"name": "Buyer", "tax_registration": "A87654321"},
			"lines": [{"description": "Item", "qty": 1, "rate": 100, "amount": 100, "tax_amount": 21}],
			"totals": {"net_total": 100, "tax_total": 21, "grand_total": 121},
		}

	def test_spain_phase1_phase2(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(self._payload("SI-ES-PH1"), country_code="ES")
		self.assertIn("fe:Facturae", p1.get("signed_xml") or "")
		p2 = run_country_phase2(
			{"company": "Test", "reference_name": "SI-ES-PH1", "phase1": p1},
			country_code="ES",
			sync=True,
		)
		self.assertTrue((p2.get("api") or {}).get("registro_id"))

	def test_colombia_phase1_phase2(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(self._payload("SI-CO-PH1"), country_code="CO")
		xml = p1.get("signed_xml") or ""
		self.assertIn("DIAN 2.1", xml)
		self.assertIn("CUFE-SHA384", xml)
		p2 = run_country_phase2(
			{"company": "Test", "reference_name": "SI-CO-PH1", "phase1": p1},
			country_code="CO",
			sync=True,
		)
		self.assertTrue((p2.get("api") or {}).get("cufe"))

	def test_germany_phase1_phase2(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(self._payload("SI-DE-PH1"), country_code="DE")
		self.assertIn("BuyerReference", p1.get("signed_xml") or "")
		p2 = run_country_phase2(
			{"company": "Test", "reference_name": "SI-DE-PH1", "phase1": p1},
			country_code="DE",
			sync=True,
		)
		self.assertTrue((p2.get("api") or {}).get("tracking_id"))

	def test_france_phase1_phase2(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(self._payload("SI-FR-PH1"), country_code="FR")
		self.assertIn("CrossIndustryInvoice", p1.get("signed_xml") or "")
		p2 = run_country_phase2(
			{"company": "Test", "reference_name": "SI-FR-PH1", "phase1": p1},
			country_code="FR",
			sync=True,
		)
		self.assertTrue((p2.get("api") or {}).get("flow_id"))
