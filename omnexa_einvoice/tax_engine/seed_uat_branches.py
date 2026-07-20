# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Seed one UAT Branch per supported country (sandbox / mock API URLs)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.country_catalog import (
	PLUGIN_COUNTRY_CODES,
	branch_country_label_for_code,
	country_display_name,
	get_catalog_entry,
)
from omnexa_einvoice.tax_engine.registry import resolve_adapter_name

# Demo tax IDs (format hints only — not real taxpayer numbers).
MOCK_TAX_IDS: dict[str, str] = {
	"EG": "123456789",
	"SA": "300000000000003",
	"AE": "100000000000003",
	"AR": "20123456789",
	"BR": "11222333000181",
	"CL": "761234567",
	"CO": "900123456",
	"DE": "DE123456789",
	"ES": "B12345678",
	"FR": "12345678901234",
	"IN": "29AABCT1332L000",
	"IT": "12345678901",
	"JO": "123456789",
	"MX": "EKU9003173C9",
	"PE": "20123456789",
	"PL": "5252525252",
	"OM": "OM1234567",
	"BH": "BH1234567",
	"KW": "KW1234567",
	"QA": "QA1234567",
	"NL": "NL123456789B01",
	"BE": "BE0123456789",
	"DK": "DK12345678",
	"NO": "NO123456789MVA",
	"SE": "SE556123456701",
	"FI": "FI12345678",
	"PT": "PT123456789",
	"RO": "RO12345678",
	"SG": "SG12345678A",
	"ID": "ID123456789012345",
	"KR": "1234567890",
	"JP": "1234567890123",
	"CN": "91110000123456789X",
	"ZA": "4123456789",
	"KE": "P051234567X",
	"UG": "1000123456",
	"TR": "1234567890"
	}


def _sandbox_url(code: str, path: str = "") -> str:
	base = f"https://sandbox.uat.{code.lower()}.erpgenex.local"
	return f"{base}{path}" if path else base


def _configuration_for_country(code: str) -> dict[str, Any]:
	entry = get_catalog_entry(code)
	engine = entry.engine if entry else "peppol_ubl"
	cfg: dict[str, Any] = {
		"uat_seed": True,
		"signing_mode": "scaffold"
	}
	if engine == "cfdi":
		cfg.update(
			{
				"signing_mode": "csd",
				"pac_provider": "uat-pac",
				"pac_base_url": _sandbox_url(code, "/timbrado")}
		)
	elif engine == "gst_irn":
		cfg.update(
			{
				"signing_mode": "digest",
				"gstin": MOCK_TAX_IDS.get(code, ""),
				"gsp_base_url": _sandbox_url(code, "/einvoice")}
		)
	elif engine == "nfe":
		cfg.update(
			{
				"signing_mode": "a1",
				"cnpj": MOCK_TAX_IDS.get(code, ""),
				"uf": "35",
				"ambiente": "homologacao",
				"sefaz_base_url": _sandbox_url(code, "/nfe")}
		)
	elif engine == "fatturapa":
		cfg.update(
			{
				"signing_mode": "cades",
				"partita_iva": MOCK_TAX_IDS.get(code, ""),
				"sdi_base_url": _sandbox_url(code, "/sdi")}
		)
	elif engine == "ksef_fa2":
		cfg.update(
			{
				"signing_mode": "ksef",
				"nip": MOCK_TAX_IDS.get(code, ""),
				"ksef_base_url": _sandbox_url(code, "/ksef")}
		)
	elif engine == "facturae":
		cfg.update(
			{
				"signing_mode": "xmldsig",
				"nif": MOCK_TAX_IDS.get(code, ""),
				"aeat_base_url": _sandbox_url(code, "/facturae")}
		)
	elif engine == "dian_ubl":
		cfg.update(
			{
				"signing_mode": "digest",
				"nit": MOCK_TAX_IDS.get(code, ""),
				"dian_base_url": _sandbox_url(code, "/dian")}
		)
	elif engine == "xrechnung":
		cfg.update(
			{
				"signing_mode": "xmldsig",
				"leitweg_id": "04011000-12345-67",
				"gateway_base_url": _sandbox_url(code, "/xrechnung")}
		)
	elif engine == "facturx":
		cfg.update(
			{
				"signing_mode": "xmldsig",
				"siret": MOCK_TAX_IDS.get(code, ""),
				"pdp_base_url": _sandbox_url(code, "/facturx")}
		)
	elif engine == "latam_invoice":
		key = {"AR": "cuit", "CL": "rut", "PE": "ruc"
	}.get(code, "tax_id")
		cfg.update(
			{
				"signing_mode": "digest",
				key: MOCK_TAX_IDS.get(code, ""),
				"authority_base_url": _sandbox_url(code, "/authority")}
		)
	elif engine == "jofotara":
		cfg.update(
			{
				"signing_mode": "digest",
				"tin": MOCK_TAX_IDS.get(code, ""),
				"jofotara_base_url": _sandbox_url(code, "/jofotara")}
		)
	elif engine == "pint_ae":
		cfg.update({"signing_mode": "xmldsig", "asp_submit_path": "/einvoice/v1/submit"
	})
	elif engine in ("pint_gulf", "peppol_ubl"):
		cfg.update({"signing_mode": "xmldsig"
	})
	return cfg


