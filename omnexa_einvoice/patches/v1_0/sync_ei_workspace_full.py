# Copyright (c) 2026, Omnexa
import os
import frappe
from frappe.modules.import_file import import_file_by_path

def _ensure_pages():
	p = frappe.get_app_path("omnexa_einvoice", "omnexa_einvoice", "page")
	if not os.path.isdir(p):
		return
	for folder in os.listdir(p):
		jp = os.path.join(p, folder, f"{folder}.json")
		if os.path.isfile(jp):
			import_file_by_path(jp, force=True)

def execute():
	_ensure_pages()
	if frappe.db.exists("Workspace", "E-Invoice"):
		from omnexa_einvoice.workspace.ei_workspace import sync_ei_workspace_menu
		sync_ei_workspace_menu(save=True, rebuild=True)
