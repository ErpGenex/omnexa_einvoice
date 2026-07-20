import frappe
from frappe import _

from omnexa_core.omnexa_core.utils.report_charts import auto_chart_for_columns


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = ["submission_kind = 'E-Invoice'"]
	params = {}
	if filters.get("company"):
		conditions.append("company = %(company)s")
		params["company"] = filters.company
	if filters.get("status"):
		conditions.append("status = %(status)s")
		params["status"] = filters.status
	rows = frappe.db.sql(
		f"""
		SELECT
			name, company, reference_name, status, eta_uuid, authority_uuid, provider_reference, modified
		FROM `tabE Invoice Submission`
		WHERE {' AND '.join(conditions)}
		ORDER BY modified DESC
		""",
		params,
		as_dict=True,
	)
	columns = [
		{"label": _("Submission"), "fieldname": "name", "fieldtype": "Link", "options": "E Invoice Submission", "width": 180
	},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 180
	},
		{"label": _("Sales Invoice"), "fieldname": "reference_name", "fieldtype": "Link", "options": "Sales Invoice", "width": 170
	},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110
	},
		{"label": _("UUID"), "fieldname": "eta_uuid", "fieldtype": "Data", "width": 220
	},
		{"label": _("Authority UUID"), "fieldname": "authority_uuid", "fieldtype": "Data", "width": 220
	},
		{"label": _("Submission ID"), "fieldname": "provider_reference", "fieldtype": "Data", "width": 180
	},
	]
	chart = auto_chart_for_columns(rows, columns)
	return columns, rows, None, chart