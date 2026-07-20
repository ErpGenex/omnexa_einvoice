# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.plugin.http_retry import build_idempotency_key, post_json_with_retry


class TestHttpRetry(FrappeTestCase):
	def test_idempotency_key(self):
		key = build_idempotency_key(
			country_code="DE",
			uuid="abc-123",
			document={"reference_name": "SI-001"},
		)
		self.assertEqual(key, "DE-abc-123")

	def test_retry_on_429(self):
		res_ok = MagicMock(status_code=200, text='{"status":"ACCEPTED"}')
		res_ok.json.return_value = {"status": "ACCEPTED"}
		res_429 = MagicMock(status_code=429, text="")
		with patch("omnexa_einvoice.tax_engine.plugin.http_retry.requests.post") as post:
			post.side_effect = [res_429, res_ok]
			with patch("omnexa_einvoice.tax_engine.plugin.http_retry.time.sleep"):
				out = post_json_with_retry(
					"https://example.com/submit",
					headers={},
					payload={},
					timeout=10,
					max_retries=2,
				)
		self.assertEqual(out.status_code, 200)
		self.assertEqual(post.call_count, 2)
