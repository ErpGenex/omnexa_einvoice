// Copyright (c) 2026, Omnexa and contributors
// License: MIT

/** Country-specific e-invoice print format on Sales Invoice. */

async function resolve_einvoice_print_format(frm) {
	if (frm.is_new() || !frm.doc.name) {
		return null;
	}
	const r = await frappe.call({
		method: "omnexa_einvoice.einvoice_print.resolve.get_print_format_for_sales_invoice",
		args: { docname: frm.doc.name },
	});
	return r.message;
}

frappe.ui.form.on("Sales Invoice", {
	async refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		const pf = await resolve_einvoice_print_format(frm);
		if (!pf) {
			return;
		}
		frm.meta.default_print_format = pf;
		frm.add_custom_button(
			__("E-Invoice Print"),
			() => frappe.utils.print(frm.doctype, frm.doc.name, pf),
			__("E-Invoice")
		);
	},
});
