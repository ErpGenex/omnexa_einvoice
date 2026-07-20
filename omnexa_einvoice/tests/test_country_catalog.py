# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.country_catalog import PLUGIN_CATALOG_BY_CODE, PLUGIN_COUNTRY_CODES
from omnexa_einvoice.tax_engine.registry import resolve_adapter_name


# User-requested countries (ISO2)
USER_COUNTRY_CODES = frozenset(
	{
		"AE",
		"IT",
		"MX",
		"BR",
		"IN",
		"ES",
		"PL",
		"DE",
		"FR",
		"CO",
		"CL",
		"PE",
		"AR",
		"ID",
		"KR",
		"SG",
		"JO",
		"OM",
		"ZA",
		"KE",
		"UG",
		"TR",
		"JP",
		"NL",
		"BE",
		"DK",
		"CN",
		"NO",
		"SE",
		"FI",
		"PT",
		"RO",
	}
)


class TestCountryCatalog(FrappeTestCase):
	def test_user_countries_in_catalog(self):
		missing = USER_COUNTRY_CODES - PLUGIN_COUNTRY_CODES
		self.assertFalse(missing, f"Missing from plugin catalog: {sorted(missing)}")

	def test_each_user_country_has_adapter(self):
		for code in sorted(USER_COUNTRY_CODES):
			with self.subTest(code=code):
				self.assertEqual(resolve_adapter_name(code), f"einvoice_{code.lower()}")
				meta = COUNTRY_REGISTRY[code]
				self.assertTrue(meta.pipeline_enabled)

	def test_catalog_has_arabic_labels(self):
		for code in USER_COUNTRY_CODES:
			entry = PLUGIN_CATALOG_BY_CODE[code]
			self.assertTrue(entry.label_ar, f"No Arabic label for {code}")
