# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Copy legacy Tax Authority Profile / Signing Profile data onto Branch inline fields."""

from __future__ import annotations

import frappe


def execute():
	if not frappe.db.exists("DocType", "Branch"):
		return

	meta = frappe.get_meta("Branch")
	if not meta.has_field("eta_rin"):
		return

	meta_branch = frappe.get_meta("Branch")
	has_profile_links = meta_branch.has_field("tax_authority_profile")
	fields = ["name", "company"]
	if has_profile_links:
		fields.extend(["tax_authority_profile", "signing_profile"])

	branches = frappe.get_all("Branch", filters={}, fields=fields)
	for row in branches:
		updates: dict = {}
		tap_name = row.get("tax_authority_profile") if has_profile_links else None
		if not tap_name and row.get("company"):
			tap_name = frappe.db.get_value("Tax Authority Profile", {"company": row.company}, "name")
		if tap_name and frappe.db.exists("Tax Authority Profile", tap_name):
			tap = frappe.db.get_value(
				"Tax Authority Profile",
				tap_name,
				[
					"taxpayer_registration_id",
					"eta_environment",
					"eta_base_url",
					"eta_client_id",
					"eta_client_secret",
					"eta_pos_device_serial",
					"eta_activity_code",
					"eta_company_trade_name",
					"eta_branch_code",
					"eta_pos_os_version",
					"eta_address_country",
					"eta_address_governate",
					"eta_address_city",
					"eta_address_street",
					"eta_address_building_number",
					"eta_address_postal_code",
					"eta_address_floor",
					"eta_address_room",
					"eta_address_landmark",
					"eta_address_additional",
					"require_e_invoice_for_sales_invoice",
				],
				as_dict=True,
			)
			if tap:
				updates.update(
					{
						"eta_rin": tap.get("taxpayer_registration_id"),
						"eta_environment": tap.get("eta_environment"),
						"eta_base_url": tap.get("eta_base_url"),
						"eta_client_id": tap.get("eta_client_id"),
						"eta_client_secret": tap.get("eta_client_secret"),
						"eta_pos_device_serial": tap.get("eta_pos_device_serial"),
						"eta_activity_code": tap.get("eta_activity_code"),
						"eta_company_trade_name": tap.get("eta_company_trade_name"),
						"eta_branch_code": tap.get("eta_branch_code"),
						"eta_pos_os_version": tap.get("eta_pos_os_version"),
						"eta_address_country": tap.get("eta_address_country"),
						"eta_address_governate": tap.get("eta_address_governate"),
						"eta_address_city": tap.get("eta_address_city"),
						"eta_address_street": tap.get("eta_address_street"),
						"eta_address_building_number": tap.get("eta_address_building_number"),
						"eta_address_postal_code": tap.get("eta_address_postal_code"),
						"eta_address_floor": tap.get("eta_address_floor"),
						"eta_address_room": tap.get("eta_address_room"),
						"eta_address_landmark": tap.get("eta_address_landmark"),
						"eta_address_additional": tap.get("eta_address_additional"),
						"eta_require_einvoice_before_si_submit": tap.get("require_e_invoice_for_sales_invoice"),
					}
				)

		sp_name = row.get("signing_profile") if has_profile_links else None
		if not sp_name and row.get("company"):
			sp_name = frappe.db.get_value("Signing Profile", {"company": row.company}, "name")
		if sp_name and frappe.db.exists("Signing Profile", sp_name):
			sp = frappe.db.get_value(
				"Signing Profile",
				sp_name,
				[
					"default_signer_mode",
					"signing_secret",
					"windows_signer_command",
					"certificate_reference",
				],
				as_dict=True,
			)
			if sp:
				updates.update(
					{
						"eta_signer_mode": sp.get("default_signer_mode"),
						"eta_signing_secret": sp.get("signing_secret"),
						"eta_windows_signer_command": sp.get("windows_signer_command"),
						"eta_certificate_reference": sp.get("certificate_reference"),
					}
				)

		if updates:
			updates["eta_einvoice_enabled"] = 1
			frappe.db.set_value("Branch", row.name, updates, update_modified=False)
