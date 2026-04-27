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

		frm.add_custom_button(__("Sign"), async () => {
			let pin = "";
			if (frm.doc.submission_kind === "E-Receipt") {
				const values = await frappe.prompt(
					[{ fieldname: "pin", fieldtype: "Password", label: __("Token PIN"), reqd: 0 }],
					() => {},
					__("Sign Submission"),
					__("Sign"),
				);
				pin = values?.pin || "";
			}
			await frappe.call({
				method: "omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.sign_submission",
				args: { name: frm.doc.name, pin },
				freeze: true,
				freeze_message: __("Signing..."),
			});
			await frm.reload_doc();
		});

		frm.add_custom_button(__("Send to ETA"), async () => {
			await frappe.call({
				method: "omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.send_submission_to_eta",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Sending..."),
			});
			await frm.reload_doc();
		}).addClass("btn-primary");
	},
});
