# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Sales Invoice hooks for international plugin countries (not EG/SA)."""

from __future__ import annotations

import frappe

from omnexa_einvoice.branch_eta import resolve_branch_for_document
from omnexa_einvoice.tax_engine.country_catalog import PLUGIN_COUNTRY_CODES
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings
from omnexa_einvoice.tax_engine.plugin.queue import enqueue_phase2
from omnexa_einvoice.tax_engine.router import is_egypt_branch, resolve_tax_provider_for_branch


def sales_invoice_international_tax_on_submit(doc, method=None) -> None:
	"""Queue a single Phase 2 job (Phase 1 + ASP) when auto-submit is enabled."""
	if doc.doctype != "Sales Invoice" or doc.docstatus != 1:
		return
	if getattr(doc.flags, "skip_international_tax_auto_submit", False):
		return
	branch = resolve_branch_for_document(doc)
	if not branch or is_egypt_branch(branch):
		return
	routing = resolve_tax_provider_for_branch(branch)
	code = routing.get("country_code")
	if code not in PLUGIN_COUNTRY_CODES:
		return
	settings = get_country_tax_settings(doc.company, code, branch=branch)
	if not settings or not settings.get("enabled") or not settings.get("auto_submit_on_si_submit"):
		return
	payload = {
		"reference_name": doc.name,
		"company": doc.company,
		"document_type": "invoice",
	}
	enqueue_phase2(payload, country_code=code)
