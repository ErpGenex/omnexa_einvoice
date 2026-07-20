# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Golden-style XML/JSON structure tests for sandbox-tier countries."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.country_catalog import xml_markers_for_country
from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1

SANDBOX_CODES = ("MX", "BR", "IN", "IT", "PL", "AE", "ES", "CO", "DE", "FR")


class TestGoldenXmlSandbox(FrappeTestCase):
	def _payload(self, ref: str, *, credit_note: bool = False) -> dict:
		p = {
			"company": "Test",
			"reference_name": ref,
			"seller_name": "Seller",
			"tax_registration_number": "123456789012345",
			"buyer": {"name": "Buyer", "tax_registration": "987654321098765"},
			"lines": [{"description": "Item", "qty": 1, "rate": 100, "amount": 100, "tax_amount": 5}],
			"totals": {"net_total": 100, "tax_total": 5, "grand_total": 105},
		}
		if credit_note:
			p["document_type"] = "credit_note"
			p["is_return"] = 1
		return p

	def test_all_sandbox_countries_phase1_markers(self):
		frappe.flags.in_test = True
		for code in SANDBOX_CODES:
			with self.subTest(country=code):
				p1 = run_country_phase1(self._payload(f"GOLD-{code}"), country_code=code)
				body = p1.get("signed_xml") or ""
				self.assertTrue(body, f"empty output for {code}")
				for marker in xml_markers_for_country(code):
					self.assertIn(marker, body, f"{code} missing {marker}")

	def test_credit_note_ubl_type_code(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(self._payload("GOLD-DE-CN", credit_note=True), country_code="DE")
		xml = p1.get("signed_xml") or ""
		self.assertIn("381", xml)

	def test_credit_note_latam_document_type(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(self._payload("GOLD-AR-CN", credit_note=True), country_code="AR")
		xml = p1.get("signed_xml") or ""
		self.assertIn('DocumentType="CN"', xml)

	def test_plugin_registry_supports_credit_note(self):
		from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY

		self.assertIn("credit_note", COUNTRY_REGISTRY["DE"].document_types)
		self.assertIn("credit_note", COUNTRY_REGISTRY["EG"].document_types)
