# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from omnexa_core.omnexa_core.integration_hub import IntegrationHubError, get_default_hub


class EInvoiceSubmission(Document):
	def validate(self):
		if not self.reference_doctype or not self.reference_name:
			frappe.throw(_("Reference DocType and Reference Name are required."))
		if not frappe.db.exists(self.reference_doctype, self.reference_name):
			frappe.throw(_("Reference document does not exist."))
		if not self.company and self.reference_doctype == "Sales Invoice":
			co = frappe.db.get_value("Sales Invoice", self.reference_name, "company")
			if co:
				self.company = co
		self._merge_company_defaults()
		if not self.adapter_name:
			frappe.throw(_("Adapter is required."))
		self._validate_lifecycle_controls()
		if self.extra_json and str(self.extra_json).strip():
			try:
				parsed = json.loads(self.extra_json)
			except json.JSONDecodeError as exc:
				raise frappe.ValidationError(_("Extra Payload must be valid JSON.")) from exc
			if not isinstance(parsed, dict):
				raise frappe.ValidationError(_("Extra Payload must be a JSON object."))

	def _validate_lifecycle_controls(self):
		if not self.company:
			frappe.throw(_("Company is mandatory for e-invoice submission."), title=_("Compliance"))
		if not self.submission_channel:
			frappe.throw(_("Submission Channel is mandatory."), title=_("Compliance"))
		if self.operation in {"submit", "cancel"} and not self.reference_name:
			frappe.throw(_("Reference Name is mandatory for submit/cancel operations."), title=_("Reference"))
		if self.status == "Completed" and not self.provider_reference:
			frappe.throw(_("Provider Reference is mandatory when status is Completed."), title=_("Result"))

	def _merge_company_defaults(self) -> None:
		"""Fill adapter / extra_json from Tax Authority Profile + Signing Profile (setdefault semantics)."""
		if not self.company:
			return
		if not frappe.db.exists("DocType", "Tax Authority Profile"):
			return
		base: dict = {}
		if self.extra_json and str(self.extra_json).strip():
			try:
				base = json.loads(self.extra_json)
			except json.JSONDecodeError:
				return
		if not isinstance(base, dict):
			return
		tap = frappe.db.get_value(
			"Tax Authority Profile",
			{"company": self.company},
			["default_einvoice_adapter", "taxpayer_registration_id", "zatca_reporting_phase"],
			as_dict=True,
		)
		if tap:
			if not self.adapter_name and tap.get("default_einvoice_adapter"):
				self.adapter_name = tap.get("default_einvoice_adapter")
			if tap.get("taxpayer_registration_id"):
				base.setdefault("taxpayer_rin", tap.get("taxpayer_registration_id"))
			if tap.get("zatca_reporting_phase"):
				base.setdefault("phase", tap.get("zatca_reporting_phase"))
		if frappe.db.exists("DocType", "Signing Profile"):
			sign = frappe.db.get_value(
				"Signing Profile",
				{"company": self.company},
				["default_signer_mode"],
				as_dict=True,
			)
			if sign and sign.get("default_signer_mode"):
				base.setdefault("signer_mode", sign.get("default_signer_mode"))
		if base:
			self.extra_json = json.dumps(base, indent=2, sort_keys=True)

	def dispatch_now(self) -> None:
		"""Send payload to IntegrationHub and persist result (idempotent per name+adapter+operation)."""
		self.reload()
		if self.status not in ("Draft", "", None):
			frappe.throw(_("Only submissions in Draft can be dispatched."))
		payload = self._build_payload()
		hub = get_default_hub()
		idem = f"{self.name}:{self.adapter_name}:{self.operation}"
		try:
			result = hub.dispatch(self.adapter_name, payload, idempotency_key=idem)
		except IntegrationHubError as err:
			self.db_set(
				{
					"status": "Failed",
					"integration_message": str(err),
				},
				update_modified=False,
			)
			raise
		next_status = "Queued" if (result.status or "").lower() == "queued" else "Completed"
		self.db_set(
			{
				"status": next_status,
				"provider_reference": result.provider_reference or "",
				"integration_message": result.message or "",
				"result_data": json.dumps(result.data, default=str) if result.data else "",
			},
			update_modified=False,
		)

	def _build_payload(self) -> dict:
		payload: dict = {
			"reference_name": self.reference_name,
			"document_type": (self.document_type or "invoice").strip().lower(),
			"operation": (self.operation or "submit").strip().lower(),
		}
		if self.extra_json and self.extra_json.strip():
			extra = json.loads(self.extra_json)
			payload.update(extra)
		return payload


@frappe.whitelist()
def dispatch_submission(name: str):
	"""Desk / API entry point to run hub dispatch for a draft submission."""
	doc = frappe.get_doc("E Invoice Submission", name)
	doc.dispatch_now()
	return doc.as_dict()
