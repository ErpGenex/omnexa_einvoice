# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SigningProfile(Document):
	def validate(self):
		existing = frappe.db.get_value("Signing Profile", {"company": self.company}, "name")
		if existing and existing != self.name:
			frappe.throw(_("A Signing Profile already exists for company {0}.").format(self.company))
