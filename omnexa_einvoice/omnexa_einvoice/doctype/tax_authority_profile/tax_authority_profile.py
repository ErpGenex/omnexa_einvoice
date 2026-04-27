# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TaxAuthorityProfile(Document):
	def validate(self):
		existing = frappe.db.get_value("Tax Authority Profile", {"company": self.company}, "name")
		if existing and existing != self.name:
			frappe.throw(_("A Tax Authority Profile already exists for company {0}.").format(self.company))
		self._validate_policy_controls()

	def _validate_policy_controls(self):
		if self.default_einvoice_adapter in {"einvoice_eta", "einvoice_zatca"} and not self.taxpayer_registration_id:
			frappe.throw(_("Taxpayer Registration ID is mandatory for ETA/ZATCA adapters."), title=_("Compliance"))
		if self.default_einvoice_adapter == "einvoice_eta":
			if not self.eta_base_url:
				frappe.throw(_("ETA Base URL is mandatory for ETA adapter."), title=_("Compliance"))
			if not self.eta_client_id or not self.eta_client_secret:
				frappe.throw(_("ETA Client ID and Secret are mandatory for ETA adapter."), title=_("Compliance"))
		if self.default_einvoice_adapter == "einvoice_zatca" and not self.zatca_reporting_phase:
			frappe.throw(_("ZATCA Reporting Phase is mandatory for ZATCA adapter."), title=_("Compliance"))
		if self.require_e_invoice_for_sales_invoice and not self.default_einvoice_adapter:
			frappe.throw(_("Default adapter is mandatory when e-invoice policy is enforced."), title=_("Policy"))
