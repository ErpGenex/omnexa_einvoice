# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Enrich neutral document dict with buyer/seller tax IDs from ERPNext (read-only)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt

from omnexa_einvoice.tax_engine.country_catalog import normalize_country_code
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings
from omnexa_einvoice.tax_engine.plugin.document import build_from_payload
from omnexa_einvoice.tax_engine.plugin.specs import get_spec


def _buyer_from_customer(customer: str | None) -> dict[str, Any]:
	if not customer:
		return {}
	row = frappe.db.get_value(
		"Customer",
		customer,
		["customer_name", "tax_id"],
		as_dict=True,
	)
	if not row:
		return {}
	return {"name": row.customer_name or customer, "tax_registration": (row.tax_id or "").strip()
	}


def build_enriched_document(payload: dict[str, Any], *, country_code: str) -> dict[str, Any]:
	code = normalize_country_code(country_code)
	spec = get_spec(code)
	document = build_from_payload(payload, country_code=code, currency=spec.default_currency)
	company = document.get("company") or payload.get("company") or ""
	branch = payload.get("branch") or document.get("branch")
	settings = get_country_tax_settings(company, code, branch=branch) if company else None
	seller = dict(document.get("seller") or {})
	if settings:
		tin = (settings.get("tax_registration_number") or "").strip()
		if tin:
			seller["tax_registration"] = tin
	document["seller"] = seller
	if document.get("customer") and not document.get("buyer"):
		document["buyer"] = _buyer_from_customer(document.get("customer"))
	elif not document.get("buyer"):
		document["buyer"] = _buyer_from_customer(payload.get("customer"))
	# Normalize line amounts
	for line in document.get("lines") or []:
		qty = flt(line.get("qty", 1)) or 1
		rate = flt(line.get("rate", 0))
		line.setdefault("net_amount", flt(line.get("amount")) or qty * rate)
		line.setdefault("qty", qty)
		line.setdefault("rate", rate)
	document["country_code"] = code
	if settings and settings.get("configuration_json"):
		try:
			import json

			cfg = json.loads(settings.configuration_json)
			if isinstance(cfg, dict):
				if code == "IT":
					document["italy"] = {
						"partita_iva": cfg.get("partita_iva") or seller.get("tax_registration"),
						"codice_destinatario": cfg.get("codice_destinatario"),
						"regime_fiscale": cfg.get("regime_fiscale")
	}
				if code == "PL":
					document["poland"] = {"nip": cfg.get("nip") or seller.get("tax_registration")
	}
				if code == "ES":
					document["spain"] = {"nif": cfg.get("nif") or seller.get("tax_registration")
	}
				if code == "CO":
					document["colombia"] = {
						"nit": cfg.get("nit") or seller.get("tax_registration"),
						"software_id": cfg.get("software_id")
	}
				if code == "DE":
					document["germany"] = {"leitweg_id": cfg.get("leitweg_id")
	}
				if code == "FR":
					document["france"] = {
						"siret": cfg.get("siret") or seller.get("tax_registration"),
						"profile": cfg.get("profile")
	}
				if code == "IN":
					document["india"] = {
						"gstin": cfg.get("gstin") or seller.get("tax_registration"),
						"gsp_base_url": cfg.get("gsp_base_url")
	}
		except json.JSONDecodeError:
			pass
	if code == "IN":
		for line in document.get("lines") or []:
			if line.get("item_code") and not line.get("hsn_code"):
				hsn = frappe.db.get_value("Item", line["item_code"], "gst_hsn_code")
				if hsn:
					line["hsn_code"] = str(hsn).strip()
	return document
