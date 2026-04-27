import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = ["submission_kind = 'E-Receipt'"]
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
		{"label": "Submission", "fieldname": "name", "fieldtype": "Link", "options": "E Invoice Submission", "width": 180},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 180},
		{"label": "Receipt Source", "fieldname": "reference_name", "fieldtype": "Data", "width": 170},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": "UUID", "fieldname": "eta_uuid", "fieldtype": "Data", "width": 220},
		{"label": "Authority UUID", "fieldname": "authority_uuid", "fieldtype": "Data", "width": 220},
		{"label": "Submission ID", "fieldname": "provider_reference", "fieldtype": "Data", "width": 180},
	]
	return columns, rows
