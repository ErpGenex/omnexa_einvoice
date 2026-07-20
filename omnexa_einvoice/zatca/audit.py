# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA audit trail — Error Log + structured context (no Egypt modules)."""

from __future__ import annotations

import json
from typing import Any

import frappe


def log_zatca_event(
	event: str,
	*,
	company: str | None = None,
	reference: str | None = None,
	phase: str | None = None,
	document_type: str | None = None,
	ok: bool = True,
	details: dict[str, Any] | None = None,
) -> None:
	"""Best-effort audit; never raises."""
	payload = {
		"module": "omnexa_einvoice.zatca",
		"event": event,
		"company": company,
		"reference": reference,
		"phase": phase,
		"document_type": document_type,
		"ok": ok,
		"details": details or {},
	}
	try:
		frappe.logger("zatca").info(json.dumps(payload, ensure_ascii=False, default=str))
	except Exception:
		pass
	if not ok:
		try:
			frappe.log_error(
				title=f"ZATCA: {event}",
				message=json.dumps(payload, indent=2, ensure_ascii=False, default=str),
			)
		except Exception:
			pass
