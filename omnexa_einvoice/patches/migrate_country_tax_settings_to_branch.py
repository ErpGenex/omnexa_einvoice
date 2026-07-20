# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Copy legacy Country Tax Settings onto matching branches (company + country_code)."""

from __future__ import annotations

import frappe


def execute():
	if not frappe.db.exists("DocType", "Country Tax Settings"):
		return
	if not frappe.db.has_column("Branch", "intl_tax_enabled"):
		return

	for row in frappe.get_all("Country Tax Settings", fields=["*"]):
		branches = frappe.get_all(
			"Branch",
			filters={"company": row.company, "country_code": row.country_code
	},
			pluck="name",
		)
		for branch_name in branches:
			branch = frappe.get_doc("Branch", branch_name)
			if branch.get("intl_tax_enabled"):
				continue
			branch.intl_tax_enabled = row.enabled
			branch.intl_tax_live_production = row.live_production
			branch.intl_tax_auto_submit_on_si_submit = row.auto_submit_on_si_submit
			branch.intl_tax_api_environment = row.api_environment
			branch.intl_tax_api_base_url = row.api_base_url
			branch.intl_tax_registration_number = row.tax_registration_number
			branch.intl_tax_authority_name = row.tax_authority_name
			branch.intl_tax_signing_mode = row.signing_mode or "scaffold"
			branch.intl_tax_client_id = row.client_id
			branch.intl_tax_configuration_json = row.configuration_json
			branch.intl_tax_remarks = row.remarks
			if row.country_code == "AE":
				branch.intl_uae_seller_tin = row.uae_seller_tin
				branch.intl_uae_peppol_sender_id = row.uae_peppol_sender_id
				branch.intl_uae_peppol_receiver_id = row.uae_peppol_receiver_id
				branch.intl_uae_legal_name_ar = row.uae_legal_name_ar
				branch.intl_uae_invoice_type_code = row.uae_invoice_type_code or "380"
				branch.intl_uae_asp_submit_path = row.uae_asp_submit_path or "/einvoice/v1/submit"
			branch.save(ignore_permissions=True)
			frappe.db.commit()
