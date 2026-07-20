# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.zatca.phase1.qr_embed import embed_qr_in_ubl, qr_tlv_to_png_base64
from omnexa_einvoice.zatca.phase1.tlv_qr import build_tlv_qr_base64
from omnexa_einvoice.zatca.phase1.ubl_builder import build_ubl_invoice_xml


class TestZatcaQrEmbed(FrappeTestCase):
	def test_embed_qr_in_ubl_xml(self):
		payload = {
			"uuid": "test-uuid-qr",
			"document_type": "tax_invoice",
			"reference_name": "SI-QR-1",
			"issue_datetime": "2026-05-19T12:00:00",
			"currency": "SAR",
			"lines": [{"description": "Item", "qty": 1, "rate": 100, "net_amount": 100
	}],
			"totals": {"net_total": 100, "tax_total": 15, "grand_total": 115}
	}
		seller = {"name": "Seller", "name_ar": "بائع", "vat_registration": "300000000000003"
	}
		xml_text, _ = build_ubl_invoice_xml(payload, icv=1, previous_hash="", seller=seller)
		qr_b64 = build_tlv_qr_base64(
			seller_name="بائع",
			vat_registration="300000000000003",
			timestamp="2026-05-19T12:00:00",
			invoice_total_with_vat="115.00",
			vat_amount="15.00",
		)
		embedded = embed_qr_in_ubl(xml_text, qr_b64)
		self.assertIn("EmbeddedDocumentBinaryObject", embedded)
		self.assertIn(qr_b64[:32], embedded)

	def test_qr_png_generation(self):
		qr_b64 = build_tlv_qr_base64(
			seller_name="Test",
			vat_registration="300000000000003",
			timestamp="2026-05-19T12:00:00",
			invoice_total_with_vat="100.00",
			vat_amount="15.00",
		)
		png_b64 = qr_tlv_to_png_base64(qr_b64)
		self.assertTrue(len(png_b64) > 100)
