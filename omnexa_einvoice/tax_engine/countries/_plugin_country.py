# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Factory for country plugin entry points."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_core.omnexa_core.integration_hub import IntegrationResult

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.plugin.service import run_phase1, run_phase2


def make_country_handlers(country_code: str):
	code = country_code.upper()
	meta = COUNTRY_REGISTRY[code]

	def process_hub_payload(payload, *, meta=meta):
		result = run_phase1(payload, country_code=code)
		ref = (payload.get("reference_name") or "").strip()
		dt = (payload.get("document_type") or "invoice").strip().lower()
		return IntegrationResult(
			status="completed",
			provider_reference=f"{code}-{dt.upper()}-{ref}",
			message=_("{0} Phase 1 ({1}) completed.").format(
				meta.label, result.get("framework") or "plugin"
			),
			data={"country_code": code, "phase1": result, "framework": result.get("framework")},
		)

	def dispatch_sales_invoice(doc, *, branch=None, phase=None, **kwargs):
		payload = {
			"reference_name": doc.name,
			"company": doc.company,
			"document_type": "invoice",
			"branch": branch,
		}
		ph = (phase or kwargs.get("phase") or "phase1").strip().lower()
		if ph == "phase2":
			return run_phase2(payload, country_code=code, sync=bool(kwargs.get("sync")))
		return run_phase1(payload, country_code=code)

	return process_hub_payload, dispatch_sales_invoice
