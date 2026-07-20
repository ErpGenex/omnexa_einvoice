# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.country_catalog import get_catalog_entry
from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1, run_country_phase2


class TestPhase1ItBrPl(FrappeTestCase):
	def test_catalog_engines(self):
		self.assertEqual(get_catalog_entry("IT").engine, "fatturapa")
		self.assertEqual(get_catalog_entry("PL").engine, "ksef_fa2")
		self.assertEqual(get_catalog_entry("BR").engine, "nfe")

	def test_integration_tiers_sandbox(self):
		for code in ("IT", "BR", "PL"):
			self.assertEqual(COUNTRY_REGISTRY[code].integration_tier, "sandbox")
			self.assertFalse(COUNTRY_REGISTRY[code].production_ready)

	def _payload(self, ref: str) -> dict:
		return {
			"company": "Test",
			"reference_name": ref,
			"seller_name": "Seller",
			"tax_registration_number": "12345678901",
			"buyer": {"name": "Buyer", "tax_registration": "98765432109"},
			"lines": [{"description": "Item", "qty": 1, "rate": 100, "amount": 100, "tax_amount": 22}],
			"totals": {"net_total": 100, "tax_total": 22, "grand_total": 122},
		}

	def test_italy_phase1_phase2(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(self._payload("SI-IT-PH1"), country_code="IT")
		xml = p1.get("signed_xml") or ""
		self.assertIn("FatturaElettronica", xml)
		self.assertIn("CodiceDestinatario", xml)
		p2 = run_country_phase2(
			{"company": "Test", "reference_name": "SI-IT-PH1", "phase1": p1},
			country_code="IT",
			sync=True,
		)
		self.assertTrue((p2.get("api") or {}).get("sdi_id"))

	def test_brazil_phase1_phase2(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(self._payload("SI-BR-PH1"), country_code="BR")
		self.assertIn("nfeProc", p1.get("signed_xml") or "")
		p2 = run_country_phase2(
			{"company": "Test", "reference_name": "SI-BR-PH1", "phase1": p1},
			country_code="BR",
			sync=True,
		)
		self.assertTrue((p2.get("api") or {}).get("chave_acesso"))

	def test_poland_phase1_phase2(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(self._payload("SI-PL-PH1"), country_code="PL")
		xml = p1.get("signed_xml") or ""
		self.assertIn("Podmiot1", xml)
		self.assertIn("<FA", xml)
		p2 = run_country_phase2(
			{"company": "Test", "reference_name": "SI-PL-PH1", "phase1": p1},
			country_code="PL",
			sync=True,
		)
		self.assertTrue((p2.get("api") or {}).get("ksef_number"))
