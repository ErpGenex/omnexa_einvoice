# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from frappe.tests.utils import FrappeTestCase

from omnexa_core.omnexa_core.integration_hub import IntegrationHubError, get_default_hub


class TestEInvoiceHubAdapters(FrappeTestCase):
	def test_eta_adapter_queues_invoice(self):
		hub = get_default_hub()
		result = hub.dispatch(
			"einvoice_eta",
			{
				"reference_name": "SI-0001",
				"document_type": "invoice",
				"taxpayer_rin": "123456789",
				"operation": "submit",
				"signer_mode": "windows_app",
			},
			idempotency_key="eta-1",
		)
		self.assertEqual(result.status, "queued")
		self.assertTrue(result.provider_reference.startswith("ETA-SUBMIT-INVOICE"))
		self.assertEqual(result.data["signer_mode"], "windows_app")

	def test_eta_cancel_requires_authority_uuid(self):
		hub = get_default_hub()
		with self.assertRaises(IntegrationHubError):
			hub.dispatch(
				"einvoice_eta",
				{
					"reference_name": "SI-0001",
					"document_type": "invoice",
					"taxpayer_rin": "123456789",
					"operation": "cancel",
				},
				idempotency_key="eta-cancel-1",
			)

	def test_zatca_phase2_requires_csid(self):
		hub = get_default_hub()
		with self.assertRaises(IntegrationHubError):
			hub.dispatch(
				"einvoice_zatca",
				{"reference_name": "SI-0002", "document_type": "tax_invoice", "phase": "phase2"},
				idempotency_key="zatca-1",
			)

	def test_zatca_adapter_accepts_valid_phase2_payload(self):
		hub = get_default_hub()
		result = hub.dispatch(
			"einvoice_zatca",
			{
				"reference_name": "SI-0003",
				"document_type": "tax_invoice",
				"phase": "phase2",
				"csid_reference": "csid-abc",
				"company": "Test SA",
				"taxpayer_registration_id": "300000000000003",
				"seller_name": "SA Seller",
			},
			idempotency_key="zatca-2",
		)
		self.assertEqual(result.status, "queued")
		self.assertTrue(result.provider_reference.startswith("ZATCA-TAX_INVOICE"))

	def test_zatca_phase1_via_hub(self):
		hub = get_default_hub()
		result = hub.dispatch(
			"einvoice_zatca",
			{
				"reference_name": "SI-0004",
				"document_type": "tax_invoice",
				"phase": "phase1",
				"company": "Test SA",
				"taxpayer_registration_id": "300000000000003",
				"seller_name": "SA Seller",
			},
			idempotency_key="zatca-p1",
		)
		self.assertEqual(result.status, "completed")
		self.assertTrue((result.data or {}).get("zatca", {}).get("qr_base64"))
