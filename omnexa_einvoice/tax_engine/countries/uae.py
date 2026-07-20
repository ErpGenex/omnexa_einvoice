# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""United Arab Emirates — Peppol PINT AE (FTA framework)."""

from __future__ import annotations

from typing import Any

from frappe import _

from omnexa_core.omnexa_core.integration_hub import IntegrationResult

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.uae.service import run_phase1, run_phase2

META = COUNTRY_REGISTRY["AE"]


def process_hub_payload(payload: dict[str, Any], *, meta=META):
	result = run_phase1(payload)
	ref = (payload.get("reference_name") or "").strip()
	dt = (payload.get("document_type") or "invoice").strip().lower()
	return IntegrationResult(
		status="completed",
		provider_reference=f"AE-{dt.upper()}-{ref}",
		message=_("{0} Phase 1 (PINT AE UBL) completed.").format(meta.label),
		data={"country_code": "AE", "phase1": result, "framework": "PINT-AE"
	},
	)


def dispatch_sales_invoice(doc, *, branch=None, phase=None, **kwargs):
	payload = {
		"reference_name": doc.name,
		"company": doc.company,
		"document_type": "invoice",
		"branch": branch
	}
	ph = (phase or kwargs.get("phase") or "phase1").strip().lower()
	if ph == "phase2":
		return run_phase2(payload, sync=bool(kwargs.get("sync")))
	return run_phase1(payload)
