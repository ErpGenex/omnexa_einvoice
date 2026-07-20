# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Jinja helpers for e-invoice print formats."""

from __future__ import annotations

from omnexa_einvoice.einvoice_print.context import get_sales_invoice_print_context


def einvoice_print_context(doc) -> dict:
	"""Usage in Print Format HTML: {% set p = einvoice_print_context(doc) %}"""
	return get_sales_invoice_print_context(doc)
