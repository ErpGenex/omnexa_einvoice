# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ZATCACompanySettings(Document):
	def validate(self):
		if self.enabled and not (self.vat_registration_number or "").strip():
			frappe.throw(_("VAT Registration Number is required when ZATCA is enabled."), title=_("ZATCA"))
		if self.zatca_phase == "Phase 2" and self.enabled:
			if not self.get_password("production_security_token", raise_exception=False):
				frappe.msgprint(
					_("Phase 2 requires Production CSID. Complete onboarding first."),
					indicator="orange",
					title=_("ZATCA"),
				)
