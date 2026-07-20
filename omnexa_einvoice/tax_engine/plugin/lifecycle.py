# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Normalize authority responses to internal lifecycle states (plugin only)."""

from __future__ import annotations

from typing import Any

# Internal log / UI states
DRAFT = "Draft"
SIGNED = "Signed"
SUBMITTED = "Submitted"
ACCEPTED = "Accepted"
REJECTED = "Rejected"
FAILED = "Failed"
CANCELLED = "Cancelled"

_AUTHORITY_TO_INTERNAL: dict[str, str] = {
	"ACCEPTED": ACCEPTED,
	"ACCEPT": ACCEPTED,
	"APPROVED": ACCEPTED,
	"CLEARED": ACCEPTED,
	"SUCCESS": ACCEPTED,
	"REJECTED": REJECTED,
	"REJECT": REJECTED,
	"FAILED": FAILED,
	"ERROR": FAILED,
	"CANCELLED": CANCELLED,
	"CANCELED": CANCELLED,
	"PENDING": SUBMITTED,
	"PROCESSING": SUBMITTED,
	"SUBMITTED": SUBMITTED,
}


def normalize_authority_status(raw: str | None) -> str:
	text = (raw or "").strip().upper()
	if not text:
		return SUBMITTED
	return _AUTHORITY_TO_INTERNAL.get(text, SUBMITTED)


def map_api_result_to_log_status(api_result: dict[str, Any]) -> str:
	status = normalize_authority_status(
		str(api_result.get("status") or api_result.get("documentStatus") or "")
	)
	if api_result.get("ok") and status in (ACCEPTED, SUBMITTED):
		return ACCEPTED if status == ACCEPTED else SUBMITTED
	if not api_result.get("ok"):
		return FAILED
	return status
