# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Hub entry point for Saudi ZATCA — routes to Phase 1 or Phase 2."""

from __future__ import annotations

from typing import Any

from frappe import _

from omnexa_core.omnexa_core.integration_hub import IntegrationHubError, IntegrationResult

from omnexa_einvoice.zatca import audit
from omnexa_einvoice.zatca.constants import (
	ADAPTER_NAME,
	DOCUMENT_TYPES,
	PHASE_1,
	PHASE_2,
	PHASES,
)
from omnexa_einvoice.zatca.phase1.service import run_phase1
from omnexa_einvoice.zatca.phase2.service import run_phase2


def validate_zatca_payload(payload: dict[str, Any]) -> dict[str, str]:
	reference = (payload.get("reference_name") or "").strip()
	document_type = (payload.get("document_type") or "").strip().lower()
	phase = (payload.get("phase") or PHASE_2).strip().lower()
	if not reference:
		raise IntegrationHubError(_("reference_name is required for ZATCA submission."))
	if document_type not in DOCUMENT_TYPES:
		raise IntegrationHubError(
			_("ZATCA supports document_type values: tax_invoice, simplified_invoice, credit_note.")
		)
	if phase not in PHASES:
		raise IntegrationHubError(_("ZATCA phase must be phase1 or phase2."))
	if phase == PHASE_2:
		company = (payload.get("company") or "").strip()
		csid = (payload.get("csid_reference") or "").strip()
		if not csid and not company:
			raise IntegrationHubError(
				_("ZATCA Phase 2 requires company or csid_reference in the payload.")
			)
	return {"reference": reference, "document_type": document_type, "phase": phase}


def process_zatca_hub_request(payload: dict[str, Any]) -> IntegrationResult:
	"""Called from ``SaudiZatcaAdapter.process`` only."""
	meta = validate_zatca_payload(payload)
	reference = meta["reference"]
	document_type = meta["document_type"]
	phase = meta["phase"]

	audit.log_zatca_event(
		"hub_request",
		company=payload.get("company"),
		reference=reference,
		phase=phase,
		document_type=document_type,
		ok=True,
	)

	try:
		if phase == PHASE_1:
			result = run_phase1(payload)
			status = "completed"
			message = _("ZATCA Phase 1 completed locally.")
		else:
			result = run_phase2(payload)
			status = result.get("status") or "queued"
			message = result.get("message") or _("ZATCA Phase 2 queued.")
	except Exception as exc:
		audit.log_zatca_event(
			"hub_error",
			company=payload.get("company"),
			reference=reference,
			phase=phase,
			document_type=document_type,
			ok=False,
			details={"error": str(exc)},
		)
		raise

	provider_ref = f"ZATCA-{document_type.upper()}-{reference}"
	return IntegrationResult(
		status=status if status in {"queued", "completed", "failed"} else "queued",
		provider_reference=provider_ref,
		message=message,
		data={"adapter": ADAPTER_NAME, "phase": phase, "zatca": result},
	)
