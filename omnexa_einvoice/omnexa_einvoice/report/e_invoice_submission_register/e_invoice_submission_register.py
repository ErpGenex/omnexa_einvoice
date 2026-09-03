# Copyright (c) 2026, ErpGenEx
# Auto-generated Global Excellence report pack

import frappe
from frappe import _


def execute(filters=None):
	data = frappe.db.sql(
		"""
		SELECT `name`, `company`, `branch`, `reference_doctype`, `reference_name`, `submission_kind`
		FROM `tabE Invoice Submission`
		ORDER BY modified DESC
		LIMIT 500
		""",
		as_dict=True,
	)
	columns = [
		{"label": _("Name"), "fieldname": "name", "fieldtype": "Link", "width": 140},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "width": 120},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "width": 120},
		{"label": _("Reference DocType"), "fieldname": "reference_doctype", "fieldtype": "Link", "width": 120},
		{"label": _("Reference Name"), "fieldname": "reference_name", "fieldtype": "Data", "width": 120},
		{"label": _("Submission Kind"), "fieldname": "submission_kind", "fieldtype": "Select", "width": 120}
	]
	return columns, data
