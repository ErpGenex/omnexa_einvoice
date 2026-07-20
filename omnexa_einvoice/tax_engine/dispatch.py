# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
Route tax submissions by branch country — each country uses its own adapter module.

Egypt: ``einvoice_eta`` → existing ``eta_*`` pipelines (not replaced here).
Saudi: ``einvoice_zatca`` → ``zatca.dispatch`` only.
Others: ``tax_engine/countries/<country>.py`` plugins.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_core.omnexa_core.integration_hub import IntegrationHubError, get_default_hub

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.countries import dispatch_sales_invoice_for_country
from omnexa_einvoice.tax_engine.router import is_egypt_branch, resolve_tax_provider_for_branch


def build_hub_payload_for_branch(
	branch: str | None,
	*,
	reference_name: str,
	document_type: str,
	operation: str = "submit",
	extra: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
	"""Return (adapter_name, payload) for IntegrationHub.dispatch."""
	routing = resolve_tax_provider_for_branch(branch)
	adapter_name = routing["tax_provider"]
	payload: dict[str, Any] = {
		"reference_name": reference_name,
		"document_type": document_type,
		"operation": operation,
		"company": extra.get("company") if extra else None,
		"branch": branch,
		"country_code": routing["country_code"]
	}
	if extra:
		payload.update(extra)
	return adapter_name, payload


def dispatch_for_branch(
	branch: str | None,
	*,
	reference_name: str,
	document_type: str,
	operation: str = "submit",
	idempotency_key: str | None = None,
	extra: dict[str, Any] | None = None,
):
	"""Dispatch to country adapter via IntegrationHub."""
	adapter_name, payload = build_hub_payload_for_branch(
		branch,
		reference_name=reference_name,
		document_type=document_type,
		operation=operation,
		extra=extra,
	)
	hub = get_default_hub()
	return hub.dispatch(adapter_name, payload, idempotency_key=idempotency_key)


@frappe.whitelist()
def dispatch_tax_for_document(
	reference_doctype: str,
	reference_name: str,
	*,
	branch: str | None = None,
	phase: str | None = None,
) -> dict[str, Any]:
	"""
	Unified entry by branch country.
	Egypt e-Receipt: ETA console only. Egypt e-Invoice: ensure_submission path.
	"""
	if reference_doctype not in ("Sales Invoice", "POS Invoice"):
		frappe.throw(_("Only Sales Invoice and POS Invoice are supported."))

	doc = frappe.get_doc(reference_doctype, reference_name)
	if not branch:
		from omnexa_einvoice.branch_eta import resolve_branch_for_document

		branch = resolve_branch_for_document(doc)

	routing = resolve_tax_provider_for_branch(branch)
	country_code = routing["country_code"]

	if is_egypt_branch(branch):
		if reference_doctype == "POS Invoice":
			frappe.throw(
				_("Egypt e-Receipt must be sent from ETA E-Receipt Console, not the tax hub."),
				title=_("E-Receipt"),
			)
		from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
			ensure_submission_for_document,
		)

		return ensure_submission_for_document(reference_doctype, reference_name)

	if country_code == "SA":
		from omnexa_einvoice.tax_engine.countries.saudi import dispatch_zatca_for_sales_invoice

		return dispatch_zatca_for_sales_invoice(doc, branch=branch, phase=phase or "phase1")

	meta = COUNTRY_REGISTRY.get(country_code)
	if meta and meta.pipeline_enabled and country_code not in ("EG", "SA"):
		if reference_doctype != "Sales Invoice":
			frappe.throw(
				_("{0} does not support POS yet.").format(meta.label),
				title=meta.label,
			)
		return dispatch_sales_invoice_for_country(
			country_code, doc, branch=branch, phase=phase
		)

	raise IntegrationHubError(
		_("No tax dispatch handler for country {0} (provider {1}).").format(
			country_code, routing["tax_provider"]
		)
	)


@frappe.whitelist()
def list_supported_countries() -> list[dict[str, Any]]:
	"""Desk API: countries and production readiness."""
	from omnexa_einvoice.tax_engine.deploy_check import list_country_status

	return list_country_status()
