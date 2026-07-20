# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Shared live-validation helpers for EU authority HTTP clients (W-B)."""

from __future__ import annotations

from typing import Any

from omnexa_einvoice.tax_engine.countries.country_http_uat import throw_if_missing, validate_required_fields


def validate_eu_client_for_live(
	cfg: Any,
	*,
	title: str,
	tax_field: str,
	tax_label: str,
	url_field: str,
	url_label: str,
	extra: list[tuple[str, str]] | None = None,
) -> None:
	required = [
		(tax_field, tax_label),
		(url_field, url_label),
	]
	if extra:
		required.extend(extra)
	throw_if_missing(
		validate_required_fields(
			{tax_field: getattr(cfg, tax_field), url_field: getattr(cfg, url_field)},
			required,
		),
		title=title,
	)
