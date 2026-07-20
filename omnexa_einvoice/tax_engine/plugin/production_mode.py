# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Production vs sandbox/mock gates for international tax plugin."""

from __future__ import annotations

import frappe


def allow_mock_api() -> bool:
	"""Mock ASP responses only in tests or when explicitly enabled on site."""
	if frappe.flags.in_test:
		return True
	if frappe.conf.get("tax_plugin_mock_api"):
		return True
	return bool(frappe.conf.get("developer_mode"))


def is_live_production_settings(settings) -> bool:
	"""Country Tax Settings row is marked for live government/ASP submission."""
	return bool(settings.get("enabled")) and bool(settings.get("live_production"))


def requires_real_api(settings) -> bool:
	"""Phase 2 must call a real ASP — not mock."""
	if allow_mock_api():
		return False
	if not settings:
		return True
	if (settings.get("api_environment") or "").strip().lower() == "production":
		return True
	return is_live_production_settings(settings)
