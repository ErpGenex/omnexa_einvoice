# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Country e-invoice adapters (ETA Egypt, ZATCA Saudi) for ``omnexa_core`` IntegrationHub."""

from typing import Any

from frappe import _

from omnexa_core.omnexa_core.integration_hub import IntegrationHubError, IntegrationResult


class EgyptETAAdapter:
	name = "einvoice_eta"
	supported_document_types = {"invoice", "receipt", "credit_note"}
	supported_operations = {"submit", "cancel", "download"}

	def process(self, payload: dict[str, Any]) -> IntegrationResult:
		reference = (payload.get("reference_name") or "").strip()
		document_type = (payload.get("document_type") or "").strip().lower()
		operation = (payload.get("operation") or "").strip().lower() or "submit"
		signer_mode = (payload.get("signer_mode") or "").strip().lower() or "remote"
		if not reference:
			raise IntegrationHubError(_("reference_name is required for ETA submission."))
		if document_type not in self.supported_document_types:
			raise IntegrationHubError(
				_("ETA supports document_type values: invoice, receipt, credit_note.")
			)
		if operation not in self.supported_operations:
			raise IntegrationHubError(_("ETA operation must be submit, cancel, or download."))
		if signer_mode not in {"remote", "windows_app"}:
			raise IntegrationHubError(_("ETA signer_mode must be remote or windows_app."))
		if not (payload.get("taxpayer_rin") or "").strip():
			raise IntegrationHubError(_("taxpayer_rin is required for ETA submission."))
		if operation == "cancel" and not (payload.get("authority_uuid") or "").strip():
			raise IntegrationHubError(_("authority_uuid is required for ETA cancel operation."))
		provider_ref = f"ETA-{operation.upper()}-{document_type.upper()}-{reference}"
		return IntegrationResult(
			status="queued",
			provider_reference=provider_ref,
			message=f"Queued for ETA {operation}",
			data={"operation": operation, "signer_mode": signer_mode
	},
		)


class SaudiZatcaAdapter:
	name = "einvoice_zatca"
	supported_document_types = {"tax_invoice", "simplified_invoice", "credit_note"}

	def process(self, payload: dict[str, Any]) -> IntegrationResult:
		from omnexa_einvoice.zatca.dispatch import process_zatca_hub_request

		return process_zatca_hub_request(payload)
