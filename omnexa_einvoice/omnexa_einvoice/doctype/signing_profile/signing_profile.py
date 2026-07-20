# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate


class SigningProfile(Document):
	def validate(self):
		existing = frappe.db.get_value("Signing Profile", {"company": self.company}, "name")
		if existing and existing != self.name:
			frappe.throw(_("A Signing Profile already exists for company {0}.").format(self.company))
		self._validate_signing_controls()

	def _validate_signing_controls(self):
		if self.default_signer_mode == "windows_app" and not self.certificate_reference:
			frappe.throw(_("Certificate / Token Reference is mandatory for windows_app signer mode."), title=_("Signing"))
		if not self.key_rotation_date:
			# Backward-compatible default for legacy inserts/tests that predate this field.
			self.key_rotation_date = nowdate()
