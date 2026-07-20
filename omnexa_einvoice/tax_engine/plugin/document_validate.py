# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""XML/JSON validation before international plugin submit."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.country_catalog import get_catalog_entry, normalize_country_code


def _validate_well_formed_xml(xml_text: str, country_code: str) -> None:
	text = (xml_text or "").strip()
	if not text:
		frappe.throw(_("Empty XML for {0}.").format(country_code), title=_("Tax Validation"))
	if text.startswith("{"):
		return
	try:
		ET.fromstring(text.encode("utf-8"))
	except ET.ParseError as exc:
		frappe.throw(
			_("Malformed XML for {0}: {1}").format(country_code, exc),
			title=_("Tax Validation"),
		)


def _validate_gst_json(text: str, country_code: str) -> None:
	try:
		data = json.loads(text)
	except json.JSONDecodeError as exc:
		frappe.throw(_("Invalid GST JSON for {0}: {1}").format(country_code, exc), title=_("Tax Validation"))
	for key in ("Version", "DocDtls", "SellerDtls", "BuyerDtls", "ItemList"):
		if key not in data:
			frappe.throw(
				_("GST IRN JSON for {0} missing required key: {1}").format(country_code, key),
				title=_("Tax Validation"),
			)


def validate_document_xml(
	xml_text: str,
	country_code: str,
	*,
	config: dict[str, Any] | None = None,
) -> None:
	"""Validate when Configuration JSON sets validate_xsd=true (plugin countries only)."""
	code = normalize_country_code(country_code)
	if code in ("EG", "SA"):
		return
	entry = get_catalog_entry(code)
	if entry and entry.engine == "gst_irn":
		_validate_gst_json(xml_text, code)
	else:
		_validate_well_formed_xml(xml_text, code)
	cfg = config or {}
	if not cfg.get("validate_xsd"):
		return
	entry = get_catalog_entry(code)
	framework = entry.framework if entry else code
	# National XSD paths are per-wave; fail closed in live mode when requested but not wired.
	xsd_path = (cfg.get("xsd_path") or "").strip()
	if not xsd_path:
		frappe.throw(
			_(
				"validate_xsd is enabled for {0} ({1}) but xsd_path is missing in Configuration JSON."
			).format(code, framework),
			title=_("Tax Validation"),
		)
	try:
		from lxml import etree
	except ImportError as exc:
		frappe.throw(
			_("XSD validation requires lxml on the server: {0}").format(exc),
			title=_("Tax Validation"),
		)
	schema_doc = etree.parse(xsd_path)
	schema = etree.XMLSchema(schema_doc)
	doc = etree.fromstring(xml_text.encode("utf-8"))
	if not schema.validate(doc):
		errors = "; ".join(str(e) for e in schema.error_log[:5])
		frappe.throw(
			_("XML validation failed for {0}: {1}").format(code, errors),
			title=_("Tax Validation"),
		)
