# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Shared fixtures for omnexa_einvoice tests."""

from __future__ import annotations

import frappe

from omnexa_core.omnexa_core.test_data import create_test_company, ensure_pilot_geo


def get_or_create_test_company(abbr: str | None = None) -> str:
	ensure_pilot_geo()
	suffix = frappe.generate_hash(length=6)
	label = abbr or f"OMNX-EINV-{suffix}"
	return create_test_company(label[:10], company_name=f"Test Co {suffix}")


def create_tax_authority_profile(company: str, suffix: str) -> str:
	existing = frappe.db.get_value("Tax Authority Profile", {"company": company
	}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Tax Authority Profile",
			"company": company,
			"default_einvoice_adapter": "einvoice_stub",
			"taxpayer_registration_id": f"TIN-{suffix}"
	}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def create_signing_profile(company: str, suffix: str) -> str:
	existing = frappe.db.get_value("Signing Profile", {"company": company
	}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Signing Profile",
			"company": company,
			"default_signer_mode": "remote",
			"certificate_reference": f"vault://eta/{suffix}"
	}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def create_eta_branch(
	company: str,
	suffix: str | None = None,
	*,
	ereceipt: bool = False,
	einvoice: bool = False,
	signing_agent: bool = False,
	require_einvoice_before_si: int = 0,
	usb_pin: str = "1234",
) -> str:
	"""Insert Branch with optional Egypt ETA credentials (profiles required when e-invoice is on)."""
	suffix = suffix or frappe.generate_hash(length=6)
	code = f"E{suffix[:4].upper()}"
	fields: dict = {
		"doctype": "Branch",
		"company": company,
		"branch_name": f"ETA {suffix
	}",
		"branch_code": code,
		"status": "Active"
	}
	if einvoice:
		tax = create_tax_authority_profile(company, suffix)
		sign = create_signing_profile(company, suffix)
		fields.update(
			{
				"eta_einvoice_enabled": 1,
				"tax_authority_profile": tax,
				"signing_profile": sign,
				"eta_invoice_environment": "preprod",
				"eta_invoice_client_id": f"inv-{suffix
	}",
				"eta_invoice_rin": "123456789",
				"eta_signer_mode": "signing_agent" if signing_agent else "remote"
	}
		)
		if signing_agent:
			fields["eta_signing_agent_url"] = "http://127.0.0.1:5002"
			if usb_pin:
				fields["eta_usb_signing_pin"] = usb_pin
	if ereceipt:
		fields.update(
			{
				"eta_ereceipt_enabled": 1,
				"eta_receipt_environment": "preprod",
				"eta_receipt_base_url": "https://api.preprod.invoicing.eta.gov.eg",
				"eta_receipt_client_id": f"rcpt-{suffix
	}",
				"eta_receipt_rin": "123456789",
				"eta_activity_code": "4620",
				"eta_pos_device_serial": "DEV-TEST-01"
	}
		)
	if require_einvoice_before_si:
		fields["eta_require_einvoice_before_si_submit"] = 1

	doc = frappe.get_doc(fields)
	if einvoice:
		doc.eta_invoice_client_secret = f"secret-{suffix}"
	if ereceipt:
		doc.eta_receipt_client_secret = f"rcpt-secret-{suffix}"
	doc.insert(ignore_permissions=True)
	return doc.name


def create_intl_branch(
	company: str,
	country_code: str = "DE",
	suffix: str | None = None,
) -> str:
	suffix = suffix or frappe.generate_hash(length=6)
	code = f"I{suffix[:4].upper()}"
	doc = frappe.get_doc(
		{
			"doctype": "Branch",
			"company": company,
			"branch_name": f"Intl {country_code} {suffix
	}",
			"branch_code": code,
			"status": "Active",
			"country_code": f"{country_code
	} — Germany" if country_code == "DE" else country_code,
			"intl_tax_enabled": 1,
			"intl_tax_api_environment": "sandbox",
			"intl_tax_registration_number": "12345678901"
	}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def stub_submission_fields(company: str | None = None) -> dict:
	co = company or get_or_create_test_company()
	branch = frappe.db.get_value("Branch", {"company": co, "status": "Active"
	}, "name")
	if not branch:
		branch = frappe.get_doc(
			{
				"doctype": "Branch",
				"company": co,
				"branch_name": "Stub Submission Branch",
				"branch_code": f"S{frappe.generate_hash(length=4).upper()[:4]
	}",
				"status": "Active"
	}
		).insert(ignore_permissions=True).name
	return {
		"company": co,
		"branch": branch,
		"submission_channel": "API"
	}
