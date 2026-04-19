// Copyright (c) 2026, Omnexa and contributors
// License: MIT. See license.txt

frappe.ui.form.on("E Invoice Submission", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 0) {
			return;
		}
		if (frm.doc.status && frm.doc.status !== "Draft") {
			return;
		}
		frm.add_custom_button(__("Dispatch to authority"), () => {
			frappe.call({
				method: "omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.dispatch_submission",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Dispatching…"),
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({ message: __("Integration hub updated"), indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		}).addClass("btn-primary");
	},
});
