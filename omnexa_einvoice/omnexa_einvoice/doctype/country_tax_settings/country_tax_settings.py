# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.country_catalog import integration_tier_for_country
from omnexa_einvoice.tax_engine.plugin.tier_gate import assert_live_production_allowed


class CountryTaxSettings(Document):
	def validate(self):
		code = (self.country_code or "").strip().upper()
		if code in ("EG", "SA"):
			frappe.throw(
				_("Use Branch ETA settings for Egypt or ZATCA Company Settings for Saudi Arabia."),
				title=_("Country Tax Settings"),
			)
		if code not in COUNTRY_REGISTRY:
			frappe.throw(_("Unsupported country code {0}.").format(code))
		meta = COUNTRY_REGISTRY[code]
		if not self.tax_authority_name:
			self.tax_authority_name = meta.label
		if self.configuration_json and str(self.configuration_json).strip():
			try:
				parsed = json.loads(self.configuration_json)
			except json.JSONDecodeError as exc:
				raise frappe.ValidationError(_("Configuration JSON must be valid.")) from exc
			if not isinstance(parsed, dict):
				raise frappe.ValidationError(_("Configuration JSON must be an object."))
		if self.live_production:
			assert_live_production_allowed(code)
		if self.enabled and (self.api_environment or "").strip().lower() == "production":
			assert_live_production_allowed(code)
		if self.enabled and self.api_environment == "production" and not self.live_production:
			frappe.msgprint(
				_("Enable Live Production when using production API environment."),
				indicator="orange",
				alert=True,
			)
		tier = integration_tier_for_country(code)
		if self.enabled and tier != "production":
			frappe.msgprint(
				_("Country {0} is integration tier «{1}» — not government-certified for live use yet.").format(
					code, tier
				),
				indicator="blue",
				title=_("International e-Invoice"),
			)
		if code == "AE":
			self._validate_uae_fields()

	def _validate_uae_fields(self) -> None:
		if self.uae_seller_tin and not self.tax_registration_number:
			self.tax_registration_number = self.uae_seller_tin.strip()
		elif self.tax_registration_number and not self.uae_seller_tin:
			self.uae_seller_tin = self.tax_registration_number.strip()
		tin = (self.uae_seller_tin or self.tax_registration_number or "").strip()
		if self.enabled and tin and (len(tin) != 15 or not tin.isdigit()):
			frappe.throw(
				_("UAE TRN must be exactly 15 digits."),
				title=_("UAE e-Invoice"),
			)
		if self.enabled and not tin:
			frappe.throw(_("Seller TRN is required for UAE e-Invoicing."), title=_("UAE e-Invoice"))
