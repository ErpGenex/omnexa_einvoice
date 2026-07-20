# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Country-aware tax authority connection tests (Branch + consoles)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.branch_country_tax import country_tab_label
from omnexa_einvoice.tax_engine.country_catalog import PLUGIN_COUNTRY_CODES, normalize_country_code
from omnexa_einvoice.tax_engine.registry import resolve_adapter_name
from omnexa_einvoice.zatca.branch_settings import branch_has_zatca


def _resolve_branch(branch: str | None, company: str | None) -> str:
	if branch:
		return branch
	if company:
		name = frappe.db.get_value(
			"Branch",
			{"company": company, "is_head_office": 1},
			"name",
			order_by="creation asc",
		) or frappe.db.get_value("Branch", {"company": company}, "name")
		if name:
			return name
	frappe.throw(_("Select a branch or company."), title=_("Tax connection test"))


def _branch_country(branch: str) -> str:
	raw_iso = frappe.db.get_value("Branch", branch, "country_iso")
	if raw_iso:
		return normalize_country_code(raw_iso)
	raw = frappe.db.get_value("Branch", branch, "country_code") or "EG"
	return normalize_country_code(raw)


@frappe.whitelist()
def get_branch_tax_test_spec(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	"""UI metadata: button label and country for Branch / consoles."""
	if not branch and not company:
		return {
			"branch": "",
			"country_code": "",
			"kind": "none",
			"tab_label": "",
			"button_label": _("Test tax connection"),
			"button_group": _("Tax"),
			"configured": False,
			"needs_branch": True,
		}
	try:
		branch = _resolve_branch(branch, company)
	except frappe.ValidationError:
		return {
			"branch": "",
			"country_code": "",
			"kind": "none",
			"tab_label": "",
			"button_label": _("Test tax connection"),
			"button_group": _("Tax"),
			"configured": False,
			"needs_branch": True,
		}
	code = _branch_country(branch)
	tab_label = country_tab_label(code)
	doc = frappe.get_doc("Branch", branch)

	if code == "IN":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "gst_irn",
			"tab_label": tab_label,
			"button_label": _("Test India GSP / IRN connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "MX":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "cfdi",
			"tab_label": tab_label,
			"button_label": _("Test Mexico PAC connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "IT":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "fatturapa",
			"tab_label": tab_label,
			"button_label": _("Test Italy SDI connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "BR":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "nfe",
			"tab_label": tab_label,
			"button_label": _("Test Brazil SEFAZ connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "PL":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "ksef_fa2",
			"tab_label": tab_label,
			"button_label": _("Test Poland KSeF connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "ES":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "facturae",
			"tab_label": tab_label,
			"button_label": _("Test Spain AEAT connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "CO":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "dian_ubl",
			"tab_label": tab_label,
			"button_label": _("Test Colombia DIAN connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "DE":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "xrechnung",
			"tab_label": tab_label,
			"button_label": _("Test Germany XRechnung connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "FR":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "facturx",
			"tab_label": tab_label,
			"button_label": _("Test France PDP connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "AE":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "pint_ae",
			"tab_label": tab_label,
			"button_label": _("Test UAE ASP connection"),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
		}

	if code == "EG":
		if doc.get("eta_ereceipt_enabled"):
			kind = "eta_receipt"
			btn = _("Test ETA E-Receipt connection")
		elif doc.get("eta_einvoice_enabled"):
			kind = "eta_invoice"
			btn = _("Test ETA e-Invoice connection")
		else:
			kind = "eta_none"
			btn = _("Test ETA connection")
		return {
			"branch": branch,
			"country_code": code,
			"kind": kind,
			"tab_label": tab_label,
			"button_label": btn,
			"button_group": tab_label,
			"configured": bool(doc.get("eta_ereceipt_enabled") or doc.get("eta_einvoice_enabled")),
		}

	if code == "SA":
		return {
			"branch": branch,
			"country_code": code,
			"kind": "zatca",
			"tab_label": tab_label,
			"button_label": _("Test ZATCA connection"),
			"button_group": tab_label,
			"configured": branch_has_zatca(branch),
		}

	if code in PLUGIN_COUNTRY_CODES:
		return {
			"branch": branch,
			"country_code": code,
			"kind": "plugin",
			"tab_label": tab_label,
			"button_label": _("Test {0} connection").format(tab_label),
			"button_group": tab_label,
			"configured": bool(doc.get("intl_tax_enabled")),
			"provider": resolve_adapter_name(code),
		}

	return {
		"branch": branch,
		"country_code": code,
		"kind": "unknown",
		"tab_label": tab_label,
		"button_label": _("Test tax connection"),
		"button_group": tab_label,
		"configured": False,
	}


def _test_eg(branch: str) -> dict[str, Any]:
	doc = frappe.get_doc("Branch", branch)
	if doc.get("eta_ereceipt_enabled"):
		from omnexa_einvoice.ereceipt_console import test_eta_receipt_connection

		out = test_eta_receipt_connection(branch=branch)
		out["kind"] = "eta_receipt"
		return out
	if doc.get("eta_einvoice_enabled"):
		from omnexa_einvoice.einvoice_console import test_eta_einvoice_connection

		out = test_eta_einvoice_connection(branch=branch)
		out["kind"] = "eta_invoice"
		return out
	return {
		"ok": False,
		"branch": branch,
		"country_code": "EG",
		"kind": "eta_none",
		"message": _("Enable Egypt ETA (e-Invoice or E-Receipt) on this branch."),
		"checklist": [
			_("Set Country Code to EG."),
			_("Open Egypt ETA tab → enable e-Invoice and/or E-Receipt."),
			_("Save the branch, then run the test again."),
		],
	}


def _test_sa(branch: str) -> dict[str, Any]:
	doc = frappe.get_doc("Branch", branch)
	tab_label = country_tab_label("SA")
	checklist: list[str] = []
	if normalize_country_code(doc.country_code) != "SA":
		return {
			"ok": False,
			"branch": branch,
			"country_code": "SA",
			"kind": "zatca",
			"message": _("Branch country is not SA."),
		}
	if not doc.get("zatca_enabled"):
		return {
			"ok": False,
			"branch": branch,
			"country_code": "SA",
			"kind": "zatca",
			"message": _("Enable ZATCA on Branch → Saudi ZATCA tab."),
			"checklist": [_("Enable ZATCA on the Saudi ZATCA tab."), _("Save the branch.")],
		}

	required = [
		("zatca_vat_registration_number", _("VAT registration number")),
		("zatca_organization_name", _("Organization name")),
		("zatca_egs_serial_number", _("EGS serial number")),
	]
	missing = []
	for field, label in required:
		if not (doc.get(field) or "").strip():
			missing.append(label)
	if missing:
		return {
			"ok": False,
			"branch": branch,
			"country_code": "SA",
			"kind": "zatca",
			"message": _("Complete ZATCA branch settings before testing."),
			"checklist": [_("Missing: {0}").format(", ".join(missing))],
		}

	has_cert = bool((doc.get("zatca_certificate_pem") or "").strip())
	has_csr = bool((doc.get("zatca_csr_pem") or "").strip())
	if not has_cert and not has_csr:
		checklist.append(_("Generate CSR / onboarding certificate on the ZATCA tab."))

	try:
		from omnexa_einvoice.zatca.branch_settings import branch_to_zatca_settings

		settings = branch_to_zatca_settings(branch)
		env = settings.get("zatca_environment") or doc.get("zatca_environment") or ""
		return {
			"ok": True,
			"branch": branch,
			"country_code": "SA",
			"kind": "zatca",
			"environment": env,
			"vat": settings.get("vat_registration_number") or "",
			"phase": settings.get("zatca_phase") or doc.get("zatca_phase"),
			"message": _("ZATCA branch configuration looks valid. Use Sales Invoice → ZATCA Phase 1 for a live API test."),
			"checklist": checklist,
		}
	except Exception as exc:
		return {
			"ok": False,
			"branch": branch,
			"country_code": "SA",
			"kind": "zatca",
			"message": str(exc),
			"checklist": checklist,
		}


def _test_plugin(branch: str, code: str) -> dict[str, Any]:
	doc = frappe.get_doc("Branch", branch)
	tab_label = country_tab_label(code)
	if not doc.get("intl_tax_enabled"):
		return {
			"ok": False,
			"branch": branch,
			"country_code": code,
			"kind": "plugin",
			"message": _("Enable e-invoice on Branch → {0} tab.").format(tab_label),
			"checklist": [_("Turn on intl_tax_enabled on the Country Tax tab."), _("Save the branch.")],
		}
	try:
		from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings

		settings = validate_production_settings(
			doc.company,
			code,
			phase="phase1",
			branch=branch,
		)
		env = (settings.get("api_environment") if settings else "") or doc.get("intl_api_environment") or ""
		base = (settings.get("api_base_url") if settings else "") or doc.get("intl_api_base_url") or ""
		live = bool(settings.get("live_production")) if settings else bool(doc.get("intl_live_production"))
		return {
			"ok": True,
			"branch": branch,
			"country_code": code,
			"kind": "plugin",
			"environment": env,
			"api_base_url": base,
			"live_production": live,
			"provider": resolve_adapter_name(code),
			"message": _("{0} branch settings validated for Phase 1.").format(tab_label),
		}
	except frappe.ValidationError as exc:
		return {
			"ok": False,
			"branch": branch,
			"country_code": code,
			"kind": "plugin",
			"message": str(exc),
			"checklist": [
				_("Complete Branch → Country Tax tab fields."),
				_("Set API Base URL and Tax Registration Number."),
				_("For live production, enable Live Production and API credentials."),
			],
		}


@frappe.whitelist()
def test_branch_tax_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	"""Run country-appropriate connection / configuration test for a branch."""
	branch = _resolve_branch(branch, company)
	code = _branch_country(branch)
	spec = get_branch_tax_test_spec(branch=branch)

	if code == "EG":
		out = _test_eg(branch)
	elif code == "SA":
		out = _test_sa(branch)
	elif code == "IN":
		from omnexa_einvoice.tax_engine.countries.india_gsp import test_india_gsp_connection

		out = test_india_gsp_connection(branch=branch, company=company)
		out.setdefault("country_code", "IN")
		out.setdefault("kind", "gst_irn")
	elif code == "MX":
		from omnexa_einvoice.tax_engine.countries.mexico_pac_client import test_mexico_pac_connection

		out = test_mexico_pac_connection(branch=branch, company=company)
		out.setdefault("country_code", "MX")
		out.setdefault("kind", "cfdi")
	elif code == "IT":
		from omnexa_einvoice.tax_engine.countries.italy_sdi import test_italy_sdi_connection

		out = test_italy_sdi_connection(branch=branch, company=company)
		out.setdefault("country_code", "IT")
		out.setdefault("kind", "fatturapa")
	elif code == "BR":
		from omnexa_einvoice.tax_engine.countries.brazil_sefaz import test_brazil_sefaz_connection

		out = test_brazil_sefaz_connection(branch=branch, company=company)
		out.setdefault("country_code", "BR")
		out.setdefault("kind", "nfe")
	elif code == "PL":
		from omnexa_einvoice.tax_engine.countries.poland_ksef_client import test_poland_ksef_connection

		out = test_poland_ksef_connection(branch=branch, company=company)
		out.setdefault("country_code", "PL")
		out.setdefault("kind", "ksef_fa2")
	elif code == "ES":
		from omnexa_einvoice.tax_engine.countries.spain_aeat import test_spain_aeat_connection

		out = test_spain_aeat_connection(branch=branch, company=company)
		out.setdefault("country_code", "ES")
		out.setdefault("kind", "facturae")
	elif code == "CO":
		from omnexa_einvoice.tax_engine.countries.colombia_dian_client import test_colombia_dian_connection

		out = test_colombia_dian_connection(branch=branch, company=company)
		out.setdefault("country_code", "CO")
		out.setdefault("kind", "dian_ubl")
	elif code == "DE":
		from omnexa_einvoice.tax_engine.countries.germany_xrechnung_client import test_germany_xrechnung_connection

		out = test_germany_xrechnung_connection(branch=branch, company=company)
		out.setdefault("country_code", "DE")
		out.setdefault("kind", "xrechnung")
	elif code == "FR":
		from omnexa_einvoice.tax_engine.countries.france_pdp import test_france_pdp_connection

		out = test_france_pdp_connection(branch=branch, company=company)
		out.setdefault("country_code", "FR")
		out.setdefault("kind", "facturx")
	elif code == "AE":
		from omnexa_einvoice.uae.api_client import test_uae_asp_connection

		out = test_uae_asp_connection(branch=branch, company=company)
		out.setdefault("country_code", "AE")
		out.setdefault("kind", "pint_ae")
	elif code in ("AR", "CL", "PE"):
		from omnexa_einvoice.tax_engine.countries.latam_authority_client import test_latam_authority_connection

		out = test_latam_authority_connection(country_code=code, branch=branch, company=company)
		out.setdefault("country_code", code)
		out.setdefault("kind", "latam_invoice")
	elif code == "JO":
		from omnexa_einvoice.tax_engine.countries.jofotara_client import test_jofotara_connection

		out = test_jofotara_connection(branch=branch, company=company)
		out.setdefault("country_code", "JO")
		out.setdefault("kind", "jofotara")
	elif code in PLUGIN_COUNTRY_CODES:
		out = _test_plugin(branch, code)
	else:
		out = {
			"ok": False,
			"branch": branch,
			"country_code": code,
			"message": _("Country {0} is not configured for tax testing.").format(code),
		}

	out["tab_label"] = spec.get("tab_label") or country_tab_label(code)
	out["button_label"] = spec.get("button_label")
	out.setdefault("country_code", code)
	out.setdefault("kind", spec.get("kind"))
	return out