def _apply_sa_branch(doc) -> None:
	doc.intl_tax_enabled = 0
	_clear_eta_fields(doc)
	doc.zatca_enabled = 1
	doc.zatca_phase = "1"
	doc.zatca_environment = "sandbox"
	doc.zatca_vat_registration_number = MOCK_TAX_IDS["SA"]
	doc.zatca_organization_name = "UAT Saudi Entity"
	doc.zatca_egs_serial_number = "UAT-EGS-001"


def _clear_eta_fields(doc) -> None:
	doc.eta_einvoice_enabled = 0
	doc.eta_ereceipt_enabled = 0
	doc.eta_signer_mode = "remote"


def _apply_eg_branch(doc) -> None:
	doc.intl_tax_enabled = 0
	_clear_eta_fields(doc)
	doc.intl_tax_remarks = "UAT Egypt branch — use ETA tab for ETA tests; not international plugin."


def _apply_intl_branch(doc, code: str) -> None:
	entry = get_catalog_entry(code)
	doc.intl_tax_enabled = 1
	doc.intl_tax_api_environment = "sandbox"
	doc.intl_tax_live_production = 0
	doc.intl_tax_auto_submit_on_si_submit = 0
	doc.intl_tax_registration_number = MOCK_TAX_IDS.get(code, f"UAT-{code}")
	doc.intl_tax_api_base_url = _sandbox_url(code)
	doc.intl_tax_authority_name = entry.authority if entry else code
	doc.intl_tax_signing_mode = _configuration_for_country(code).get("signing_mode") or "scaffold"
	doc.intl_tax_configuration_json = json.dumps(_configuration_for_country(code), indent=2)
	doc.intl_tax_remarks = f"Auto-seeded UAT branch for {code}. Mock API — enable real URL for authority UAT."
	_clear_eta_fields(doc)
	if code == "AE":
		tin = MOCK_TAX_IDS["AE"]
		doc.intl_uae_seller_tin = tin
		doc.intl_tax_registration_number = tin
		doc.intl_uae_peppol_sender_id = f"0235:{tin}"
		doc.intl_uae_peppol_receiver_id = "0235:100000000000004"
		doc.intl_uae_asp_submit_path = "/einvoice/v1/submit"


@frappe.whitelist()
def seed_uat_branches(company: str | None = None, *, update_existing: bool = True) -> dict[str, Any]:
	"""
	Create/update Branch rows: one per country (EG, SA, + all plugin countries).
	Naming: {company}-UAT-{CODE}  (branch_code = UAT-{CODE}).
	"""
	company = (company or frappe.defaults.get_global_default("company") or "").strip()
	if not company:
		frappe.throw("Set company=Your Company on bench execute.")
	if not frappe.db.exists("Company", company):
		frappe.throw(f"Company {company} does not exist.")

	codes = sorted({"EG", "SA", *PLUGIN_COUNTRY_CODES})
	created: list[str] = []
	updated: list[str] = []
	skipped: list[str] = []

	frappe.flags.ignore_mandatory = True
	try:
		_seed_loop(company, codes, update_existing, created, updated, skipped)
	finally:
		frappe.flags.ignore_mandatory = False

	frappe.db.commit()
	return {
		"ok": True,
		"company": company,
		"total_countries": len(codes),
		"created": created,
		"updated": updated,
		"skipped": skipped,
		"message": _("Seeded {0} UAT branches on company {1}.").format(len(codes), company)}


def _seed_loop(
	company: str,
	codes: list[str],
	update_existing: bool,
	created: list[str],
	updated: list[str],
	skipped: list[str],
) -> None:
	for code in codes:
		branch_code = f"UAT-{code}"
		name = f"{company}-{branch_code}"
		is_new = not frappe.db.exists("Branch", name)
		if not is_new and not update_existing:
			skipped.append(name)
			continue

		if is_new:
			doc = frappe.new_doc("Branch")
			doc.company = company
			doc.branch_code = branch_code
		else:
			doc = frappe.get_doc("Branch", name)

		doc.branch_name = f"UAT {country_display_name(code)}"
		doc.country_code = branch_country_label_for_code(code)
		doc.status = "Active"
		doc.is_head_office = 0
		entry = get_catalog_entry(code)
		try:
			doc.default_vat_rate = float(entry.vat_percent) if entry and entry.vat_percent else 0.0
		except (TypeError, ValueError):
			doc.default_vat_rate = 0.0

		if code == "EG":
			_apply_eg_branch(doc)
		elif code == "SA":
			_apply_sa_branch(doc)
		else:
			_apply_intl_branch(doc, code)

		doc.flags.ignore_permissions = True
		doc.flags.ignore_links = True
		if is_new:
			doc.db_insert()
			created.append(name)
		else:
			doc.db_update()
			updated.append(name)

		# db_insert skips validate hooks — sync ISO + tax_provider.
		frappe.db.set_value(
			"Branch",
			name,
			{
				"country_iso": code,
				"country_code": branch_country_label_for_code(code),
				"country_name": country_display_name(code),
				"tax_provider": resolve_adapter_name(code)
	},
			update_modified=False,
		)
