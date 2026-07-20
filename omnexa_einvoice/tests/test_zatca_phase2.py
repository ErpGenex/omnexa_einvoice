# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.zatca.phase2.clearance import submit_clearance
from omnexa_einvoice.zatca.phase2.reporting import submit_reporting
from omnexa_einvoice.zatca.phase2.service import run_phase2


class TestZatcaPhase2(FrappeTestCase):
	def test_phase2_scaffold_queues_without_settings(self):
		out = run_phase2(
			{
				"reference_name": "ZATCA-P2-001",
				"document_type": "tax_invoice",
				"company": "Test SA",
				"csid_reference": "csid-test",
				"taxpayer_registration_id": "300000000000003",
				"seller_name": "Seller",
			}
		)
		self.assertTrue(out.get("ok"))
		self.assertEqual(out.get("status"), "queued")
		self.assertTrue(out.get("phase1", {}).get("qr_base64"))

	@patch("omnexa_einvoice.zatca.phase2.clearance.submit_clearance_api")
	def test_clearance_wrapper(self, mock_api):
		import base64

		cleared_b64 = base64.b64encode(b"<Invoice/>").decode("ascii")
		mock_api.return_value = (200, {"clearanceStatus": "CLEARED", "clearedInvoice": cleared_b64})
		settings = type("S", (), {"zatca_environment": "sandbox", "name": "x"})()
		with patch(
			"omnexa_einvoice.zatca.phase2.clearance.get_production_auth",
			return_value=("t", "s"),
		):
			out = submit_clearance(
				settings=settings,
				signed_xml="<Invoice/>",
				invoice_hash_b64="hash",
				uuid="uuid-1",
			)
		self.assertEqual(out["clearance_status"], "CLEARED")

	@patch("omnexa_einvoice.zatca.phase2.reporting.submit_reporting_api")
	def test_reporting_wrapper(self, mock_api):
		mock_api.return_value = (200, {"reportingStatus": "REPORTED"})
		settings = type("S", (), {"zatca_environment": "sandbox", "name": "x"})()
		with patch(
			"omnexa_einvoice.zatca.phase2.reporting.get_production_auth",
			return_value=("t", "s"),
		):
			out = submit_reporting(
				settings=settings,
				signed_xml="<Invoice/>",
				invoice_hash_b64="hash",
				uuid="uuid-2",
			)
		self.assertEqual(out["reporting_status"], "REPORTED")
