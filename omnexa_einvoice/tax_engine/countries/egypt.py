# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
Egypt ETA — entry points remain in ``eta_*`` and ``e_invoice_submission``.

This module documents the boundary only; do not move ETA logic here.
"""

from omnexa_einvoice.branch_eta import (
	branch_einvoice_enabled,
	branch_ereceipt_enabled,
	get_eta_branch_settings,
	resolve_branch_for_document,
)
from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
	ensure_submission_for_document,
)

__all__ = [
	"branch_einvoice_enabled",
	"branch_ereceipt_enabled",
	"ensure_submission_for_document",
	"get_eta_branch_settings",
	"resolve_branch_for_document",
]
