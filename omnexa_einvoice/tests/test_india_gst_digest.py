# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.countries.india_gst_digest import (
	canonical_gst_json_bytes,
	sign_gst_irn_digest,
	validate_gsp_config,
)
from omnexa_einvoice.tax_engine.plugin.engines.india import build_gst_irn_json
from omnexa_einvoice.tax_engine.plugin.signing_providers import build_signing_context, sign_with_provider


class TestIndiaGstDigest(FrappeTestCase):
	def test_canonical_stable(self):
		a = json.dumps({"Version": "1.1", "DocDtls": {"No": "1"
	}, "_meta": {"x": 1}
	})
		b = json.dumps({"_meta": {"y": 2
	}, "DocDtls": {"No": "1"
	}, "Version": "1.1"
	})
		self.assertEqual(canonical_gst_json_bytes(a), canonical_gst_json_bytes(b))

	def test_sign_adds_meta_hash(self):
		raw = build_gst_irn_json(
			{
				"reference_name": "SI-IN-D",
				"issue_datetime": "2026-05-20",
				"seller": {"tax_registration": "29AABCT1332L000", "name": "S"
	},
				"buyer": {"tax_registration": "29AABCT1332L001", "name": "B"
	},
				"lines": [{"description": "Item", "qty": 1, "rate": 100, "amount": 100
	}],
				"totals": {"net_total": 100, "tax_total": 18, "grand_total": 118}
	}
		)
		out = sign_gst_irn_digest(raw, signing_secret="test-secret")
		data = json.loads(out["signed_xml"])
		self.assertIn("InvoiceHash", data["_meta"])
		self.assertIn("DigestSig", data["_meta"])
		self.assertEqual(out["signer"], "digest:gst-irn-scaffold")

	def test_provider_routes_in_digest(self):
		raw = build_gst_irn_json({"reference_name": "X", "totals": {
	}, "lines": []
	})
		ctx = build_signing_context(
			country_code="IN",
			settings=frappe._dict(api_environment="sandbox"),
			config={"signing_mode": "digest", "gstin": "29AABCT1332L000"
	},
		)
		out = sign_with_provider(raw, ctx)
		self.assertEqual(out["signer"], "digest:gst-irn-scaffold")

	def test_validate_gsp_config(self):
		self.assertGreaterEqual(len(validate_gsp_config({})), 2)
